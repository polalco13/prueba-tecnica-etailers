"""Comprobación F12 con fuentes originales, solo en la BD temporal f12_real.

Ejecutar desde la raíz: .venv/bin/python docs/validation/verify_repeatability.py.
No imprime clientes, extractos de pedidos ni configuración privada.
"""

import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/integration"))

from etl_checks import (  # noqa: E402
    assert_counters,
    assert_integrity,
    business_snapshot,
    snapshot_hash,
)

from src import db  # noqa: E402
from src.analytics.queries import AnalyticsQueries  # noqa: E402
from src.config import configure_logging, load_settings  # noqa: E402
from src.etl.runner import run_etl  # noqa: E402

AS_OF = date(2026, 9, 28)


def file_hashes() -> dict[str, str]:
    paths = [*sorted((ROOT / "data").glob("*")), ROOT / "mock-api/stock.json"]
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }


def main() -> None:
    settings = load_settings()
    if (
        settings.db_host != "127.0.0.1"
        or settings.db_port != 13317
        or settings.db_name != "f12_real"
        or settings.stock_api_url != "http://127.0.0.1:13311/api/v1/stock"
        or settings.make.webhook_url
    ):
        raise RuntimeError("Requiere el entorno aislado F12 y Make desactivado")
    with db.connect(settings) as connection, connection.cursor() as cursor:
        for table in ("products", "orders", "order_lines", "etl_runs"):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            if cursor.fetchone()[0]:
                raise RuntimeError("La comprobación exige f12_real inicialmente vacía")
        cursor.execute("SELECT VERSION()")
        mysql_version = cursor.fetchone()[0]

    configure_logging()
    hashes_before = file_hashes()
    runs = []
    snapshots = []
    for _ in range(2):
        result = run_etl(settings, as_of=AS_OF)
        assert_integrity(settings)
        counters = assert_counters(settings, result.run_id)
        snapshot = business_snapshot(settings)
        snapshots.append(snapshot)
        with db.connect(settings) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT csv_sha256, xml_sha256, orders_sha256, stock_sha256, "
                "make_status, make_attempts FROM etl_runs WHERE id=%s",
                (result.run_id,),
            )
            source_hashes = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM rejections WHERE run_id=%s", (result.run_id,))
            issues = cursor.fetchone()[0]
        assert source_hashes[4:] == ("not_applicable", 0)
        runs.append(
            {
                "run_id": result.run_id,
                "counters": counters,
                "issues": issues,
                "source_hashes": source_hashes[:4],
                "business_hash": snapshot_hash(snapshot),
                "table_counts": {table: len(rows) for table, rows in snapshot.items()},
            }
        )
    assert snapshots[0] == snapshots[1]
    assert runs[0]["source_hashes"] == runs[1]["source_hashes"]
    assert file_hashes() == hashes_before

    # Recálculo Decimal sobre valores de líneas; no reutiliza el SQL de AnalyticsQueries.
    monthly = defaultdict(lambda: [Decimal("0.00"), 0])
    revenue = margin = known = unknown = Decimal("0.00")
    order_ids = set()
    cent = Decimal("0.01")
    with db.connect(settings) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT o.id, o.order_date, o.status, l.quantity, l.unit_price, "
            "l.discount, p.net_cost FROM order_lines l "
            "JOIN orders o ON o.id=l.order_id JOIN products p ON p.id=l.product_id"
        )
        for order_id, day, status, quantity, price, discount, cost in cursor.fetchall():
            if status not in ("ENVIADO", "COMPLETADO") or quantity <= 0:
                continue
            if not date(2025, 4, 1) <= day <= AS_OF:
                continue
            amount = (quantity * price * (1 - discount)).quantize(cent, rounding=ROUND_HALF_UP)
            revenue += amount
            order_ids.add(order_id)
            monthly[day.replace(day=1)][0] += amount
            monthly[day.replace(day=1)][1] += quantity
            if cost is None:
                unknown += amount
            else:
                known += amount
                margin += amount - (quantity * cost).quantize(cent, rounding=ROUND_HALF_UP)
        analytics = AnalyticsQueries(connection, AS_OF)
        summary = analytics.sales_summary()
        margins = analytics.margin_summary()
        series = analytics.monthly_sales()
        assert summary.revenue == revenue and summary.orders == len(order_ids)
        assert margins.known_margin == margin
        assert (margins.known_revenue, margins.unknown_revenue) == (known, unknown)
        assert sum(row.revenue for row in analytics.sales_by_channel()) == revenue
        assert sum(row.revenue for row in analytics.sales_by_category()) == revenue
        for month in series:
            assert [month.revenue, month.units] == monthly[month.month]
        cursor.execute("SELECT COUNT(*) FROM etl_runs WHERE status='completed'")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT DISTINCT source_order_id FROM orders")
        loaded_ids = {row[0] for row in cursor.fetchall()}
        with settings.orders_csv_path.open(encoding="utf-8-sig", newline="") as stream:
            source_ids = {row["id_pedido"].strip().upper() for row in csv.DictReader(stream)}
        source_ids.discard("")
        missing_ids = sorted(source_ids - loaded_ids)
        # Solo identificadores y motivos; nunca cabeceras con nombres de clientes.
        missing_reasons = {}
        for order_id in missing_ids:
            cursor.execute(
                "SELECT DISTINCT reason_code FROM rejections "
                "WHERE run_id=%s AND source='orders_csv' AND entity_key=%s",
                (runs[-1]["run_id"], order_id),
            )
            missing_reasons[order_id] = [row[0] for row in cursor.fetchall()]
        report = {
            "base_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "as_of": AS_OF,
            "mysql_version": mysql_version,
            "inputs": hashes_before,
            "runs": runs,
            "same_business": True,
            "source_orders": len(source_ids),
            "loaded_orders": len(loaded_ids),
            "missing_order_reasons": missing_reasons,
            "sales": asdict(summary),
            "margin": asdict(margins),
            "monthly": [asdict(row) for row in series],
            "low_stock_count": len(analytics.low_stock_products()),
            "independent_recalculation": "passed",
            "make_requests": 0,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
