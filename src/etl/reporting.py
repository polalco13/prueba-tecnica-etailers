"""Contadores de catálogo/pedidos y versión de reglas, independientes de affected_rows."""

from dataclasses import asdict, dataclass

from src.etl.orders import OrdersSelection
from src.etl.pricing import PricedCatalog
from src.etl.records import Action

RULES_VERSION = "catalog-stock-orders-v2"


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
