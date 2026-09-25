"""Contadores de catálogo/pedidos y versión de reglas, independientes de affected_rows."""

import json
from dataclasses import asdict, dataclass
from datetime import date

from pymysql.connections import Connection

from src.analytics.queries import AnalyticsQueries, months_before
from src.etl.orders import OrdersSelection
from src.etl.pricing import PricedCatalog
from src.etl.records import Action

RULES_VERSION = "catalog-stock-orders-v2"
SUMMARY_VERSION = "etl-summary-v1"


def needs_alert(rows_rejected: int, low_stock_count: int, threshold: int) -> bool:
    """Umbral estricto; duplicados/avisos no son rechazos."""

    if min(rows_rejected, low_stock_count, threshold) < 0:
        raise ValueError("Contadores o umbral negativos")
    return rows_rejected > threshold or low_stock_count > 0


def make_summary(
    connection: Connection,
    run_id: str,
    business_timezone: str,
    threshold: int,
    as_of: date | None = None,
) -> dict:
    """Captura el run y sus métricas antes del commit, bajo el lock del escritor.

    Se persiste junto con el negocio; el HTTP se ejecuta después del commit.
    No reconstruir este resumen con los datos de una ejecución posterior.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, finished_at, rules_version, counters FROM etl_runs WHERE id = %s",
            (run_id,),
        )
        row = cursor.fetchone()
        if row is None or row[0] != "completed" or row[1] is None or row[3] is None:
            raise ValueError("El resumen requiere un run completado con contadores")
        _, finished_at, rules_version, counters_json = row
        counters = json.loads(counters_json)
        cursor.execute(
            "SELECT source, reason_code, COUNT(DISTINCT record_locator) FROM rejections "
            "WHERE run_id = %s AND action = 'reject_row' "
            "GROUP BY source, reason_code ORDER BY source, reason_code",
            (run_id,),
        )
        reasons = [
            {"source": source, "reason_code": code, "rows": int(count)}
            for source, code, count in cursor.fetchall()
        ]
    queries = AnalyticsQueries(connection, as_of, business_timezone)
    previous_month = months_before(queries.as_of.replace(day=1), 1)
    low_stock = [asdict(product) for product in queries.low_stock_products()]
    rejected = sum(source["rows_rejected"] for source in counters.values())
    return {
        "schema_version": SUMMARY_VERSION,
        "run_id": run_id,
        "status": "completed",
        "finished_at": finished_at.isoformat(timespec="microseconds") + "Z",
        "rules_version": rules_version,
        "as_of": queries.as_of.isoformat(),
        "business_timezone": business_timezone,
        "products_loaded": counters["catalog_csv"]["products_loaded"],
        "rows": counters,
        "rows_rejected": rejected,
        "rejected_by_reason": reasons,
        "revenue_previous_month": format(queries.previous_month_sales().revenue, ".2f"),
        "previous_month": previous_month.strftime("%Y-%m"),
        "currency": None,
        "tax_basis": "unconfirmed",
        "low_stock_count": len(low_stock),
        "low_stock_products": low_stock,
        "rejection_threshold": threshold,
        "alert_required": needs_alert(rejected, len(low_stock), threshold),
    }


def orders_counters(selection: OrdersSelection, historical_created: int = 0) -> dict[str, int]:
    return {
        "rows_read": selection.rows_read,
        "rows_accepted": selection.rows_accepted,
        "rows_rejected": selection.rows_rejected,
        "rows_deduplicated": selection.rows_deduplicated,
        "quality_warnings": sum(i.action == Action.WARN for i in selection.issues)
        + historical_created,
        "discarded_fields": 0,
        "orders_loaded": len(selection.orders),
        "partial_orders": sum(o.has_rejected_lines for o in selection.orders),
        "historical_products_created": historical_created,
    }


@dataclass(frozen=True, slots=True)
class CatalogCounters:
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    rows_deduplicated: int
    quality_warnings: int
    discarded_fields: int
    products_loaded: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def catalog_counters(priced: PricedCatalog) -> CatalogCounters:
    selection = priced.selection
    counters = CatalogCounters(
        rows_read=selection.rows_read,
        rows_accepted=selection.rows_accepted,
        rows_rejected=selection.rows_rejected,
        rows_deduplicated=selection.rows_deduplicated,
        quality_warnings=sum(issue.action == Action.WARN for issue in priced.issues),
        discarded_fields=sum(issue.action == Action.DROP_FIELD for issue in priced.issues),
        products_loaded=len(priced.products),
    )
    if (
        counters.rows_read
        != counters.rows_accepted + counters.rows_rejected + counters.rows_deduplicated
        or counters.rows_accepted != counters.products_loaded
    ):
        raise ValueError("Contadores de catálogo inconsistentes")
    return counters
