"""Consultas de solo lectura para contrastar F7, sin cálculos analíticos de F8."""

import hashlib
import json
from collections import Counter

from src import db
from src.config import Settings

BUSINESS_TABLES = ("products", "stock_by_warehouse", "orders", "order_lines")


def business_snapshot(settings: Settings) -> dict[str, tuple]:
    """Todos los campos, incluidos IDs y fechas de origen; excluir solo last_run_id."""
    snapshot = {}
    with db.connect(settings) as connection, connection.cursor() as cursor:
        for table in BUSINESS_TABLES:  # Identificadores constantes, nunca entrada externa.
            cursor.execute(f"SELECT * FROM {table} ORDER BY 1, 2")
            indexes = [i for i, col in enumerate(cursor.description) if col[0] != "last_run_id"]
            snapshot[table] = tuple(tuple(row[i] for i in indexes) for row in cursor.fetchall())
    return snapshot


def snapshot_hash(snapshot: dict[str, tuple]) -> str:
    serialized = json.dumps(snapshot, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def assert_integrity(settings: Settings) -> None:
    checks = (
        "SELECT COUNT(*) FROM order_lines l LEFT JOIN orders o ON o.id=l.order_id "
        "LEFT JOIN products p ON p.id=l.product_id WHERE o.id IS NULL OR p.id IS NULL",
        "SELECT COUNT(*) FROM stock_by_warehouse s LEFT JOIN products p ON p.id=s.product_id "
        "WHERE p.id IS NULL OR p.in_catalog<>1",
        "SELECT COUNT(*) FROM orders o LEFT JOIN order_lines l ON l.order_id=o.id "
        "WHERE l.id IS NULL",
        "SELECT COUNT(*) FROM order_lines l JOIN orders o ON o.id=l.order_id "
        "WHERE l.quantity<0 AND o.status<>'DEVUELTO'",
        "SELECT COUNT(*) FROM products WHERE stock_status<>'known' "
        "AND (stock_total IS NOT NULL OR stock_as_of IS NOT NULL)",
        "SELECT COUNT(*) FROM products WHERE is_historical=1 "
        "AND (in_catalog<>0 OR net_cost IS NOT NULL OR pvp IS NOT NULL OR stock_total IS NOT NULL)",
        "SELECT COUNT(*) FROM (SELECT p.id FROM products p LEFT JOIN stock_by_warehouse s "
        "ON s.product_id=p.id WHERE p.stock_status='known' GROUP BY p.id, p.stock_total "
        "HAVING COUNT(s.product_id)=0 OR p.stock_total<>SUM(s.quantity)) AS mismatch",
    )
    unique_keys = (
        ("products", "sku"),
        ("orders", "source_order_id"),
        ("order_lines", "order_id, line_key"),
        ("stock_by_warehouse", "product_id, warehouse_code"),
        ("rejections", "run_id, source, record_locator, reason_code, field_name"),
    )
    with db.connect(settings) as connection, connection.cursor() as cursor:
        for sql in checks:
            cursor.execute(sql)
            assert cursor.fetchone()[0] == 0, sql
        for table in (*BUSINESS_TABLES, "rejections"):
            column = "run_id" if table == "rejections" else "last_run_id"
            cursor.execute(
                f"SELECT COUNT(*) FROM {table} t LEFT JOIN etl_runs r ON r.id=t.{column} "
                "WHERE r.id IS NULL"
            )
            assert cursor.fetchone()[0] == 0, table
        for table, key in unique_keys:
            cursor.execute(
                f"SELECT COUNT(*) FROM (SELECT {key} FROM {table} "
                f"GROUP BY {key} HAVING COUNT(*)>1) AS duplicates"
            )
            assert cursor.fetchone()[0] == 0, (table, key)


def assert_counters(settings: Settings, run_id: str) -> dict[str, dict[str, int]]:
    """Reconciliar contadores con incidencias persistidas, no con el normalizador."""
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT status, counters FROM etl_runs WHERE id=%s", (run_id,))
        status, raw = cursor.fetchone()
        assert status == "completed"
        counters = json.loads(raw)
        cursor.execute(
            "SELECT source, record_locator, action FROM rejections WHERE run_id=%s", (run_id,)
        )
        issues = cursor.fetchall()
        for source, counts in counters.items():
            assert counts["rows_read"] == sum(
                counts[key] for key in ("rows_accepted", "rows_rejected", "rows_deduplicated")
            )
            for action, key in (
                ("reject_row", "rows_rejected"),
                ("deduplicate", "rows_deduplicated"),
            ):
                rows = {loc for src, loc, act in issues if src == source and act == action}
                assert counts[key] == len(rows), (source, key)
            # Las métricas de incidencias de catálogo incluyen las reglas XML asociadas.
            sources = {source, "tariffs_xml"} if source == "catalog_csv" else {source}
            actions = Counter(act for src, _, act in issues if src in sources)
            assert counts["quality_warnings"] == actions["warn"], source
            assert counts["discarded_fields"] == actions["drop_field"], source
        for source, sql in (
            ("catalog_csv", "SELECT COUNT(*) FROM products WHERE in_catalog=1"),
            ("stock_api", "SELECT COUNT(*) FROM stock_by_warehouse"),
            ("orders_csv", "SELECT COUNT(*) FROM order_lines"),
        ):
            cursor.execute(sql)
            assert counters[source]["rows_accepted"] == cursor.fetchone()[0], source
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(has_rejected_lines), 0) FROM orders")
        assert cursor.fetchone() == (
            counters["orders_csv"]["orders_loaded"],
            counters["orders_csv"]["partial_orders"],
        )
    return counters
