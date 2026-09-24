"""F5 en MySQL real aislado con CSV/XML/HTTP sintéticos."""

import json
from dataclasses import replace

import httpx
import pymysql
import pytest
from test_products import _row, _write

from src import db
from src.config import Settings
from src.etl import repository, runner
from src.etl.stock_client import StockFetchError, fetch_stock


def stock_row(**changes: object) -> dict:
    return {
        "sku": "PRV-001",
        "warehouse": "MAD",
        "quantity": 5,
        "reserved": 2,
        "updated_at": "2026-01-01T00:00:00Z",
        **changes,
    }


def mock_api(monkeypatch: pytest.MonkeyPatch, rows: list, fail_last: bool = False) -> list:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params["page"])
        if fail_last and page == 2:
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={
                "data": rows[(page - 1) * 2 : page * 2],
                "meta": {
                    "page": page,
                    "per_page": 2,
                    "total_records": len(rows),
                    "total_pages": (len(rows) + 1) // 2,
                    "has_next": page * 2 < len(rows),
                },
            },
        )

    def fetch(settings: Settings, run_id: str):
        settings = replace(settings, stock=replace(settings.stock, per_page=2, attempts=2))
        return fetch_stock(
            settings, run_id, transport=httpx.MockTransport(handler), sleep=lambda _: None
        )

    monkeypatch.setattr(runner, "fetch_stock", fetch)
    return requests


def business(settings: Settings) -> tuple:
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, sku, net_cost, in_catalog, stock_total, stock_status, stock_as_of "
            "FROM products ORDER BY sku"
        )
        products = cursor.fetchall()
        cursor.execute(
            "SELECT product_id, warehouse_code, quantity, reserved, updated_at "
            "FROM stock_by_warehouse ORDER BY product_id, warehouse_code"
        )
        return products, cursor.fetchall()


def test_repeat_reconcile_missing_and_constraints(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(settings, [_row(), _row(sku="ZERO"), _row(sku="ABSENT")])
    requests = mock_api(
        monkeypatch,
        [
            stock_row(),
            stock_row(warehouse="BCN", quantity=7, reserved=9),
            stock_row(sku="ZERO", quantity=0, reserved=0),
            stock_row(sku="UNKNOWN"),
        ],
    )
    first = runner.run_etl(settings)
    before = business(settings)
    second = runner.run_etl(settings)
    assert business(settings) == before
    assert len(requests) == 4
    assert first.stock_counters.rows_read == 4
    assert first.stock_counters.rows_accepted == 3
    assert first.stock_counters.rows_rejected == 1
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT sku, stock_total, stock_status FROM products WHERE in_catalog=1 ORDER BY sku"
        )
        assert cursor.fetchall() == (
            ("ABSENT", None, "unknown"),
            ("PRV-001", 12, "known"),
            ("ZERO", 0, "known"),
        )
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku='UNKNOWN'")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT counters, stock_sha256 FROM etl_runs WHERE id=%s", (second.run_id,))
        counters, digest = cursor.fetchone()
        assert json.loads(counters)["stock_api"]["rows_read"] == 4
        assert len(digest) == 64
        cursor.execute("SELECT id FROM products WHERE sku='PRV-001'")
        product_id = cursor.fetchone()[0]
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute(
                "INSERT INTO stock_by_warehouse VALUES (%s,'MAD',0,0,NOW(),%s)",
                (product_id, first.run_id),
            )
        connection.rollback()
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute(
                "INSERT INTO stock_by_warehouse VALUES (99999999,'MAD',0,0,NOW(),%s)",
                (first.run_id,),
            )
        connection.rollback()
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute(
                "UPDATE stock_by_warehouse SET last_run_id='00000000-0000-0000-0000-000000000000'"
            )
        connection.rollback()
        with pytest.raises(pymysql.OperationalError):
            cursor.execute("UPDATE stock_by_warehouse SET quantity=-1")
        connection.rollback()
        with pytest.raises(pymysql.OperationalError):
            cursor.execute("UPDATE stock_by_warehouse SET reserved=-1")
        connection.rollback()
    mock_api(monkeypatch, [stock_row(quantity=1)])
    runner.run_etl(settings)
    assert len(business(settings)[1]) == 1  # BCN y ZERO ya no pertenecen al snapshot.
    mock_api(monkeypatch, [])
    runner.run_etl(settings)
    assert business(settings)[1] == ()
    assert all(row[4:6] == (None, "unknown") for row in business(settings)[0])


@pytest.mark.parametrize("during_publish", [False, True])
def test_failure_preserves_all_business_and_audits(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    during_publish: bool,
) -> None:
    _write(settings, [_row()])
    mock_api(monkeypatch, [stock_row()])
    runner.run_etl(settings)
    before = business(settings)
    _write(settings, [_row(precio_coste="200"), _row(sku="NEW")])
    requests = mock_api(
        monkeypatch,
        [stock_row(quantity=20), stock_row(warehouse="BCN"), stock_row(sku="NEW")],
        fail_last=not during_publish,
    )
    if during_publish:

        def fail(*_args: object) -> None:
            raise RuntimeError("fallo sintético tras escribir almacenes")

        monkeypatch.setattr(repository, "complete_run", fail)
    with pytest.raises(RuntimeError if during_publish else StockFetchError):
        runner.run_etl(settings)
    assert business(settings) == before
    assert len(requests) == (2 if during_publish else 3)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, status, phase, error_code FROM etl_runs ORDER BY started_at DESC LIMIT 1"
        )
        run_id, status, phase, code = cursor.fetchone()
        assert status == "failed"
        assert phase == ("publish" if during_publish else "extract")
        assert code == ("UNEXPECTED_ERROR" if during_publish else "STOCK_FETCH_FAILED")
        cursor.execute(
            "SELECT COUNT(*) FROM rejections WHERE run_id=%s AND reason_code=%s", (run_id, code)
        )
        assert cursor.fetchone()[0] == 1


def test_invalid_and_conflicting_observations_persist_null_with_audit(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(settings, [_row(), _row(sku="CONFLICT")])
    mock_api(
        monkeypatch,
        [
            stock_row(),
            stock_row(warehouse="BCN", quantity=-1),
            stock_row(sku="CONFLICT"),
            stock_row(sku="CONFLICT", quantity=9),
        ],
    )
    result = runner.run_etl(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT stock_total, stock_status FROM products WHERE in_catalog=1")
        assert cursor.fetchall() == ((None, "invalid"), (None, "invalid"))
        cursor.execute(
            "SELECT reason_code, action FROM rejections WHERE run_id=%s AND source='stock_api'",
            (result.run_id,),
        )
        issues = cursor.fetchall()
        assert ("INVALID_STOCK", "reject_row") in issues
        assert ("CONFLICTING_STOCK", "warn") in issues
    assert result.stock_counters.rows_read == 4
    assert result.stock_counters.rows_accepted == 1
    assert result.stock_counters.rows_rejected == 3


def test_resume_interrupted_migration(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # La fixture usa exclusivamente f4_test_* en un servidor temporal.
    _write(settings, [_row()])
    mock_api(monkeypatch, [stock_row()])
    result = runner.run_etl(settings)
    before = business(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        # Simula DDL F5 aplicado pero registro de versión aún no confirmado.
        cursor.execute("DELETE FROM schema_migrations WHERE version='002_stock'")
        connection.commit()
        assert not db.schema_is_current(connection)
        assert db.apply_migration(connection)
        assert not db.apply_migration(connection)
        assert db.schema_is_current(connection)
        cursor.execute("SELECT stock_sha256 FROM etl_runs WHERE id=%s", (result.run_id,))
        assert len(cursor.fetchone()[0]) == 64
    assert business(settings) == before
