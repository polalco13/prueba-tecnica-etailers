"""F9: HTTP/HTML real con SQL en MySQL aislado y datos únicamente sintéticos."""

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pymysql
import pytest
from fastapi.testclient import TestClient
from test_analytics import SyntheticSales
from test_analytics import sales_db as sales_db

from src.analytics import AnalyticsQueries
from src.config import Settings
from src.web import app as web


@pytest.fixture
def client(
    sales_db: SyntheticSales, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    # Las peticiones de prueba son secuenciales y ven la misma transacción sintética.
    @contextmanager
    def connection(_: Settings) -> Iterator:
        yield sales_db.connection

    monkeypatch.setattr(web.db, "connect", connection)
    with TestClient(web.create_app(settings, date(2026, 9, 25))) as test_client:
        yield test_client


def test_catalog_combines_search_category_and_pagination(
    client: TestClient, sales_db: SyntheticSales
) -> None:
    for index in range(23):
        product = sales_db.product(
            f"SKU-{index:02d}", category="Herramientas" if index < 21 else "Jardín"
        )
        with sales_db.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE products SET name = %s, description = %s WHERE id = %s",
                (f"Pieza {index}", "Uso exterior", product),
            )
    sales_db.product("HISTORICO", historical=True)
    first = client.get("/", params={"q": "pieza", "category": "herramientas"})
    assert first.status_code == 200
    catalog = first.context["catalog"]
    assert (catalog.total, catalog.page, catalog.pages) == (21, 1, 2)
    assert [p.sku for p in catalog.products] == [f"SKU-{i:02d}" for i in range(20)]
    assert "q=pieza&amp;category=herramientas&amp;page=2#catalogo" in first.text
    second = client.get("/", params={"q": "pieza", "category": "herramientas", "page": 2})
    assert [p.sku for p in second.context["catalog"].products] == ["SKU-20"]
    assert client.get("/?page=999").context["catalog"].page == 2
    assert client.get("/?q=sku-02").context["catalog"].total == 1
    assert client.get("/?q=exterior&category=jardín").context["catalog"].total == 2
    assert "HISTORICO" not in first.text
    assert client.get("/?page=0").status_code == 422
    assert client.get("/", params={"q": "x" * 201}).status_code == 422


def test_search_is_literal_and_sql_values_are_bound(
    client: TestClient, sales_db: SyntheticSales
) -> None:
    special = sales_db.product("WITH_PERCENT")
    sales_db.product("NORMAL")
    with sales_db.connection.cursor() as cursor:
        cursor.execute("UPDATE products SET name = %s WHERE id = %s", ("Oferta 100%!", special))
    for search in ("%", "_", "!", "100%!"):
        response = client.get("/", params={"q": search})
        assert [p.sku for p in response.context["catalog"].products] == ["WITH_PERCENT"]
    for params in ({"q": "' OR 1=1 --"}, {"category": "' OR 1=1 --"}):
        response = client.get("/", params=params)
        assert response.status_code == 200
        assert response.context["catalog"].total == 0
        assert "No hay productos que coincidan" in response.text
    assert client.get("/").context["catalog"].total == 2


def test_html_escapes_source_and_filter_text(client: TestClient, sales_db: SyntheticSales) -> None:
    product = sales_db.product("SAFE")
    payload = '<script>alert("synthetic")</script>'
    with sales_db.connection.cursor() as cursor:
        cursor.execute("UPDATE products SET name = %s WHERE id = %s", (payload, product))
    response = client.get("/", params={"q": payload})
    assert response.context["catalog"].total == 1
    assert payload not in response.text
    assert "&lt;script&gt;" in response.text
    assert response.text.count('id="chart-data"') == 1


def test_dashboard_values_match_sql_and_explain_unknowns(
    client: TestClient, sales_db: SyntheticSales
) -> None:
    product = sales_db.product("SOLD", stock=0)
    historical = sales_db.product("OLD", historical=True)
    sales_db.product("UNKNOWN", stock=None)
    order = sales_db.order(date(2026, 9, 25), partial=True)
    sales_db.line(order, product, quantity=2, discount="0.1")
    sales_db.line(order, historical, price="5")
    pending = sales_db.order(date(2026, 9, 25), status="PENDIENTE")
    sales_db.line(pending, product, price="100")
    with sales_db.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE etl_runs SET finished_at = %s WHERE id = %s",
            ("2026-09-25 10:00:00", sales_db.run_id),
        )
        cursor.execute(
            "INSERT INTO rejections (run_id, source, record_locator, entity_key, "
            "reason_code, action, severity, detail) VALUES "
            "(%s, 'catalog_csv', '2', 'SOLD', 'CONFLICTING_PRODUCT_SKU', "
            "'reject_row', 'error', 'Fixture sintética')",
            (sales_db.run_id,),
        )
    response = client.get("/")
    assert response.status_code == 200
    queries = AnalyticsQueries(sales_db.connection, date(2026, 9, 25))
    assert response.context["summary"] == queries.sales_summary()
    assert response.context["summary"].revenue == Decimal("23.00")
    for key, query in (
        ("monthly", queries.monthly_sales),
        ("channels", queries.sales_by_channel),
        ("categories", queries.sales_by_category),
        ("top_products", queries.top_products),
        ("margin", queries.margin_summary),
        ("low_stock", queries.low_stock_products),
    ):
        assert response.context[key] == query()
    assert 'id="revenue" data-value="23.00">23,00' in response.text
    assert 'data-value="4.00">4,00' in response.text
    assert "78,26 %" in response.text
    assert "1 con líneas rechazadas" in response.text
    assert "Histórico" in response.text and "Sin categoría" in response.text
    assert "Desconocido" in response.text
    assert "25/09/2026 10:00 UTC" in response.text
    assert "Costes por revisar" in response.text and "SOLD" in response.text
    assert "Moneda EUR y base fiscal (IVA) pendientes de confirmar" in response.text
    assert 'class="badge low">0</span>' in response.text
    payload = json.loads(
        re.search(r'<script id="chart-data"[^>]*>(.*?)</script>', response.text).group(1)
    )
    assert len(payload["labels"]) == 18
    assert payload["revenue"] == ["0.00"] * 17 + ["23.00"]
    assert payload["units"] == [0] * 17 + [3]
    # El catálogo puede no tener resultados sin vaciar las estadísticas generales.
    filtered = client.get("/?q=no-match")
    assert filtered.context["catalog"].total == 0
    assert filtered.context["summary"] == response.context["summary"]


def test_empty_database_shows_empty_states(client: TestClient, sales_db: SyntheticSales) -> None:
    with sales_db.connection.cursor() as cursor:
        cursor.execute("DELETE FROM etl_runs WHERE id = %s", (sales_db.run_id,))
    response = client.get("/")
    assert response.status_code == 200
    assert "Todavía no hay una carga completada" in response.text
    assert "No hay ventas elegibles" in response.text
    assert "Sin dato" in response.text
    assert "Sin ventas por categoría" in response.text
    assert "No hay productos que cumplan" in response.text
    assert response.context["margin"].coverage is None


def test_failed_run_does_not_replace_publication_or_hide_negative_margin(
    client: TestClient, sales_db: SyntheticSales
) -> None:
    product = sales_db.product("UNCERTAIN", cost="20", stock=None)
    sales_db.line(sales_db.order(date(2026, 9, 24)), product)
    with sales_db.connection.cursor() as cursor:
        cursor.execute("UPDATE products SET stock_status = 'invalid' WHERE id = %s", (product,))
        cursor.execute(
            "UPDATE etl_runs SET finished_at = '2026-09-24 10:00:00' WHERE id = %s",
            (sales_db.run_id,),
        )
        cursor.execute(
            "INSERT INTO etl_runs (id, status, phase, rules_version, started_at, finished_at) "
            "VALUES ('synthetic-failed', 'failed', 'extract', 'synthetic', "
            "'2026-09-25 10:00:00', '2026-09-25 10:01:00')"
        )
        cursor.execute(
            "INSERT INTO rejections (run_id, source, record_locator, entity_key, "
            "reason_code, action, severity, detail) VALUES "
            "('synthetic-failed', 'catalog_csv', '2', 'UNCERTAIN', "
            "'CONFLICTING_PRODUCT_SKU', 'reject_row', 'error', 'Fixture sintética')"
        )
    response = client.get("/")
    assert response.context["publication"].run_id == sales_db.run_id
    assert "24/09/2026 10:00 UTC" in response.text
    assert "Costes por revisar" not in response.text
    assert 'class="negative" data-value="-10.00">-10,00' in response.text
    assert "Dato inválido" in response.text
    assert response.context["low_stock"] == []


def test_db_error_is_503_without_sensitive_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_: Settings) -> None:
        raise pymysql.OperationalError(2003, "synthetic-password-do-not-display")

    monkeypatch.setattr(web.db, "connect", unavailable)
    response = client.get("/")
    assert response.status_code == 503
    assert "No se pudo cargar el panel" in response.text
    assert "synthetic-password" not in response.text
    assert 'id="revenue"' not in response.text


def test_missing_schema_has_actionable_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web.db, "schema_is_current", lambda _: False)
    response = client.get("/")
    assert response.status_code == 503
    assert "Aplica las migraciones documentadas" in response.text


def test_assets_are_local_and_page_is_read_only(client: TestClient) -> None:
    for path in ("styles.css", "dashboard.js", "vendor/chart.umd.min.js"):
        assert client.get(f"/static/{path}").status_code == 200
    assert "v4.5.1" in client.get("/static/vendor/chart.umd.min.js").text[:300]
    assert client.post("/").status_code == 405
