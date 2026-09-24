"""F6: pedidos sintéticos en MySQL 8 aislado; no ejecuta la validación real F7."""

import csv
import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pymysql
import pytest
from test_products import _row, _write

from src import db
from src.config import Settings
from src.etl import repository, runner
from src.etl.orders import HEADER, OrdersReadError
from src.etl.runner import RunValidationError
from src.etl.stock_client import StockSnapshot


def order_row(**changes: str) -> list[str]:
    fields = dict(
        zip(
            HEADER,
            [
                "ORD-1",
                "2026-01-01",
                "Cliente sintético",
                "B2B",
                "COMPLETADO",
                "PRV-001",
                "2",
                "10",
                "10%",
            ],
            strict=True,
        )
    )
    fields.update(changes)
    return [fields[key] for key in HEADER]


def write_orders(settings: Settings, rows: list[list[str]]) -> None:
    with settings.orders_csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)


@pytest.fixture(autouse=True)
def stock_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "fetch_stock", lambda *_: StockSnapshot((), "0" * 64))


def business(settings: Settings) -> list[tuple]:
    with db.connect(settings) as connection, connection.cursor() as cursor:
        result = []
        for query in (
            "SELECT id,sku,in_catalog,is_historical,net_cost,pvp,stock_total FROM products ORDER BY sku",
            "SELECT id,source_order_id,order_date,customer,channel,status,has_rejected_lines FROM orders ORDER BY id",
            "SELECT id,order_id,product_id,line_key,quantity,unit_price,discount FROM order_lines ORDER BY id",
            "SELECT product_id,warehouse_code,quantity,reserved,updated_at FROM stock_by_warehouse ORDER BY product_id,warehouse_code",
        ):
            cursor.execute(query)
            result.append(cursor.fetchall())
        return result


def test_repeat_partial_historical_dedup_and_mysql_constraints(settings: Settings) -> None:
    archive_sku = f"ARCHIVE-F6-{uuid4().hex[:8]}"
    rejected_sku = f"REJECTED-F6-{uuid4().hex[:8]}"
    _write(settings, [_row(), _row(sku=rejected_sku, pvp_recomendado="0")])
    write_orders(
        settings,
        [
            order_row(),
            order_row(),
            order_row(sku=archive_sku),
            order_row(sku=rejected_sku),
            order_row(cantidad="0"),
        ],
    )
    first = runner.run_etl(settings)
    assert first.orders_counters == {
        "rows_read": 5,
        "rows_accepted": 3,
        "rows_rejected": 1,
        "rows_deduplicated": 1,
        "quality_warnings": 2,
        "discarded_fields": 0,
        "orders_loaded": 1,
        "partial_orders": 1,
        "historical_products_created": 2,
    }
    before = business(settings)
    second = runner.run_etl(settings)
    assert business(settings) == before
    assert second.orders_counters["historical_products_created"] == 0
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT in_catalog,is_historical,net_cost,pvp,stock_total,name FROM products WHERE sku=%s",
            (archive_sku.upper(),),
        )
        assert cursor.fetchone() == (0, 1, None, None, None, None)
        cursor.execute(
            "SELECT detail FROM rejections WHERE run_id=%s AND reason_code='HISTORICAL_PRODUCT_CREATED' ORDER BY entity_key",
            (first.run_id,),
        )
        details = [r[0] for r in cursor.fetchall()]
        assert any("ausente del catálogo" in value for value in details)
        assert any("rechazado en catálogo" in value for value in details)
        cursor.execute("SELECT orders_sha256,counters FROM etl_runs WHERE id=%s", (second.run_id,))
        digest, counters = cursor.fetchone()
        assert len(digest) == 64
        assert json.loads(counters)["orders_csv"]["rows_accepted"] == 3
        for query in (
            "UPDATE order_lines SET product_id=99999999",
            "UPDATE order_lines SET order_id=99999999",
            "UPDATE order_lines SET last_run_id='00000000-0000-0000-0000-000000000000'",
            "DELETE FROM orders",
            "INSERT INTO orders (source_order_id,order_date,customer,channel,status,has_rejected_lines,last_run_id) SELECT source_order_id,order_date,customer,channel,status,has_rejected_lines,last_run_id FROM orders",
            "INSERT INTO order_lines (order_id,product_id,line_key,quantity,unit_price,discount,source_locator,last_run_id) SELECT order_id,product_id,line_key,quantity,unit_price,discount,source_locator,last_run_id FROM order_lines",
        ):
            with pytest.raises(pymysql.IntegrityError):
                cursor.execute(query)
            connection.rollback()
        for query in (
            "UPDATE order_lines SET quantity=0",
            "UPDATE order_lines SET unit_price=0",
            "UPDATE order_lines SET discount=1.1",
            "UPDATE orders SET status='other'",
            "UPDATE orders SET channel='web'",
            "UPDATE orders SET has_rejected_lines=2",
        ):
            with pytest.raises(pymysql.OperationalError):
                cursor.execute(query)
            connection.rollback()


def test_correction_removes_old_line_and_missing_or_invalid_orders(settings: Settings) -> None:
    _write(settings, [_row()])
    write_orders(
        settings,
        [
            order_row(),
            order_row(precio_unitario="12"),
            order_row(id_pedido="GONE"),
            order_row(id_pedido="BAD-NOW"),
        ],
    )
    runner.run_etl(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM orders WHERE source_order_id='ORD-1'")
        original_id = cursor.fetchone()[0]
    write_orders(
        settings, [order_row(precio_unitario="20"), order_row(id_pedido="BAD-NOW", cantidad="0")]
    )
    result = runner.run_etl(settings)
    assert result.orders_counters["orders_loaded"] == 1
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id,source_order_id FROM orders")
        assert cursor.fetchall() == ((original_id, "ORD-1"),)
        cursor.execute("SELECT unit_price FROM order_lines")
        assert cursor.fetchall() == ((Decimal("20.0000"),),)


def test_historical_promotion_retirement_and_return_sign(settings: Settings) -> None:
    _write(settings, [_row()])
    write_orders(settings, [order_row(sku="HISTORY-F6", estado="DEVUELTO", cantidad="-2")])
    runner.run_etl(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM products WHERE sku='HISTORY-F6'")
        original_id = cursor.fetchone()[0]
    _write(settings, [_row(), _row(sku="HISTORY-F6")])
    runner.run_etl(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id,is_historical,net_cost FROM products WHERE sku='HISTORY-F6'")
        assert cursor.fetchone() == (original_id, 0, Decimal("85.0000"))
        cursor.execute("SELECT product_id,quantity FROM order_lines")
        assert cursor.fetchone() == (original_id, -2)
    _write(settings, [_row()])
    runner.run_etl(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id,is_historical,net_cost FROM products WHERE sku='HISTORY-F6'")
        assert cursor.fetchone() == (original_id, 1, None)


@pytest.mark.parametrize("mode", ["empty", "all_invalid", "header", "changed", "publish"])
def test_failure_preserves_previous_business_and_audits(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    _write(settings, [_row()])
    write_orders(settings, [order_row()])
    runner.run_etl(settings)
    before = business(settings)
    _write(settings, [_row(precio_coste="200")])
    write_orders(settings, [order_row(sku="NEVER-PUBLISH")])
    code, error_type = "UNEXPECTED_ERROR", RuntimeError
    if mode == "empty":
        write_orders(settings, [])
        code, error_type = "EMPTY_ORDERS", RunValidationError
    elif mode == "all_invalid":
        write_orders(settings, [order_row(cantidad="0")])
        code, error_type = "EMPTY_ORDERS", RunValidationError
    elif mode == "header":
        settings.orders_csv_path.write_text("invalid,header\n")
        code, error_type = "INVALID_HEADER", OrdersReadError
    elif mode == "changed":
        original = runner.extract_orders

        def modify(path: Path):
            result = original(path)
            with path.open("a") as stream:
                stream.write("\n")
            return result

        monkeypatch.setattr(runner, "extract_orders", modify)
        code, error_type = "SOURCE_CHANGED", RunValidationError
    else:

        def fail(*_args: object) -> None:
            raise RuntimeError("fallo sintético después de publicar pedidos")

        monkeypatch.setattr(repository, "complete_run", fail)
    with pytest.raises(error_type):
        runner.run_etl(settings)
    assert business(settings) == before
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id,status,error_code FROM etl_runs ORDER BY started_at DESC LIMIT 1")
        run_id, status, actual_code = cursor.fetchone()
        assert (status, actual_code) == ("failed", code)
        cursor.execute(
            "SELECT COUNT(*) FROM rejections WHERE run_id=%s AND reason_code=%s", (run_id, code)
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku='NEVER-PUBLISH'")
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT COUNT(*) FROM rejections WHERE run_id=%s AND reason_code='HISTORICAL_PRODUCT_CREATED'",
            (run_id,),
        )
        assert cursor.fetchone()[0] == 0  # No afirmar una creación que se revirtió.


def test_resume_orders_migration_preserves_data(settings: Settings) -> None:
    _write(settings, [_row()])
    write_orders(settings, [order_row()])
    runner.run_etl(settings)
    before = business(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("DELETE FROM schema_migrations WHERE version='003_orders'")
        connection.commit()
        assert not db.schema_is_current(connection)
        assert db.apply_migration(connection)
        assert not db.apply_migration(connection)
    assert business(settings) == before
