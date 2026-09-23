"""Persistencia parametrizada de catálogo F4; el caller controla la transacción."""

import json
from collections.abc import Iterable

from pymysql.connections import Connection

from src.etl.normalize import comparison_key
from src.etl.pricing import PricedCatalog, PricedProduct
from src.etl.records import Issue
from src.etl.reporting import RULES_VERSION, CatalogCounters


def start_run(connection: Connection, run_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO etl_runs (id, status, phase, rules_version) "
            "VALUES (%s, 'running', 'extract', %s)",
            (run_id, RULES_VERSION),
        )
    connection.commit()


def mark_publishing(connection: Connection, run_id: str, csv_hash: str, xml_hash: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE etl_runs SET phase = 'publish', csv_sha256 = %s, xml_sha256 = %s "
            "WHERE id = %s AND status = 'running'",
            (csv_hash, xml_hash, run_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Estado de ejecución no actualizable")
    connection.commit()


def insert_issues(connection: Connection, run_id: str, issues: Iterable[Issue]) -> None:
    with connection.cursor() as cursor:
        for issue in issues:
            cursor.execute(
                "INSERT INTO rejections (run_id, source, record_locator, entity_key, "
                "reason_code, field_name, action, severity, detail, raw_excerpt) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    run_id,
                    issue.ref.source,
                    issue.ref.locator,
                    issue.ref.entity_key,
                    str(issue.reason_code),
                    issue.field_name or "",
                    issue.action.value,
                    issue.severity.value,
                    issue.detail,
                    issue.raw_excerpt,
                ),
            )


def _product_params(product: PricedProduct, run_id: str) -> tuple[object, ...]:
    source = product.candidate.record.payload
    quote = product.quote
    return (
        source.sku,
        source.ean,
        source.name,
        source.brand,
        source.category,
        comparison_key(source.brand),
        comparison_key(source.category),
        source.base_cost,
        quote.net_cost,
        source.pvp,
        source.tax_rate,
        source.weight_kg,
        source.listed_on,
        source.description,
        quote.origin,
        quote.category_ratio,
        quote.brand_ratio,
        run_id,
    )


def publish_catalog(connection: Connection, run_id: str, priced: PricedCatalog) -> None:
    """Upsert y retiro de ausentes; nunca borrar filas ni convertir stock NULL en cero."""

    if not priced.products:
        raise ValueError("Catálogo sin productos válidos; se conserva el snapshot anterior")
    columns = (
        "sku",
        "ean",
        "name",
        "brand",
        "category",
        "brand_key",
        "category_key",
        "base_cost",
        "net_cost",
        "pvp",
        "tax_rate",
        "weight_kg",
        "listed_on",
        "description",
        "price_origin",
        "category_discount",
        "brand_discount",
    )
    assignments = ", ".join(f"{column} = VALUES({column})" for column in columns[1:])
    with connection.cursor() as cursor:
        for product in priced.products:
            cursor.execute(
                "INSERT INTO products ("
                + ", ".join(columns)
                + ", last_run_id) VALUES ("
                + ", ".join(["%s"] * 18)
                + ") "
                "ON DUPLICATE KEY UPDATE "
                + assignments
                + ", in_catalog = 1, is_historical = 0, last_run_id = VALUES(last_run_id)",
                _product_params(product, run_id),
            )
        cursor.execute(
            "UPDATE products SET in_catalog = 0, is_historical = 1, "
            "ean = NULL, name = NULL, brand = NULL, category = NULL, brand_key = NULL, "
            "category_key = NULL, base_cost = NULL, net_cost = NULL, pvp = NULL, "
            "tax_rate = NULL, weight_kg = NULL, listed_on = NULL, description = NULL, "
            "price_origin = NULL, category_discount = NULL, brand_discount = NULL, "
            "stock_total = NULL, stock_status = 'unknown', stock_as_of = NULL, "
            "last_run_id = %s WHERE in_catalog = 1 AND last_run_id <> %s",
            (run_id, run_id),
        )


def complete_run(
    connection: Connection,
    run_id: str,
    counters: CatalogCounters,
    csv_hash: str,
    xml_hash: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE etl_runs SET status = 'completed', phase = 'publish', "
            "finished_at = UTC_TIMESTAMP(6), csv_sha256 = %s, xml_sha256 = %s, "
            "counters = %s WHERE id = %s AND status = 'running'",
            (csv_hash, xml_hash, json.dumps({"catalog_csv": counters.as_dict()}), run_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Estado de ejecución no actualizable")


def fail_run(connection: Connection, run_id: str, code: str, issues: Iterable[Issue]) -> None:
    insert_issues(connection, run_id, issues)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE etl_runs SET status = 'failed', finished_at = UTC_TIMESTAMP(6), "
            "error_code = %s WHERE id = %s AND status = 'running'",
            (code, run_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Estado de ejecución no actualizable")
    connection.commit()
