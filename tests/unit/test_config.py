"""Configuración sintética: nunca usa credenciales locales."""

import io
from pathlib import Path

import pytest

from src.config import ConfigError, configure_logging, get_run_logger, load_settings


@pytest.fixture
def settings_env() -> dict[str, str]:
    return {
        "DB_HOST": "localhost",
        "DB_PORT": "3307",
        "DB_NAME": "catalogo_test",
        "DB_USER": "user_test",
        "DB_PASSWORD": "secret-db-test",
        "STOCK_API_URL": "http://localhost:3001/api/v1/stock",
        "STOCK_API_TOKEN": "secret-stock-test",
        "CSV_PATH": "data/proveedor_productos.csv",
        "XML_PATH": "data/tarifas_proveedor.xml",
    }


def test_settings_are_typed_and_secrets_are_hidden(settings_env: dict[str, str]) -> None:
    settings = load_settings(env_file=None, environ=settings_env)
    assert settings.db_port == 3307
    assert settings.csv_path == Path("data/proveedor_productos.csv")
    assert settings.orders_csv_path == Path("data/pedidos_historico.csv")
    assert settings.business_timezone == "Europe/Madrid"
    assert settings.log_level == "INFO"
    assert "secret-db-test" not in repr(settings)
    assert "secret-stock-test" not in repr(settings)
    assert "api/v1/stock" not in repr(settings)


def test_process_environment_overrides_dotenv(tmp_path: Path, settings_env: dict[str, str]) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DB_HOST=from-file\nDB_PASSWORD=file-secret\n", encoding="utf-8")
    settings = load_settings(env_file, environ=settings_env)
    assert settings.db_host == "localhost"
    assert settings.db_password == "secret-db-test"


@pytest.mark.parametrize("key", ["DB_PASSWORD", "STOCK_API_TOKEN", "CSV_PATH"])
def test_missing_required_setting_names_only(settings_env: dict[str, str], key: str) -> None:
    settings_env[key] = ""
    with pytest.raises(ConfigError) as error:
        load_settings(env_file=None, environ=settings_env)
    assert key in str(error.value)
    assert "secret-db-test" not in str(error.value)
    assert "secret-stock-test" not in str(error.value)


@pytest.mark.parametrize(
    ("key", "bad_value"),
    [
        ("DB_PORT", "secret-port"),
        ("DB_PORT", "70000"),
        ("STOCK_API_URL", "http://secret-token@localhost:3001/stock"),
        ("STOCK_API_URL", "http://localhost:bad/stock"),
        ("BUSINESS_TIMEZONE", "secret-zone"),
        ("LOG_LEVEL", "secret-level"),
    ],
)
def test_invalid_settings_do_not_echo_input(
    settings_env: dict[str, str], key: str, bad_value: str
) -> None:
    settings_env[key] = bad_value
    with pytest.raises(ConfigError) as error:
        load_settings(env_file=None, environ=settings_env)
    assert key in str(error.value)
    assert bad_value not in str(error.value)


def test_optional_settings_are_configurable(settings_env: dict[str, str]) -> None:
    settings_env.update(
        {
            "ORDERS_CSV_PATH": "other/orders.csv",
            "BUSINESS_TIMEZONE": "UTC",
            "LOG_LEVEL": "warning",
        }
    )
    settings = load_settings(env_file=None, environ=settings_env)
    assert settings.orders_csv_path == Path("other/orders.csv")
    assert settings.business_timezone == "UTC"
    assert settings.log_level == "WARNING"


def test_logging_has_run_context_and_no_duplicate_handler() -> None:
    logger = configure_logging("INFO")
    handler_count = len(logger.handlers)
    assert configure_logging("DEBUG") is logger
    assert len(logger.handlers) == handler_count

    handler = logger.handlers[0]
    stream = io.StringIO()
    previous_stream = handler.stream
    handler.stream = stream
    try:
        get_run_logger("normalize", "run-123").info("normalización lista")
    finally:
        handler.stream = previous_stream
    output = stream.getvalue()
    assert "run=run-123" in output
    assert "normalización lista" in output
    assert "secret" not in output


@pytest.mark.parametrize(
    "key,value",
    [
        ("STOCK_PER_PAGE", "101"),
        ("STOCK_ATTEMPTS", "0"),
        ("STOCK_REQUESTS_PER_MINUTE", "41"),
        ("STOCK_BUDGET_SECONDS", "-1"),
        ("STOCK_CONNECT_TIMEOUT", "bad-secret"),
        ("STOCK_READ_TIMEOUT", "NaN"),
    ],
)
def test_invalid_stock_options(settings_env: dict[str, str], key: str, value: str) -> None:
    settings_env[key] = value
    with pytest.raises(ConfigError, match=key) as error:
        load_settings(None, settings_env)
    assert "bad-secret" not in str(error.value)


def test_stock_options_defaults_and_overrides(settings_env: dict[str, str]) -> None:
    defaults = load_settings(None, settings_env).stock
    assert (defaults.attempts, defaults.per_page, defaults.budget_seconds) == (5, 50, 300)
    settings_env.update({"STOCK_PER_PAGE": "100", "STOCK_ATTEMPTS": "3"})
    assert load_settings(None, settings_env).stock.per_page == 100
    assert load_settings(None, settings_env).stock.attempts == 3
