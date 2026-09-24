"""Configuración de entorno y logging sin exponer secretos."""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values


class ConfigError(ValueError):
    """Un ajuste falta o es inválido; el valor nunca se muestra."""


@dataclass(frozen=True, slots=True)
class StockOptions:
    per_page: int = 50
    attempts: int = 5
    connect_timeout: int = 5
    read_timeout: int = 15
    requests_per_minute: int = 30
    budget_seconds: int = 300


@dataclass(frozen=True, slots=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    stock_api_url: str = field(repr=False)
    stock_api_token: str = field(repr=False)
    csv_path: Path
    xml_path: Path
    orders_csv_path: Path
    business_timezone: str
    log_level: str
    stock: StockOptions = field(default_factory=StockOptions)


_REQUIRED = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "STOCK_API_URL",
    "STOCK_API_TOKEN",
    "CSV_PATH",
    "XML_PATH",
)
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def _stock_options(values: Mapping[str, str]) -> StockOptions:
    options = {}
    for name, default, maximum in (
        ("per_page", 50, 100),
        ("attempts", 5, 10),
        ("connect_timeout", 5, 120),
        ("read_timeout", 15, 120),
        ("requests_per_minute", 30, 40),
        ("budget_seconds", 300, 3600),
    ):
        key = f"STOCK_{name.upper()}"
        try:
            value = int(values.get(key, str(default)))
        except ValueError:
            raise ConfigError(f"{key} inválido") from None
        if not 1 <= value <= maximum:
            raise ConfigError(f"{key} fuera de rango")
        options[name] = value
    return StockOptions(**options)


def load_settings(
    env_file: Path | None = Path(".env"),
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Carga .env si existe y da prioridad a variables reales del proceso."""

    values: dict[str, str] = {}
    if env_file is not None and env_file.is_file():
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    values.update(os.environ if environ is None else environ)

    for key in _REQUIRED:
        if not values.get(key, "").strip():
            raise ConfigError(f"Falta variable requerida: {key}")

    try:
        port = int(values["DB_PORT"])
    except ValueError:
        raise ConfigError("DB_PORT inválido") from None
    if not 1 <= port <= 65535:
        raise ConfigError("DB_PORT fuera de rango")

    try:
        url = urlsplit(values["STOCK_API_URL"])
        url_port = url.port
    except ValueError:
        raise ConfigError("STOCK_API_URL inválida") from None
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or (url_port is not None and not 1 <= url_port <= 65535)
    ):
        raise ConfigError("STOCK_API_URL inválida")

    timezone_name = values.get("BUSINESS_TIMEZONE", "Europe/Madrid").strip()
    try:
        ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError):
        raise ConfigError("BUSINESS_TIMEZONE inválida") from None

    log_level = values.get("LOG_LEVEL", "INFO").strip().upper()
    if log_level not in _LOG_LEVELS:
        raise ConfigError("LOG_LEVEL inválido")

    return Settings(
        db_host=values["DB_HOST"].strip(),
        db_port=port,
        db_name=values["DB_NAME"].strip(),
        db_user=values["DB_USER"].strip(),
        db_password=values["DB_PASSWORD"],
        stock_api_url=values["STOCK_API_URL"].strip(),
        stock_api_token=values["STOCK_API_TOKEN"],
        csv_path=Path(values["CSV_PATH"]),
        xml_path=Path(values["XML_PATH"]),
        orders_csv_path=Path(values.get("ORDERS_CSV_PATH") or "data/pedidos_historico.csv"),
        business_timezone=timezone_name,
        log_level=log_level,
        stock=_stock_options(values),
    )


class _RunFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "run_id"):
            record.run_id = "-"
        return super().format(record)


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configura una vez el logger de la aplicación, sin registrar ajustes."""

    normalized = level.upper()
    if normalized not in _LOG_LEVELS:
        raise ConfigError("LOG_LEVEL inválido")
    logger = logging.getLogger("src")
    logger.setLevel(normalized)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            _RunFormatter("%(asctime)s %(levelname)s %(name)s run=%(run_id)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


def get_run_logger(component: str, run_id: str | None = None) -> logging.LoggerAdapter:
    """Añade el identificador de ejecución al log del componente."""

    return logging.LoggerAdapter(logging.getLogger(f"src.{component}"), {"run_id": run_id or "-"})
