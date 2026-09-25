"""Catálogo comercial y metadatos de publicación, siempre de solo lectura."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pymysql.connections import Connection

from src.etl.normalize import comparison_key

PAGE_SIZE = 20


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    sku: str
    name: str
    category: str
    net_cost: Decimal
    pvp: Decimal
    stock_total: int | None
    stock_status: str


@dataclass(frozen=True, slots=True)
class CatalogPage:
    products: list[CatalogProduct]
    total: int
    page: int
    pages: int


@dataclass(frozen=True, slots=True)
class Publication:
    run_id: str | None
    finished_at: datetime | None  # UTC, como etl_runs
    conflicting_skus: list[str]


def catalog_page(
    connection: Connection, search: str = "", category: str = "", page: int = 1
) -> CatalogPage:
    """Búsqueda literal sin distinguir mayúsculas; % y _ no son comodines."""

    clauses = ["in_catalog = 1"]
    parameters: list[object] = []
    if search.strip():
        text = search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        clauses.append(
            "(sku COLLATE utf8mb4_unicode_ci LIKE %s ESCAPE '!' "
            "OR name COLLATE utf8mb4_unicode_ci LIKE %s ESCAPE '!' "
            "OR description COLLATE utf8mb4_unicode_ci LIKE %s ESCAPE '!')"
        )
        parameters.extend([f"%{text}%"] * 3)
    if category:
        clauses.append("category_key = %s")
        parameters.append(comparison_key(category))
    where = " AND ".join(clauses)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM products WHERE {where}", parameters)
        total = int(cursor.fetchone()[0])
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(max(page, 1), pages)
        cursor.execute(
            "SELECT sku, name, category, net_cost, pvp, stock_total, stock_status "
            f"FROM products WHERE {where} ORDER BY sku LIMIT %s OFFSET %s",
            (*parameters, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )
        products = [CatalogProduct(*row) for row in cursor.fetchall()]
    return CatalogPage(products, total, page, pages)


def catalog_categories(connection: Connection) -> list[tuple[str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT category_key, MAX(category COLLATE utf8mb4_bin) "
            "FROM products WHERE in_catalog = 1 GROUP BY category_key ORDER BY category_key"
        )
        return list(cursor.fetchall())


def latest_publication(connection: Connection) -> Publication:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, finished_at FROM etl_runs WHERE status = 'completed' "
            "ORDER BY finished_at DESC, started_at DESC, id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            return Publication(None, None, [])
        run_id, finished_at = row
        cursor.execute(
            "SELECT DISTINCT r.entity_key FROM rejections r "
            "JOIN products p ON p.sku = r.entity_key "
            "WHERE r.run_id = %s AND r.source = 'catalog_csv' "
            "AND r.reason_code = 'CONFLICTING_PRODUCT_SKU' AND p.in_catalog = 1 "
            "ORDER BY r.entity_key",
            (run_id,),
        )
        return Publication(run_id, finished_at, [record[0] for record in cursor.fetchall()])
