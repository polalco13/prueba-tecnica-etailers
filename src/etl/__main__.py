"""ETL y entrega F10; --resend-make reenvía sin volver a cargar fuentes."""

import argparse

from src.config import configure_logging, get_run_logger, load_settings
from src.etl.make_client import deliver_run
from src.etl.runner import run_etl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ETL de cuatro fuentes y entrega Make")
    parser.add_argument("--resend-make", metavar="RUN_ID", help="Reenviar el resumen guardado")
    parser.add_argument(
        "--force", action="store_true", help="Reenviar aun con HTTP aceptado previo"
    )
    args = parser.parse_args(argv)
    if args.force and not args.resend_make:
        parser.error("--force requiere --resend-make")
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        if args.resend_make:
            delivery = deliver_run(settings, args.resend_make, force=args.force)
            return 0 if delivery.status == "accepted" else 2
        result = run_etl(settings)
    except Exception as exc:
        # Los detalles de excepciones de fuentes/DB pueden incluir datos o credenciales.
        if args.resend_make:
            get_run_logger("make").error("Reenvío no confirmado (%s)", type(exc).__name__)
            return 2
        get_run_logger("etl").error("Ejecución ETL no completada (%s)", type(exc).__name__)
        return 1
    get_run_logger("etl", result.run_id).info(
        "Catálogo: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d",
        result.counters.rows_read,
        result.counters.rows_accepted,
        result.counters.rows_rejected,
        result.counters.rows_deduplicated,
    )
    get_run_logger("etl", result.run_id).info(
        "Stock: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d",
        result.stock_counters.rows_read,
        result.stock_counters.rows_accepted,
        result.stock_counters.rows_rejected,
        result.stock_counters.rows_deduplicated,
    )
    get_run_logger("etl", result.run_id).info(
        "Pedidos: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d pedidos=%d parciales=%d",
        result.orders_counters["rows_read"],
        result.orders_counters["rows_accepted"],
        result.orders_counters["rows_rejected"],
        result.orders_counters["rows_deduplicated"],
        result.orders_counters["orders_loaded"],
        result.orders_counters["partial_orders"],
    )
    if result.make_status not in {"accepted", "not_applicable"}:
        get_run_logger("etl", result.run_id).warning(
            "ETL completado; entrega Make no confirmada. Reenviar con --resend-make RUN_ID"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
