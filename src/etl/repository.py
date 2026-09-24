"""Persistencia parametrizada de catálogo y stock; el caller controla la transacción."""

import json
from collections.abc import Iterable

from pymysql.connections import Connection

from src.etl.normalize import comparison_key
from src.etl.orders import OrdersSelection
from src.etl.pricing import PricedCatalog, PricedProduct
from src.etl.records import Action, Issue, ReasonCode, Severity, SourceRef
from src.etl.reporting import RULES_VERSION, CatalogCounters
from src.etl.stock import ReconciledStock, StockCounters


def start_run(connection: Connection, run_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO etl_runs (id, status, phase, rules_version) "
            "VALUES (%s, 'running', 'extract', %s)",
            (run_id, RULES_VERSION),
        )
    connection.commit()


def mark_publishing(
    connection: Connection,
    run_id: str,
    csv_hash: str,
    xml_hash: str,
    stock_hash: str,
    orders_hash: str,
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE etl_runs SET phase = 'publish', csv_sha256 = %s, xml_sha256 = %s, "
            "stock_sha256 = %s, orders_sha256 = %s WHERE id = %s AND status = 'running'",
            (csv_hash, xml_hash, stock_hash, orders_hash, run_id),
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
    stock_counters: StockCounters,
    order_counts: dict[str, int],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE etl_runs SET status = 'completed', phase = 'publish', "
            "finished_at = UTC_TIMESTAMP(6), csv_sha256 = %s, xml_sha256 = %s, "
            "counters = %s WHERE id = %s AND status = 'running'",
            (
                csv_hash,
                xml_hash,
                json.dumps(
                    {
                        "catalog_csv": counters.as_dict(),
                        "stock_api": stock_counters.as_dict(),
                        "orders_csv": order_counts,
                    }
                ),
                run_id,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("Estado de ejecución no actualizable")


def publish_stock(connection: Connection, run_id: str, stock: ReconciledStock) -> None:
    """Reemplaza solo la instantánea de almacenes dentro de la transacción del caller."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT sku, id FROM products WHERE in_catalog = 1")
        product_ids = dict(cursor.fetchall())
        if product_ids.keys() != {total.sku for total in stock.totals}:
            raise ValueError("Stock y catálogo no corresponden a la misma instantánea")
        cursor.execute("DELETE FROM stock_by_warehouse")
        for row in stock.observations:
            cursor.execute(
                "INSERT INTO stock_by_warehouse "
                "(product_id, warehouse_code, quantity, reserved, updated_at, last_run_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    product_ids[row.sku],
                    row.warehouse,
                    row.quantity,
                    row.reserved,
                    row.updated_at.replace(tzinfo=None),
                    run_id,
                ),
            )
        for total in stock.totals:
            cursor.execute(
                "UPDATE products SET stock_total = %s, stock_status = %s, stock_as_of = %s "
                "WHERE id = %s",
                (
                    total.quantity,
                    total.status,
                    total.as_of.replace(tzinfo=None) if total.as_of else None,
                    product_ids[total.sku],
                ),
            )


def publish_orders(
    connection: Connection, run_id: str, selection: OrdersSelection, catalog_skus_seen: set[str]
) -> tuple[Issue, ...]:
    """Upserts conservan IDs; retira versiones ausentes sin desactivar las FKs."""
    if not selection.orders:
        raise ValueError("Pedidos sin entidades válidas; no se publica")
    created = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT sku, id FROM products")
        product_ids = dict(cursor.fetchall())
        for order in selection.orders:
            for line in order.lines:
                if line.sku in product_ids:
                    cursor.execute(
                        "UPDATE products SET last_run_id = %s WHERE id = %s",
                        (run_id, product_ids[line.sku]),
                    )
                    continue
                cursor.execute(
                    "INSERT INTO products (sku, in_catalog, is_historical, last_run_id) "
                    "VALUES (%s, 0, 1, %s)",
                    (line.sku, run_id),
                )
                product_ids[line.sku] = cursor.lastrowid
                origin = (
                    "rechazado en catálogo"
                    if line.sku in catalog_skus_seen
                    else "ausente del catálogo"
                )
                created.append(
                    Issue(
                        SourceRef("orders_csv", line.ref.locator, line.sku),
                        ReasonCode.HISTORICAL_PRODUCT_CREATED,
                        Action.WARN,
                        Severity.WARNING,
                        f"Histórico creado: SKU {origin}; pedido {order.header.source_order_id}",
                    )
                )
            header = order.header
            cursor.execute(
                "INSERT INTO orders (source_order_id, order_date, customer, channel, status, "
                "has_rejected_lines, last_run_id) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE order_date=VALUES(order_date), customer=VALUES(customer), "
                "channel=VALUES(channel), status=VALUES(status), "
                "has_rejected_lines=VALUES(has_rejected_lines), last_run_id=VALUES(last_run_id)",
                (
                    header.source_order_id,
                    header.order_date,
                    header.customer,
                    header.channel,
                    header.status,
                    order.has_rejected_lines,
                    run_id,
                ),
            )
            cursor.execute(
                "SELECT id FROM orders WHERE source_order_id=%s", (header.source_order_id,)
            )
            order_id = cursor.fetchone()[0]
            for line in order.lines:
                cursor.execute(
                    "INSERT INTO order_lines (order_id, product_id, line_key, quantity, unit_price, "
                    "discount, source_locator, last_run_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE source_locator=VALUES(source_locator), "
                    "last_run_id=VALUES(last_run_id)",
                    (
                        order_id,
                        product_ids[line.sku],
                        line.line_key,
                        line.quantity,
                        line.unit_price,
                        line.discount,
                        line.ref.locator,
                        run_id,
                    ),
                )
        cursor.execute("DELETE FROM order_lines WHERE last_run_id <> %s", (run_id,))
        cursor.execute("DELETE FROM orders WHERE last_run_id <> %s", (run_id,))
    return tuple(created)


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
