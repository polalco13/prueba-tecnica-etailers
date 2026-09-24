"""Comando parcial F6 (cuatro fuentes): python -m src.etl."""

from src.config import configure_logging, get_run_logger, load_settings
from src.etl.runner import run_etl


def main() -> int:
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        result = run_etl(settings)
    except Exception as exc:
        # Los detalles de excepciones de fuentes/DB pueden incluir datos o credenciales.
        get_run_logger("etl").error("Ejecución F5 no completada (%s)", type(exc).__name__)
        return 1
    get_run_logger("etl", result.run_id).info(
        "F6 catálogo: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d",
        result.counters.rows_read,
        result.counters.rows_accepted,
        result.counters.rows_rejected,
        result.counters.rows_deduplicated,
    )
    get_run_logger("etl", result.run_id).info(
        "F6 stock: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d",
        result.stock_counters.rows_read,
        result.stock_counters.rows_accepted,
        result.stock_counters.rows_rejected,
        result.stock_counters.rows_deduplicated,
    )
    get_run_logger("etl", result.run_id).info(
        "F6 pedidos: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d pedidos=%d parciales=%d",
        result.orders_counters["rows_read"],
        result.orders_counters["rows_accepted"],
        result.orders_counters["rows_rejected"],
        result.orders_counters["rows_deduplicated"],
        result.orders_counters["orders_loaded"],
        result.orders_counters["partial_orders"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
