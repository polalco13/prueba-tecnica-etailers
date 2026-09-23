"""Comando parcial F4: python -m src.etl."""

from src.config import configure_logging, get_run_logger, load_settings
from src.etl.runner import run_catalog_pricing


def main() -> int:
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        result = run_catalog_pricing(settings)
    except Exception as exc:
        # Los detalles de excepciones de fuentes/DB pueden incluir datos o credenciales.
        get_run_logger("etl").error("Ejecución F4 no completada (%s)", type(exc).__name__)
        return 1
    get_run_logger("etl", result.run_id).info(
        "F4 completada: leídas=%d aceptadas=%d rechazadas=%d deduplicadas=%d",
        result.counters.rows_read,
        result.counters.rows_accepted,
        result.counters.rows_rejected,
        result.counters.rows_deduplicated,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
