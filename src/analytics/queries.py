"""Métricas F8 sobre MySQL; una sola definición de venta elegible.

Los importes son operativos y conservan la base fiscal recibida del ERP. El
coste actual del catálogo solo permite estimar un margen con cobertura visible.
"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from pymysql.connections import Connection

SALES_START = date(2025, 4, 1)
ZERO_MONEY = Decimal("0.00")
ONE_HUNDREDTH = Decimal("0.01")
ONE_TEN_THOUSANDTH = Decimal("0.0001")

# Cada consulta usa este conjunto. El JOIN con products es 1:1 por PK; nunca
# se une stock_by_warehouse a líneas de pedido.
_ELIGIBLE = """
WITH eligible_lines AS (
    SELECT o.id AS order_id, o.order_date, o.channel, o.has_rejected_lines,
           l.product_id, l.quantity, p.sku, p.name, p.category, p.category_key,
           p.is_historical, p.net_cost,
           ROUND(l.quantity * l.unit_price * (1 - l.discount), 2) AS amount
    FROM orders AS o
    JOIN order_lines AS l ON l.order_id = o.id
    JOIN products AS p ON p.id = l.product_id
    WHERE o.status IN ('ENVIADO', 'COMPLETADO')
      AND l.quantity > 0
      AND o.order_date >= %s AND o.order_date <= %s
)
"""


@dataclass(frozen=True, slots=True)
class SalesSummary:
    revenue: Decimal
    orders: int
    average_ticket: Decimal | None
    partial_orders: int


@dataclass(frozen=True, slots=True)
class MonthlySales:
    month: date
    revenue: Decimal
    units: int
    is_partial: bool


@dataclass(frozen=True, slots=True)
class SalesBreakdown:
    label: str
    revenue: Decimal
    units: int


@dataclass(frozen=True, slots=True)
class CategorySales:
    category_key: str | None
    label: str
    revenue: Decimal
    units: int


@dataclass(frozen=True, slots=True)
class TopProduct:
    sku: str
    name: str | None
    is_historical: bool
    revenue: Decimal
    units: int


@dataclass(frozen=True, slots=True)
class MarginSummary:
    known_margin: Decimal
    known_revenue: Decimal
    unknown_revenue: Decimal
    coverage: Decimal | None  # fracción monetaria, no porcentaje


@dataclass(frozen=True, slots=True)
class LowStockProduct:
    sku: str
    name: str
    stock_total: int
    recent_units: int


def months_before(day: date, count: int) -> date:
    """Resta meses naturales conservando el día o ajustando al último válido."""

    if count < 0:
        raise ValueError("count debe ser no negativo")
    month_index = day.year * 12 + day.month - 1 - count
    year, zero_based_month = divmod(month_index, 12)
    if year < 1:
        raise ValueError("fecha fuera de rango")
    month = zero_based_month + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _next_month(day: date) -> date:
    year = day.year + (day.month == 12)
    month = 1 if day.month == 12 else day.month + 1
    return date(year, month, 1)


def _money(value: Decimal | None) -> Decimal:
    return ZERO_MONEY if value is None else value.quantize(ONE_HUNDREDTH)


class AnalyticsQueries:
    """Consultas de solo lectura sobre una conexión MySQL del esquema F6.

    La llamada que agrupa varias métricas debe usar la misma conexión para
    mantener una instantánea consistente frente a una publicación ETL.
    """

    def __init__(
        self,
        connection: Connection,
        as_of: date | None = None,
        business_timezone: str = "Europe/Madrid",
    ) -> None:
        self.connection = connection
        if as_of is not None and isinstance(as_of, datetime):
            raise TypeError("as_of debe ser una fecha sin hora")
        self.as_of = as_of or datetime.now(ZoneInfo(business_timezone)).date()

    def _fetch(self, sql: str, *parameters: object) -> tuple[tuple, ...]:
        with self.connection.cursor() as cursor:
            cursor.execute(_ELIGIBLE + sql, (SALES_START, self.as_of, *parameters))
            return cursor.fetchall()

    def _summary(self, start: date | None = None, end: date | None = None) -> SalesSummary:
        clause = ""
        parameters: tuple[date, ...] = ()
        if start is not None and end is not None:
            clause = "WHERE order_date >= %s AND order_date < %s"
            parameters = (start, end)
        row = self._fetch(
            f"""
            SELECT COALESCE(SUM(amount), 0), COUNT(DISTINCT order_id),
                   COUNT(DISTINCT CASE WHEN has_rejected_lines = 1 THEN order_id END)
            FROM eligible_lines {clause}
            """,
            *parameters,
        )[0]
        revenue, orders, partial_orders = _money(row[0]), int(row[1]), int(row[2])
        ticket = (
            (revenue / Decimal(orders)).quantize(ONE_HUNDREDTH, rounding=ROUND_HALF_UP)
            if orders
            else None
        )
        return SalesSummary(revenue, orders, ticket, partial_orders)

    def sales_summary(self) -> SalesSummary:
        return self._summary()

    def previous_month_sales(self) -> SalesSummary:
        """Mes natural anterior completo; conserva el límite global abril 2025."""

        month_start = self.as_of.replace(day=1)
        return self._summary(months_before(month_start, 1), month_start)

    def monthly_sales(self) -> list[MonthlySales]:
        rows = self._fetch(
            """
            SELECT DATE_FORMAT(order_date, '%%Y-%%m'), SUM(amount), SUM(quantity)
            FROM eligible_lines
            GROUP BY DATE_FORMAT(order_date, '%%Y-%%m')
            ORDER BY DATE_FORMAT(order_date, '%%Y-%%m')
            """
        )
        by_month = {month: (_money(revenue), int(units)) for month, revenue, units in rows}
        result = []
        month = SALES_START
        current_month = self.as_of.replace(day=1)
        while month <= current_month:
            revenue, units = by_month.get(month.strftime("%Y-%m"), (ZERO_MONEY, 0))
            result.append(MonthlySales(month, revenue, units, month == current_month))
            month = _next_month(month)
        return result

    def sales_by_channel(self) -> list[SalesBreakdown]:
        rows = self._fetch(
            """
            SELECT channel, SUM(amount), SUM(quantity)
            FROM eligible_lines GROUP BY channel
            """
        )
        by_channel = {channel: (_money(amount), int(units)) for channel, amount, units in rows}
        return [
            SalesBreakdown(channel, *by_channel.get(channel, (ZERO_MONEY, 0)))
            for channel in ("B2B", "B2C", "marketplace")
        ]

    def sales_by_category(self) -> list[CategorySales]:
        rows = self._fetch(
            """
            SELECT category_key, MAX(category COLLATE utf8mb4_bin), SUM(amount), SUM(quantity)
            FROM eligible_lines GROUP BY category_key
            ORDER BY category_key IS NULL, category_key
            """
        )
        return [
            CategorySales(
                key,
                category if category is not None else "Sin categoría",
                _money(amount),
                int(units),
            )
            for key, category, amount, units in rows
        ]

    def top_products(self) -> list[TopProduct]:
        rows = self._fetch(
            """
            SELECT sku, name, is_historical, SUM(amount) AS revenue, SUM(quantity)
            FROM eligible_lines
            GROUP BY product_id, sku, name, is_historical
            ORDER BY revenue DESC, sku ASC
            LIMIT 10
            """
        )
        return [
            TopProduct(sku, name, bool(historical), _money(amount), int(units))
            for sku, name, historical, amount, units in rows
        ]

    def margin_summary(self) -> MarginSummary:
        known_margin, known_revenue, unknown_revenue = self._fetch(
            """
            SELECT COALESCE(SUM(CASE WHEN net_cost IS NOT NULL
                        THEN amount - ROUND(quantity * net_cost, 2) ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN net_cost IS NOT NULL THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN net_cost IS NULL THEN amount ELSE 0 END), 0)
            FROM eligible_lines
            """
        )[0]
        known, unknown = _money(known_revenue), _money(unknown_revenue)
        total = known + unknown
        coverage = (
            (known / total).quantize(ONE_TEN_THOUSANDTH, rounding=ROUND_HALF_UP)
            if total != ZERO_MONEY
            else None
        )
        return MarginSummary(_money(known_margin), known, unknown, coverage)

    def low_stock_products(self) -> list[LowStockProduct]:
        """Stock físico vigente conocido <5 y venta en ventana inclusiva."""

        cutoff = months_before(self.as_of, 3)
        rows = self._fetch(
            """
            SELECT p.sku, p.name, p.stock_total, SUM(e.quantity) AS recent_units
            FROM products AS p
            JOIN eligible_lines AS e ON e.product_id = p.id
            WHERE p.in_catalog = 1 AND p.stock_status = 'known'
              AND p.stock_total < 5 AND e.order_date >= %s
            GROUP BY p.id, p.sku, p.name, p.stock_total
            ORDER BY p.stock_total ASC, recent_units DESC, p.sku ASC
            """,
            cutoff,
        )
        return [
            LowStockProduct(sku, name, int(stock), int(units)) for sku, name, stock, units in rows
        ]
