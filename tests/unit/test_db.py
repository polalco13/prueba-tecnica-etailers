"""Arranque MySQL sintético: no conecta a servicios ni usa secretos locales."""

import logging
import sys
from unittest.mock import MagicMock, Mock

import pymysql
import pytest
from pymysql.connections import Connection

from src import db
from src.config import Settings, load_settings


@pytest.fixture
def settings() -> Settings:
    return load_settings(
        env_file=None,
        environ={
            "DB_HOST": "example.invalid",
            "DB_PORT": "3307",
            "DB_NAME": "synthetic_db",
            "DB_USER": "synthetic_user",
            "DB_PASSWORD": "synthetic-password-do-not-display",
            "STOCK_API_URL": "http://example.invalid/stock",
            "STOCK_API_TOKEN": "synthetic-token-do-not-display",
            "CSV_PATH": "unused.csv",
            "XML_PATH": "unused.xml",
        },
    )


@pytest.fixture
def connection() -> MagicMock:
    value = MagicMock(spec=Connection)
    value.__enter__.return_value = value
    return value


def test_migration_connects_immediately_without_waiting(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, connection: MagicMock
) -> None:
    factory = Mock(return_value=connection)
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    assert db._connect_for_migration(settings) is connection
    factory.assert_called_once()
    sleep.assert_not_called()
    connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SET time_zone = '+00:00'"
    )
    connection.close.assert_not_called()


@pytest.mark.parametrize("code", [2003, 2006, 2013, 1053])
def test_transient_opening_error_is_retried(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, connection: MagicMock, code: int
) -> None:
    factory = Mock(side_effect=[pymysql.OperationalError(code, "synthetic-secret"), connection])
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    assert db._connect_for_migration(settings) is connection
    assert factory.call_count == 2
    sleep.assert_called_once_with(1)


def test_connection_retry_exhaustion_is_bounded_and_preserves_error(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    failure = pymysql.OperationalError(2003, "synthetic-secret")
    factory = Mock(side_effect=failure)
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    with pytest.raises(pymysql.OperationalError) as error:
        db._connect_for_migration(settings)
    assert error.value is failure
    assert factory.call_count == 6
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4, 8, 10]


@pytest.mark.parametrize("failed_attempts", [1, 2, 3, 4, 5])
def test_success_after_transient_failures_stops_retrying(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    connection: MagicMock,
    failed_attempts: int,
) -> None:
    factory = Mock(
        side_effect=[pymysql.OperationalError(2003, "synthetic-secret")] * failed_attempts
        + [connection]
    )
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    assert db._connect_for_migration(settings) is connection
    assert factory.call_count == failed_attempts + 1
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4, 8, 10][:failed_attempts]


@pytest.mark.parametrize("code", [1045, 1049, 1064, 1205, 1213])
def test_permanent_or_sql_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, code: int
) -> None:
    failure = pymysql.OperationalError(code, "synthetic-secret")
    factory = Mock(side_effect=failure)
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    with pytest.raises(pymysql.OperationalError) as error:
        db._connect_for_migration(settings)
    assert error.value is failure
    factory.assert_called_once()
    sleep.assert_not_called()


def test_unexpected_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    factory = Mock(side_effect=RuntimeError("synthetic-secret"))
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    with pytest.raises(RuntimeError):
        db._connect_for_migration(settings)
    factory.assert_called_once()
    sleep.assert_not_called()


def test_failed_session_initialization_closes_connection(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, connection: MagicMock
) -> None:
    failure = pymysql.OperationalError(2013, "synthetic-secret")
    connection.cursor.return_value.__enter__.return_value.execute.side_effect = failure
    monkeypatch.setattr(db.pymysql, "connect", Mock(return_value=connection))

    with pytest.raises(pymysql.OperationalError) as error:
        db.connect(settings)
    assert error.value is failure
    connection.close.assert_called_once()


@pytest.mark.parametrize("code", [2003, 2006, 2013, 1053])
def test_ordinary_connection_keeps_one_attempt(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, code: int
) -> None:
    factory = Mock(side_effect=pymysql.OperationalError(code, "synthetic-secret"))
    sleep = Mock()
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db.time, "sleep", sleep)

    with pytest.raises(pymysql.OperationalError):
        db.connect(settings)
    factory.assert_called_once()
    sleep.assert_not_called()


def test_retry_log_has_context_without_driver_text_or_credentials(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    settings: Settings,
    connection: MagicMock,
) -> None:
    logger = logging.getLogger("src.db")
    monkeypatch.setattr(logger, "handlers", [caplog.handler])
    monkeypatch.setattr(logger, "propagate", False)
    caplog.set_level(logging.WARNING, logger="src.db")
    monkeypatch.setattr(
        db.pymysql,
        "connect",
        Mock(side_effect=[pymysql.OperationalError(2003, "synthetic-secret"), connection]),
    )
    monkeypatch.setattr(db.time, "sleep", Mock())

    db._connect_for_migration(settings)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "WARNING" and record.run_id == "-"
    assert "2003" in record.getMessage() and "1/6" in record.getMessage()
    for private_text in (
        "synthetic-secret",
        settings.db_password,
        settings.db_user,
        settings.db_host,
    ):
        assert private_text not in caplog.text


def test_migrate_does_not_retry_sql_after_connection_succeeds(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, connection: MagicMock
) -> None:
    factory = Mock(return_value=connection)
    migrate = Mock(side_effect=pymysql.OperationalError(2013, "synthetic-secret"))
    sleep = Mock()
    monkeypatch.setattr(sys, "argv", ["src.db", "migrate"])
    monkeypatch.setattr(db, "load_settings", Mock(return_value=settings))
    monkeypatch.setattr(db.pymysql, "connect", factory)
    monkeypatch.setattr(db, "apply_migration", migrate)
    monkeypatch.setattr(db.time, "sleep", sleep)

    assert db.main() == 1
    factory.assert_called_once()
    migrate.assert_called_once_with(connection)
    sleep.assert_not_called()
