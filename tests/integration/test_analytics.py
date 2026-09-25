"""F8: resultados esperados calculados a mano sobre MySQL 8 aislado.

Las filas de esta suite son sintéticas y se revierten al terminar cada prueba.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pymysql.connections import Connection

from src import db
from src.analytics.queries import AnalyticsQueries, months_before
from src.config import Settings


@dataclass
class SyntheticSales:
    connection: Connection
    run_id: str
    sequence: int = 0

    def product(
        self,
        sku: str,
        *,
        category: str | None = "Herramientas",
        cost: str | None = "7.0000",
        stock: int | None = None,
        historical: bool = False,
    ) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO products
                    (sku, name, brand, category, category_key, net_cost, pvp, is_historical,
                     in_catalog, stock_total, stock_status, stock_as_of, last_run_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sku,
                    None if historical else f"Producto {sku}",
                    None if historical else "Marca sintética",
                    None if historical else category,
                    None if historical or category is None else category.casefold(),
                    None if historical else Decimal(cost or "7.0000"),
                    None if historical else Decimal("30.0000"),
                    historical,
                    not historical,
                    None if historical else stock,
                    "known" if stock is not None and not historical else "unknown",
                    datetime(2026, 1, 1) if stock is not None and not historical else None,
                    self.run_id,
                ),
            )
            return int(cursor.lastrowid)

    def order(
        self,
        day: date,
        *,
        channel: str = "B2B",
        status: str = "COMPLETADO",
        partial: bool = False,
    ) -> int:
        self.sequence += 1
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO orders
                    (source_order_id, order_date, channel, status,
                     has_rejected_lines, last_run_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (f"F8-SYNTH-{self.sequence}", day, channel, status, partial, self.run_id),
            )
            return int(cursor.lastrowid)

    def line(
        self,
        order_id: int,
        product_id: int,
        *,
        quantity: int = 1,
        price: str = "10.0000",
        discount: str = "0.000000",
    ) -> None:
        self.sequence += 1
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO order_lines
                    (order_id, product_id, line_key, quantity, unit_price,
                     discount, source_locator, last_run_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    product_id,
                    f"{self.sequence:064x}",
                    quantity,
                    Decimal(price),
                    Decimal(discount),
                    f"synthetic:{self.sequence}",
                    self.run_id,
                ),
            )

    def warehouse(self, product_id: int, code: str, quantity: int) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stock_by_warehouse
                    (product_id, warehouse_code, quantity, reserved, updated_at, last_run_id)
                VALUES (%s, %s, %s, 0, %s, %s)
                """,
                (product_id, code, quantity, datetime(2026, 1, 1), self.run_id),
            )


@pytest.fixture
def sales_db(settings: Settings) -> Iterator[SyntheticSales]:
    """Vacía solo la vista transaccional de la BD de tests; rollback restaura todo."""

    with db.connect(settings) as connection:
        with connection.cursor() as cursor:
            for table in (
                "rejections",
                "stock_by_warehouse",
                "order_lines",
                "orders",
                "products",
                "etl_runs",
            ):
                cursor.execute(f"DELETE FROM {table}")
            run_id = str(uuid4())
            cursor.execute(
                "INSERT INTO etl_runs (id, status, phase, rules_version) "
                "VALUES (%s, 'completed', 'publish', 'synthetic-f8')",
                (run_id,),
            )
        try:
            yield SyntheticSales(connection, run_id)
        finally:
            connection.rollback()


def test_reconciled_sales_margin_stock_and_exclusions(sales_db: SyntheticSales) -> None:
    a = sales_db.product("A", cost="7.0000", stock=0)
    b = sales_db.product("B", cost="20.0000", stock=4)
    historical = sales_db.product("H", historical=True)
    unknown_stock = sales_db.product("U", cost="10.0000", stock=None)
    five_stock = sales_db.product("F", cost="10.0000", stock=5)
    sales_db.warehouse(a, "MAD", 0)
    sales_db.warehouse(a, "BCN", 0)
    sales_db.warehouse(b, "MAD", 4)

    april = sales_db.order(date(2025, 4, 1), partial=True)
    sales_db.line(april, a, quantity=2, discount="0.100000")  # 18.00; coste 14.00
    sales_db.line(april, b)  # 10.00; coste 20.00
    february = sales_db.order(date(2026, 2, 28), channel="B2C")
    sales_db.line(february, a)  # 10.00; coste 7.00
    may = sales_db.order(date(2026, 5, 31))
    sales_db.line(may, b)  # 10.00; coste 20.00
    sales_db.line(may, historical, price="5.0000")  # 5.00; coste desconocido
    sales_db.line(may, unknown_stock)  # 10.00; stock desconocido
    sales_db.line(may, five_stock)  # 10.00; no bajo mínimos

    for status, quantity in (("CANCELADO", 1), ("PENDIENTE", 1), ("DEVUELTO", -1)):
        excluded = sales_db.order(date(2026, 5, 31), status=status)
        sales_db.line(excluded, a, quantity=quantity, price="100.0000")
    before_start = sales_db.order(date(2025, 3, 31))
    sales_db.line(before_start, a, price="100.0000")
    after_as_of = sales_db.order(date(2026, 6, 1))
    sales_db.line(after_as_of, a, price="100.0000")

    report = AnalyticsQueries(sales_db.connection, date(2026, 5, 31))
    assert report.sales_summary().revenue == Decimal("73.00")
    assert report.sales_summary().orders == 3
    assert report.sales_summary().average_ticket == Decimal("24.33")
    assert report.sales_summary().partial_orders == 1

    months = {row.month: row for row in report.monthly_sales()}
    assert len(months) == 14
    assert (months[date(2025, 4, 1)].revenue, months[date(2025, 4, 1)].units) == (
        Decimal("28.00"),
        3,
    )
    assert (months[date(2025, 5, 1)].revenue, months[date(2025, 5, 1)].units) == (
        Decimal("0.00"),
        0,
    )
    assert months[date(2026, 2, 1)].revenue == Decimal("10.00")
    assert months[date(2026, 5, 1)].revenue == Decimal("35.00")
    assert months[date(2026, 5, 1)].is_partial
    assert not months[date(2026, 4, 1)].is_partial
    assert sum(row.revenue for row in months.values()) == Decimal("73.00")

    channels = {row.label: row.revenue for row in report.sales_by_channel()}
    assert channels == {
        "B2B": Decimal("63.00"),
        "B2C": Decimal("10.00"),
        "marketplace": Decimal("0.00"),
    }
    categories = {row.label: row.revenue for row in report.sales_by_category()}
    assert categories == {"Herramientas": Decimal("68.00"), "Sin categoría": Decimal("5.00")}
    assert {row.category_key for row in report.sales_by_category()} == {"herramientas", None}
    assert sum(channels.values()) == sum(categories.values()) == Decimal("73.00")

    top = report.top_products()
    assert [(row.sku, row.revenue) for row in top] == [
        ("A", Decimal("28.00")),
        ("B", Decimal("20.00")),
        ("F", Decimal("10.00")),
        ("U", Decimal("10.00")),
        ("H", Decimal("5.00")),
    ]
    assert top[-1].is_historical and top[-1].name is None

    margin = report.margin_summary()
    assert margin.known_margin == Decimal("-13.00")
    assert margin.known_revenue == Decimal("68.00")
    assert margin.unknown_revenue == Decimal("5.00")
    assert margin.coverage == Decimal("0.9315")
    assert margin.known_revenue + margin.unknown_revenue == report.sales_summary().revenue
    assert [
        (row.sku, row.stock_total, row.recent_units) for row in report.low_stock_products()
    ] == [
        ("A", 0, 1),
        ("B", 4, 1),
    ]
    assert report.previous_month_sales().revenue == Decimal("0.00")


def test_previous_month_window_and_empty_results(sales_db: SyntheticSales) -> None:
    product = sales_db.product("A", stock=0)
    before = sales_db.order(date(2026, 5, 31))
    sales_db.line(before, product, quantity=2, price="5.0000")
    on_day = sales_db.order(date(2026, 6, 1))
    sales_db.line(on_day, product, price="7.0000")
    sent = sales_db.order(date(2026, 6, 1), channel="marketplace", status="ENVIADO")
    sales_db.line(sent, product, price="3.0000")
    returned = sales_db.order(date(2026, 6, 1), status="DEVUELTO")
    sales_db.line(returned, product, price="100.0000")
    report = AnalyticsQueries(sales_db.connection, date(2026, 6, 1))
    assert report.previous_month_sales().revenue == Decimal("10.00")
    assert report.previous_month_sales().orders == 1
    assert report.sales_summary().revenue == Decimal("20.00")
    assert report.sales_summary().orders == 3
    assert report.low_stock_products()[0].recent_units == 4
    assert {row.label: row.revenue for row in report.sales_by_channel()}["marketplace"] == Decimal(
        "3.00"
    )

    early = AnalyticsQueries(sales_db.connection, date(2025, 4, 1))
    assert early.sales_summary().revenue == Decimal("0.00")
    assert early.sales_summary().orders == 0
    assert early.sales_summary().average_ticket is None
    assert early.previous_month_sales().revenue == Decimal("0.00")
    assert early.margin_summary().coverage is None
    assert early.monthly_sales()[0].revenue == Decimal("0.00")
    assert early.sales_by_category() == []
    assert early.top_products() == []
    assert early.low_stock_products() == []


def test_rounds_each_line_before_summing_and_top_ties(sales_db: SyntheticSales) -> None:
    order = sales_db.order(date(2025, 4, 2))
    for index in range(11, 0, -1):
        product = sales_db.product(f"SKU-{index:02d}", cost="0.0025")
        sales_db.line(order, product, price="10.0000")
    tiny = sales_db.product("TINY", cost="0.0025")
    sales_db.line(order, tiny, price="0.0050")
    sales_db.line(order, tiny, price="0.0050")
    report = AnalyticsQueries(sales_db.connection, date(2025, 4, 2))
    assert report.sales_summary().revenue == Decimal("110.02")
    assert report.sales_summary().average_ticket == Decimal("110.02")
    assert [row.sku for row in report.top_products()] == [
        f"SKU-{index:02d}" for index in range(1, 11)
    ]
    assert report.margin_summary().known_margin == Decimal("110.02")


def test_category_key_collapses_source_case_variants(sales_db: SyntheticSales) -> None:
    lower_case = sales_db.product("A", category="Herramienta manual")
    upper_case = sales_db.product("B", category="HERRAMIENTA MANUAL")
    order = sales_db.order(date(2025, 4, 2))
    sales_db.line(order, lower_case)
    sales_db.line(order, upper_case)
    report = AnalyticsQueries(sales_db.connection, date(2025, 4, 2))
    assert [(row.label, row.revenue) for row in report.sales_by_category()] == [
        ("Herramienta manual", Decimal("20.00"))
    ]
    assert report.sales_by_category()[0].category_key == "herramienta manual"


def test_calendar_month_clamping_and_reference_date_type(sales_db: SyntheticSales) -> None:
    assert months_before(date(2026, 5, 31), 3) == date(2026, 2, 28)
    assert months_before(date(2024, 5, 31), 3) == date(2024, 2, 29)
    assert months_before(date(2026, 1, 31), 3) == date(2025, 10, 31)
    with pytest.raises(ValueError, match="count"):
        months_before(date(2026, 5, 31), -1)
    with pytest.raises(TypeError, match="sin hora"):
        AnalyticsQueries(sales_db.connection, datetime(2026, 5, 31, 12))
