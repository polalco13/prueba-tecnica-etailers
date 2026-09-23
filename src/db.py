"""Conexión MySQL y aplicación explícita de la migración versionada F4."""

import argparse
from pathlib import Path

import pymysql
from pymysql.connections import Connection

from src.config import Settings, configure_logging, get_run_logger, load_settings

MIGRATION_VERSION = "001_products_and_runs"
MIGRATION_PATH = Path(__file__).resolve().parent.parent / "db/migrations/001_products_and_runs.sql"


def connect(settings: Settings) -> Connection:
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")
    return connection


def schema_is_current(connection: Connection) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = 'schema_migrations'"
        )
        if cursor.fetchone()[0] == 0:
            return False
        cursor.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = %s", (MIGRATION_VERSION,)
        )
        return cursor.fetchone()[0] == 1


def apply_migration(connection: Connection) -> bool:
    """DDL idempotente bajo lock; no recrea ni borra tablas de un volumen existente."""

    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 10)", ("prueba_tecnica_schema",))
        if cursor.fetchone()[0] != 1:
            raise RuntimeError("No se pudo obtener bloqueo de migración")
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version VARCHAR(64) PRIMARY KEY, applied_at DATETIME(6) NOT NULL "
                "DEFAULT CURRENT_TIMESTAMP(6)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        if schema_is_current(connection):
            return False
        sql = "\n".join(
            line
            for line in MIGRATION_PATH.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("--")
        )
        with connection.cursor() as cursor:
            for statement in sql.split(";"):
                if statement.strip():
                    cursor.execute(statement)
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (MIGRATION_VERSION,)
            )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", ("prueba_tecnica_schema",))


def main() -> int:
    parser = argparse.ArgumentParser(description="Migraciones MySQL versionadas")
    parser.add_argument("command", choices=("migrate",))
    parser.parse_args()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        with connect(settings) as connection:
            applied = apply_migration(connection)
    except Exception as exc:
        get_run_logger("db").error("Migración no completada (%s)", type(exc).__name__)
        return 1
    get_run_logger("db").info(
        "Migración %s: %s", MIGRATION_VERSION, "aplicada" if applied else "ya aplicada"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
