"""F7: cuatro fuentes sintéticas congeladas; persistencia y transacciones en MySQL 8."""

import csv
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pymysql
import pytest
from etl_checks import assert_counters, assert_integrity, business_snapshot, snapshot_hash
from test_products import _row, _write
from test_stock_persistence import mock_api, stock_row

from src import db
from src.config import Settings
from src.etl import repository, runner
from src.etl.orders import HEADER
from src.etl.stock_client import StockFetchError, StockSnapshot


def write_orders(settings: Settings, rows: list[list[str]]) -> None:
    with settings.orders_csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)


def order_row(
    order_id: str = "E2E-1",
    sku: str = "PRV-001",
    quantity: str = "2,0",
    price: str = "20",
    discount: str = "10%",
    status: str = "completado",
    customer: str = "Cliente sintético",
) -> list[str]:
    return [
        order_id,
        "01/04/2025",
        customer,
        "b2b",
        status,
        sku,
        quantity,
        price,
        discount,
    ]


def test_four_sources_reconcile_repeat_and_trace(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # SKU nuevo en cada invocación para no depender de históricos de otros tests.
    historical = "E2E-H-" + uuid4().hex[:8].upper()
    _write(
        settings,
        [
            _row(),
            _row(sku="EX-001", precio_coste="N/D"),
            _row(sku="ZERO"),
            _row(sku="ABSENT"),
            _row(),
            _row(sku="E2E-BAD", nombre="", pvp_recomendado="0"),
        ],
    )
    write_orders(
        settings,
        [
            order_row(),
            order_row(),
            order_row(
                sku="EX-001", quantity="1", price="30", discount="", customer="CLIENTE SINTÉTICO"
            ),
            order_row(sku="E2E-BAD", quantity="0"),
            order_row("E2E-2", historical),
            order_row("E2E-3", quantity="-1", status="DEVUELTO"),
            order_row("E2E-4", sku="E2E-NEVER", quantity="2,5"),
        ],
    )
    requests = mock_api(
        monkeypatch,
        [
            stock_row(),
            stock_row(warehouse="BCN", quantity=7, reserved=9),
            stock_row(),
            stock_row(sku="ZERO", quantity=0, reserved=0),
            stock_row(sku="E2E-STOCK-ONLY"),
            stock_row(sku="EX-001", quantity=3),
            stock_row(sku="EX-001", warehouse="BCN", quantity=-1),
        ],
    )
    first = runner.run_etl(settings)
    counts = assert_counters(settings, first.run_id)
    expected = {"catalog_csv": (6, 4, 1, 1), "orders_csv": (7, 4, 2, 1), "stock_api": (7, 4, 2, 1)}
    for source, numbers in expected.items():
        assert (
            tuple(
                counts[source][key]
                for key in ("rows_read", "rows_accepted", "rows_rejected", "rows_deduplicated")
            )
            == numbers
        )
    assert counts["orders_csv"]["historical_products_created"] == 1
    assert counts["orders_csv"]["quality_warnings"] == 2
    assert_integrity(settings)
    before = business_snapshot(settings)
    second = runner.run_etl(settings)
    after = business_snapshot(settings)
    assert after == before
    assert snapshot_hash(after) == snapshot_hash(before)
    assert len(requests) == 8  # Cuatro páginas completas por ejecución.
    repeated = assert_counters(settings, second.run_id)
    assert repeated["orders_csv"]["historical_products_created"] == 0
    assert repeated["orders_csv"]["quality_warnings"] == 1
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT sku, net_cost, stock_total, stock_status FROM products "
            "WHERE in_catalog=1 ORDER BY sku"
        )
        assert cursor.fetchall() == (
            ("ABSENT", Decimal("85.0000"), None, "unknown"),
            ("EX-001", Decimal("42.2200"), None, "invalid"),
            ("PRV-001", Decimal("85.0000"), 12, "known"),
            ("ZERO", Decimal("85.0000"), 0, "known"),
        )
        cursor.execute(
            "SELECT o.source_order_id, o.order_date, o.status, o.has_rejected_lines, p.sku, "
            "l.quantity, l.unit_price, l.discount, l.source_locator FROM order_lines l "
            "JOIN orders o ON o.id=l.order_id JOIN products p ON p.id=l.product_id "
            "ORDER BY o.source_order_id, p.sku"
        )
        assert cursor.fetchall() == (
            (
                "E2E-1",
                date(2025, 4, 1),
                "COMPLETADO",
                1,
                "EX-001",
                1,
                Decimal("30"),
                Decimal("0"),
                "4",
            ),
            (
                "E2E-1",
                date(2025, 4, 1),
                "COMPLETADO",
                1,
                "PRV-001",
                2,
                Decimal("20"),
                Decimal("0.1"),
                "2",
            ),
            (
                "E2E-2",
                date(2025, 4, 1),
                "COMPLETADO",
                0,
                historical,
                2,
                Decimal("20"),
                Decimal("0.1"),
                "6",
            ),
            (
                "E2E-3",
                date(2025, 4, 1),
                "DEVUELTO",
                0,
                "PRV-001",
                -1,
                Decimal("20"),
                Decimal("0.1"),
                "7",
            ),
        )
        cursor.execute(
            "SELECT COUNT(*) FROM products WHERE sku IN ('E2E-BAD','E2E-NEVER','E2E-STOCK-ONLY')"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT reason_code FROM rejections WHERE run_id=%s AND source='catalog_csv' "
            "AND record_locator='7' AND action='reject_row' ORDER BY reason_code",
            (first.run_id,),
        )
        assert cursor.fetchall() == (("MISSING_REQUIRED_FIELD",), ("NON_POSITIVE_PRICE",))
        cursor.execute(
            "SELECT csv_sha256, xml_sha256, stock_sha256, orders_sha256, rules_version "
            "FROM etl_runs WHERE id IN (%s,%s)",
            (first.run_id, second.run_id),
        )
        hashes = cursor.fetchall()
        assert len(hashes) == 2 and hashes[0] == hashes[1]
        assert all(len(value) == 64 for value in hashes[0][:4])
        cursor.execute(
            "SELECT COUNT(*) FROM rejections WHERE run_id=%s AND reason_code<>'HISTORICAL_PRODUCT_CREATED'",
            (first.run_id,),
        )
        expected_repeated = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM rejections WHERE run_id=%s", (second.run_id,))
        assert cursor.fetchone()[0] == expected_repeated > 0


def test_duplicates_only_never_count_as_rejected_rows(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(
        settings,
        [_row(), _row()],
        "<TarifasProveedor><Descuentos/><Excepciones/></TarifasProveedor>",
    )
    write_orders(settings, [order_row(), order_row()])
    mock_api(monkeypatch, [stock_row(), stock_row()])
    result = runner.run_etl(settings)
    counts = assert_counters(settings, result.run_id)
    for source in counts.values():
        assert (source["rows_read"], source["rows_accepted"], source["rows_deduplicated"]) == (
            2,
            1,
            1,
        )
        assert (
            source["rows_rejected"] == source["quality_warnings"] == source["discarded_fields"] == 0
        )
    assert_integrity(settings)


@pytest.mark.parametrize("failure", ["last_page", "mysql"])
def test_failure_keeps_all_four_business_tables_and_durable_audit(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    _write(settings, [_row()])
    write_orders(settings, [order_row()])
    mock_api(monkeypatch, [stock_row()])
    initial = runner.run_etl(settings)
    before = business_snapshot(settings)
    # Cambiar catálogo, tarifas, pedidos y stock, incluidos un histórico y una firma nuevos.
    _write(
        settings,
        [_row(precio_coste="200")],
        "<TarifasProveedor><Descuentos/><Excepciones/></TarifasProveedor>",
    )
    historical = "E2E-ROLLBACK-" + uuid4().hex[:8].upper()
    write_orders(settings, [order_row(price="40"), order_row("E2E-NEW", historical)])
    requests = mock_api(
        monkeypatch,
        [stock_row(quantity=20), stock_row(warehouse="BCN"), stock_row(warehouse="SEV")],
        fail_last=failure == "last_page",
    )
    if failure == "mysql":

        def fail(connection: pymysql.Connection, *_args: object) -> None:
            # Otro lector ve la versión anterior aun después de escribir las cuatro tablas.
            assert business_snapshot(settings) == before
            with connection.cursor() as cursor:
                cursor.execute("SELECT unit_price FROM order_lines WHERE source_locator='2'")
                assert cursor.fetchone()[0] == Decimal("40")
                # Fallo real de FK dentro de la transacción (sin desactivar restricciones).
                cursor.execute(
                    "UPDATE order_lines SET last_run_id='00000000-0000-0000-0000-000000000000'"
                )

        monkeypatch.setattr(repository, "complete_run", fail)
    with pytest.raises(pymysql.IntegrityError if failure == "mysql" else StockFetchError):
        runner.run_etl(settings)
    assert business_snapshot(settings) == before
    assert len(requests) == (2 if failure == "mysql" else 3)
    assert_integrity(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, status, phase, error_code FROM etl_runs ORDER BY started_at DESC LIMIT 1"
        )
        failed_id, status, phase, code = cursor.fetchone()
        assert failed_id != initial.run_id
        assert (status, phase, code) == (
            "failed",
            "publish" if failure == "mysql" else "extract",
            "DATABASE_ERROR" if failure == "mysql" else "STOCK_FETCH_FAILED",
        )
        cursor.execute(
            "SELECT reason_code FROM rejections WHERE run_id=%s AND action='fail_run'", (failed_id,)
        )
        assert cursor.fetchall() == ((code,),)
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku=%s", (historical,))
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT COUNT(*) FROM rejections WHERE run_id=%s AND reason_code='HISTORICAL_PRODUCT_CREATED'",
            (failed_id,),
        )
        assert cursor.fetchone()[0] == 0


def test_second_writer_cannot_start_while_first_extracts(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(settings, [_row()])
    write_orders(settings, [order_row()])
    mock_api(monkeypatch, [stock_row()])
    initial = runner.run_etl(settings)
    before = business_snapshot(settings)
    fetch = runner.fetch_stock

    def during_extraction(config: Settings, run_id: str) -> StockSnapshot:
        assert run_id != initial.run_id
        with db.connect(settings) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM etl_runs")
            count = cursor.fetchone()[0]
        with pytest.raises(RuntimeError, match="Ya hay una carga"):
            runner.run_etl(settings)
        with db.connect(settings) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM etl_runs")
            assert cursor.fetchone()[0] == count
        assert business_snapshot(settings) == before
        return fetch(config, run_id)

    monkeypatch.setattr(runner, "fetch_stock", during_extraction)
    completed = runner.run_etl(settings)
    assert_counters(settings, completed.run_id)
    assert business_snapshot(settings) == before
    # Una vez liberado el lock, la siguiente ejecución sí puede completar.
    monkeypatch.setattr(runner, "fetch_stock", fetch)
    assert_counters(settings, runner.run_etl(settings).run_id)
