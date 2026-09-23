"""F4 contra MySQL 8 aislado; todos los CSV/XML de este módulo son sintéticos."""

import csv
import os
from decimal import Decimal
from pathlib import Path

import pymysql
import pytest

from src import db
from src.config import Settings
from src.etl import repository, runner
from src.etl.catalog import HEADER
from src.etl.pricing import TariffReadError, Tariffs
from src.etl.runner import LOCK_NAME, RunValidationError, run_catalog_pricing


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    port = os.environ.get("F4_TEST_DB_PORT")
    if not port:
        pytest.skip("F4_TEST_DB_PORT: requiere MySQL 8 de pruebas aislado")
    base = Settings(
        db_host=os.environ.get("F4_TEST_DB_HOST", "127.0.0.1"),
        db_port=int(port),
        db_name=os.environ.get("F4_TEST_DB_NAME", "f4_test_catalog"),
        db_user=os.environ.get("F4_TEST_DB_USER", "f4_tester"),
        db_password=os.environ["F4_TEST_DB_PASSWORD"],
        stock_api_url="http://127.0.0.1:1",
        stock_api_token="unused",
        csv_path=tmp_path / "catalog.csv",
        xml_path=tmp_path / "tariffs.xml",
        orders_csv_path=tmp_path / "unused.csv",
        business_timezone="Europe/Madrid",
        log_level="ERROR",
    )
    if not base.db_name.startswith("f4_test_"):
        raise ValueError("Las pruebas F4 requieren una base f4_test_* aislada")
    with db.connect(base) as connection:
        db.apply_migration(connection)
    return base


def _row(**changes: str) -> list[str]:
    fields = dict(
        zip(
            HEADER,
            [
                "PRV-001",
                "N/D",
                "Producto sintético",
                "Marca Prueba",
                "Ejemplo",
                "100",
                "120",
                "21",
                "0",
                "2025-04-01",
                "N/D",
            ],
            strict=True,
        )
    )
    fields.update(changes)
    return [fields[key] for key in HEADER]


def _write(settings: Settings, rows: list[list[str]], xml: str | None = None) -> None:
    with settings.csv_path.open("w", encoding="latin-1", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(HEADER)
        writer.writerows(rows)
    settings.xml_path.write_text(
        xml
        or '<TarifasProveedor><Descuentos><Descuento tipo="categoria" valor="Ejemplo">'
        '<PorcentajeBase>10%</PorcentajeBase><PorVolumen minimo="5">2%</PorVolumen>'
        '</Descuento><Descuento tipo="marca" valor="Marca Prueba">'
        "<PorcentajeBase>5</PorcentajeBase></Descuento></Descuentos><Excepciones>"
        '<Producto sku="EX-001"><PrecioNetoAcordado>42.22</PrecioNetoAcordado>'
        "</Producto></Excepciones></TarifasProveedor>",
        encoding="utf-8",
    )


def _business(settings: Settings) -> list[tuple[object, ...]]:
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT sku, net_cost, pvp, stock_total, stock_status, in_catalog, "
            "is_historical FROM products WHERE in_catalog = 1 ORDER BY sku"
        )
        return list(cursor.fetchall())


def _run_status(settings: Settings, run_id: str) -> tuple[object, ...]:
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, error_code, JSON_EXTRACT(counters, '$.catalog_csv.rows_read') "
            "FROM etl_runs WHERE id = %s",
            (run_id,),
        )
        return cursor.fetchone()


def test_migration_repeat_load_audit_and_mysql_constraints(settings: Settings) -> None:
    rows = [
        _row(),
        _row(),
        _row(sku="BAD-001", pvp_recomendado="0"),
        _row(sku="EX-001", precio_coste="N/D"),
    ]
    _write(settings, rows)
    with db.connect(settings) as connection:
        assert db.apply_migration(connection) is False
    first = run_catalog_pricing(settings)
    assert first.counters.as_dict() == {
        "rows_read": 4,
        "rows_accepted": 2,
        "rows_rejected": 1,
        "rows_deduplicated": 1,
        "quality_warnings": 1,
        "discarded_fields": 1,
        "products_loaded": 2,
    }
    before = _business(settings)
    assert any(row[:3] == ("PRV-001", Decimal("85.0000"), Decimal("120.0000")) for row in before)
    assert any(row[:3] == ("EX-001", Decimal("42.2200"), Decimal("120.0000")) for row in before)
    assert all(row[3:5] == (None, "unknown") for row in before)
    second = run_catalog_pricing(settings)
    assert _business(settings) == before
    assert second.run_id != first.run_id
    assert _run_status(settings, second.run_id) == ("completed", None, "4")
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM products WHERE sku IN ('PRV-001', 'EX-001')")
        assert cursor.fetchone()[0] == 2
        cursor.execute(
            "SELECT action, reason_code, record_locator FROM rejections "
            "WHERE run_id = %s ORDER BY id",
            (first.run_id,),
        )
        issues = cursor.fetchall()
        assert ("reject_row", "NON_POSITIVE_PRICE", "4") in issues
        assert ("deduplicate", "EXACT_DUPLICATE", "3") in issues
        assert any(row[0] == "warn" and row[1] == "UNAPPLIED_TARIFF_TERM" for row in issues)
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute(
                "INSERT INTO products (sku, name, brand, category, net_cost, pvp, last_run_id) "
                "VALUES (%s, 'Otro', 'M', 'C', 1, 2, %s)",
                ("PRV-001", first.run_id),
            )
        connection.rollback()
        with pytest.raises(pymysql.OperationalError):
            cursor.execute("UPDATE products SET net_cost = -1 WHERE sku = 'PRV-001'")
        connection.rollback()
        with pytest.raises(pymysql.OperationalError):
            cursor.execute("UPDATE products SET net_cost = NULL WHERE sku = 'PRV-001'")
        connection.rollback()
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute(
                "INSERT INTO products (sku, name, brand, category, net_cost, pvp, last_run_id) "
                "VALUES ('NO-RUN', 'Otro', 'M', 'C', 1, 2, %s)",
                ("00000000-0000-0000-0000-000000000000",),
            )
        connection.rollback()
        with pytest.raises(pymysql.OperationalError):
            cursor.execute("UPDATE products SET stock_total = 0 WHERE sku = 'PRV-001'")
        connection.rollback()
        with pytest.raises(pymysql.OperationalError):
            cursor.execute(
                "UPDATE products SET stock_status = 'known', stock_as_of = UTC_TIMESTAMP(6) "
                "WHERE sku = 'PRV-001'"
            )
        connection.rollback()


def test_retire_absent_and_promote_same_sku(settings: Settings) -> None:
    _write(settings, [_row(), _row(sku="EX-001")])
    run_catalog_pricing(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM products WHERE sku = 'EX-001'")
        original_id = cursor.fetchone()[0]
    _write(settings, [_row()])
    run_catalog_pricing(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, in_catalog, is_historical, net_cost, pvp, stock_total "
            "FROM products WHERE sku = 'EX-001'"
        )
        assert cursor.fetchone() == (original_id, 0, 1, None, None, None)
    _write(settings, [_row(), _row(sku="EX-001")])
    run_catalog_pricing(settings)
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, in_catalog, is_historical, net_cost FROM products WHERE sku='EX-001'"
        )
        assert cursor.fetchone() == (original_id, 1, 0, Decimal("42.2200"))


def test_forced_publish_failure_rolls_back_and_audits(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(settings, [_row()])
    run_catalog_pricing(settings)
    before = _business(settings)
    _write(settings, [_row(precio_coste="200"), _row(sku="NEW-001")])

    def fail(*_args: object) -> None:
        raise RuntimeError("fallo sintético después de escribir productos")

    monkeypatch.setattr(repository, "complete_run", fail)
    with pytest.raises(RuntimeError, match="fallo sintético"):
        run_catalog_pricing(settings)
    assert _business(settings) == before
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, status, phase, error_code, csv_sha256, xml_sha256 "
            "FROM etl_runs ORDER BY started_at DESC LIMIT 1"
        )
        failed_id, status, phase, error_code, csv_hash, xml_hash = cursor.fetchone()
        assert (status, phase, error_code) == ("failed", "publish", "UNEXPECTED_ERROR")
        assert len(csv_hash) == len(xml_hash) == 64
        cursor.execute("SELECT reason_code FROM rejections WHERE run_id = %s", (failed_id,))
        assert ("UNEXPECTED_ERROR",) in cursor.fetchall()


def test_empty_snapshot_keeps_previous_business_state(settings: Settings) -> None:
    _write(settings, [_row()])
    run_catalog_pricing(settings)
    before = _business(settings)
    _write(settings, [])
    with pytest.raises(RunValidationError, match="EMPTY_CATALOG"):
        run_catalog_pricing(settings)
    assert _business(settings) == before
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT status, error_code FROM etl_runs ORDER BY started_at DESC LIMIT 1")
        assert cursor.fetchone() == ("failed", "EMPTY_CATALOG")


def test_conflicting_tariff_audited_without_publication(settings: Settings) -> None:
    _write(settings, [_row()])
    run_catalog_pricing(settings)
    before = _business(settings)
    _write(
        settings,
        [_row(precio_coste="200")],
        "<TarifasProveedor><Descuentos>"
        '<Descuento tipo="categoria" valor="Ejemplo"><PorcentajeBase>10%</PorcentajeBase></Descuento>'
        '<Descuento tipo="categoria" valor="Ejemplo"><PorcentajeBase>20%</PorcentajeBase></Descuento>'
        "</Descuentos><Excepciones/></TarifasProveedor>",
    )
    with pytest.raises(TariffReadError):
        run_catalog_pricing(settings)
    assert _business(settings) == before
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, status, error_code FROM etl_runs ORDER BY started_at DESC LIMIT 1"
        )
        failed_id, status, error_code = cursor.fetchone()
        assert (status, error_code) == ("failed", "CONFLICTING_TARIFF")
        cursor.execute("SELECT source, reason_code FROM rejections WHERE run_id = %s", (failed_id,))
        assert cursor.fetchall() == (("tariffs_xml", "CONFLICTING_TARIFF"),)


def test_concurrent_writer_is_rejected_before_run_is_created(settings: Settings) -> None:
    _write(settings, [_row()])
    with db.connect(settings) as blocker, blocker.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", (LOCK_NAME,))
        assert cursor.fetchone()[0] == 1
        with pytest.raises(RuntimeError, match="Ya hay una carga"):
            run_catalog_pricing(settings)
        cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
    run_catalog_pricing(settings)


def test_changed_source_aborts_before_publish(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(settings, [_row()])
    run_catalog_pricing(settings)
    before = _business(settings)
    original = runner.load_tariffs

    def edit_csv_during_extraction(path: Path) -> Tariffs:
        with settings.csv_path.open("a", encoding="latin-1") as stream:
            stream.write("\n")
        return original(path)

    monkeypatch.setattr(runner, "load_tariffs", edit_csv_during_extraction)
    with pytest.raises(RunValidationError, match="SOURCE_CHANGED"):
        run_catalog_pricing(settings)
    assert _business(settings) == before
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT status, error_code FROM etl_runs ORDER BY started_at DESC LIMIT 1")
        assert cursor.fetchone() == ("failed", "SOURCE_CHANGED")
