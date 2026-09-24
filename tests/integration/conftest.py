"""MySQL temporal compartido por las regresiones F4 y la integración F5."""

import csv
import os
from pathlib import Path

import pytest

from src import db
from src.config import Settings
from src.etl.orders import HEADER


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
    # Un pedido válido sintético mantiene las regresiones F4/F5 aisladas de datos reales.
    with base.orders_csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerow(
            [
                "REGRESSION",
                "2026-01-01",
                "Cliente sintético",
                "B2B",
                "COMPLETADO",
                "PRV-001",
                "1",
                "10",
                "0",
            ]
        )
    return base
