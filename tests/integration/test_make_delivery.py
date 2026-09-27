"""F10: MySQL 8 aislado, fuentes sintéticas y todos los POST simulados."""

import json
from dataclasses import replace
from datetime import date
from uuid import uuid4

import httpx
import pymysql
import pytest
from etl_checks import business_snapshot
from test_etl import order_row, write_orders
from test_products import _row, _write
from test_stock_persistence import mock_api, stock_row

from src import db
from src.analytics import AnalyticsQueries
from src.config import MakeOptions, Settings
from src.etl import make_client, runner
from src.etl.make_client import DeliveryError, deliver_run

AS_OF = date(2026, 9, 25)


def prepare(settings: Settings, monkeypatch: pytest.MonkeyPatch, *, stock: int = 5) -> None:
    _write(settings, [_row(), _row()])
    row = order_row()
    row[1] = "2026-08-15"
    write_orders(settings, [row, row])
    mock_api(monkeypatch, [stock_row(quantity=stock)])


def audit(settings: Settings, run_id: str) -> tuple:
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, make_summary, make_status, make_attempts, make_error_code, "
            "make_last_attempt_at, make_accepted_at, counters FROM etl_runs WHERE id = %s",
            (run_id,),
        )
        return cursor.fetchone()


def test_frozen_summary_matches_sql_counters_and_duplicate_only_run(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(settings, monkeypatch)
    monkeypatch.setattr(runner, "deliver_run", lambda *_: pytest.fail("Make desactivado"))
    result = runner.run_etl(settings, as_of=AS_OF)
    row = audit(settings, result.run_id)
    summary = json.loads(row[1])
    assert row[0] == "completed"
    assert row[2:5] == ("not_applicable", 0, None)
    assert summary["run_id"] == result.run_id
    assert summary["schema_version"] == "etl-summary-v1"
    assert summary["rows"] == json.loads(row[7])
    assert summary["rows"]["catalog_csv"]["rows_deduplicated"] == 1
    assert summary["rows"]["orders_csv"]["rows_deduplicated"] == 1
    assert summary["rows_rejected"] == 0
    assert summary["rejected_by_reason"] == []
    assert summary["alert_required"] is False
    assert summary["products_loaded"] == 1
    assert summary["previous_month"] == "2026-08"
    assert summary["revenue_previous_month"] == "36.00"  # 2 × 20 × (1 − 0.10)
    assert summary["currency"] is None
    assert summary["finished_at"].endswith("Z")
    assert summary["as_of"] == "2026-09-25"
    assert "Cliente sintético" not in row[1]
    with db.connect(settings) as connection:
        queries = AnalyticsQueries(connection, AS_OF)
        assert str(queries.previous_month_sales().revenue) == summary["revenue_previous_month"]
        assert queries.low_stock_products() == summary["low_stock_products"] == []


def test_summary_separates_row_rejections_and_reasons_and_uses_low_stock_sql(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(settings, monkeypatch, stock=0)
    _write(settings, [_row(), _row(sku="BAD", nombre="", pvp_recomendado="0")])
    result = runner.run_etl(settings, as_of=AS_OF)
    summary = json.loads(audit(settings, result.run_id)[1])
    assert summary["rows_rejected"] == 1
    assert sum(reason["rows"] for reason in summary["rejected_by_reason"]) == 2
    assert {reason["reason_code"] for reason in summary["rejected_by_reason"]} == {
        "MISSING_REQUIRED_FIELD",
        "NON_POSITIVE_PRICE",
    }
    assert summary["low_stock_count"] == 1
    assert summary["low_stock_products"] == [
        {"sku": "PRV-001", "name": "Producto sintético", "stock_total": 0, "recent_units": 2}
    ]
    assert summary["alert_required"] is True


@pytest.mark.parametrize("failure", ["500", "timeout"])
def test_delivery_fails_after_commit_and_retry_preserves_original_snapshot(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    prepare(settings, monkeypatch, stock=0)
    enabled = replace(settings, make=MakeOptions("https://example.invalid/synthetic-secret"))
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        sent.append(payload)
        # Otro lector ve negocio y resumen confirmados antes de enviar HTTP.
        row = audit(settings, payload["run_id"])
        assert row[0] == "completed" and row[2] == "pending" and row[3] == 1
        assert json.loads(row[1]) == payload
        with db.connect(settings) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE last_run_id = %s", (payload["run_id"],)
            )
            assert cursor.fetchone()[0] == 1
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic-secret")
        return httpx.Response(500, text="synthetic-secret")

    original_post = make_client.post_summary
    monkeypatch.setattr(
        make_client,
        "post_summary",
        lambda options, payload, transport=None: original_post(
            options, payload, httpx.MockTransport(handler)
        ),
    )
    result = runner.run_etl(enabled, as_of=AS_OF)
    assert result.make_status == ("failed" if failure == "500" else "uncertain")
    assert audit(settings, result.run_id)[0] == "completed"
    assert "secret" not in str(audit(settings, result.run_id)[4])

    # Una publicación posterior cambia ventas/fecha/umbral. Reenviar no debe recalcular nada.
    new_row = order_row(price="200")
    new_row[1] = "2026-09-15"
    write_orders(settings, [new_row])
    runner.run_etl(
        replace(settings, make=MakeOptions(rejection_threshold=99)), as_of=date(2026, 10, 1)
    )
    business = business_snapshot(settings)
    monkeypatch.setattr(make_client, "post_summary", original_post)

    def accepted(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200)

    transport = httpx.MockTransport(accepted)
    assert deliver_run(enabled, result.run_id, transport=transport).status == "accepted"
    assert sent[0] == sent[1]
    assert audit(settings, result.run_id)[3] == 2
    assert audit(settings, result.run_id)[6] is not None
    assert business_snapshot(settings) == business
    # Un accepted no se reenvía implícitamente; --force lo hace de forma deliberada.
    deliver_run(enabled, result.run_id, transport=transport)
    assert len(sent) == 2
    deliver_run(enabled, result.run_id, force=True, transport=transport)
    assert len(sent) == 3 and sent[2] == sent[0]


def test_delivery_lock_blocks_simultaneous_replays(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(settings, monkeypatch)
    result = runner.run_etl(settings, as_of=AS_OF)
    enabled = replace(settings, make=MakeOptions("https://example.invalid/synthetic"))
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", ("make:" + result.run_id,))
        assert cursor.fetchone()[0] == 1
        with pytest.raises(DeliveryError, match="en curso"):
            deliver_run(enabled, result.run_id)
    assert audit(settings, result.run_id)[3] == 0


def test_summary_error_rolls_back_business_and_prevents_http(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(settings, monkeypatch)
    runner.run_etl(settings, as_of=AS_OF)
    before = business_snapshot(settings)
    _write(settings, [_row(precio_coste="200")])

    def fail(*args: object) -> dict:
        raise RuntimeError("Synthetic summary failure")

    monkeypatch.setattr(runner, "make_summary", fail)
    monkeypatch.setattr(runner, "deliver_run", lambda *_: pytest.fail("No HTTP tras rollback"))
    with pytest.raises(RuntimeError, match="Synthetic"):
        runner.run_etl(
            replace(settings, make=MakeOptions("https://example.invalid/test")), as_of=AS_OF
        )
    assert business_snapshot(settings) == before
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT status, make_summary FROM etl_runs ORDER BY started_at DESC LIMIT 1")
        assert cursor.fetchone() == ("failed", None)


def test_migration_can_resume_and_retains_saved_summary(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(settings, monkeypatch)
    result = runner.run_etl(settings, as_of=AS_OF)
    before = audit(settings, result.run_id)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM schema_migrations WHERE version = '004_make_delivery'")
        connection.commit()
        assert db.apply_migration(connection) is True
        assert db.apply_migration(connection) is False
    assert audit(settings, result.run_id) == before


def test_cannot_rebuild_old_run_from_current_business(settings: Settings) -> None:
    enabled = replace(settings, make=MakeOptions("https://example.invalid/synthetic"))
    run_id = str(uuid4())
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO etl_runs (id, status, phase, rules_version) VALUES (%s, 'completed', 'publish', 'old')",
            (run_id,),
        )
        connection.commit()
    with pytest.raises(DeliveryError, match="sin resumen"):
        deliver_run(enabled, run_id)
    assert audit(settings, run_id)[3] == 0


def test_delivery_audit_error_does_not_mark_published_etl_failed(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(settings, monkeypatch)

    def fail(*args: object) -> None:
        raise pymysql.OperationalError(2006, "synthetic-secret")

    monkeypatch.setattr(runner, "deliver_run", fail)
    result = runner.run_etl(
        replace(settings, make=MakeOptions("https://example.invalid/synthetic")), as_of=AS_OF
    )
    row = audit(settings, result.run_id)
    assert result.make_status == "uncertain"
    assert row[0] == "completed" and row[2] == "pending"
    assert json.loads(row[1])["revenue_previous_month"] == "36.00"
