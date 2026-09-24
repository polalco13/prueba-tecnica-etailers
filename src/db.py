"""Conexión MySQL y aplicación explícita de migraciones versionadas."""

import argparse
from pathlib import Path

import pymysql
from pymysql.connections import Connection

from src.config import Settings, configure_logging, get_run_logger, load_settings

MIGRATIONS = ("001_products_and_runs", "002_stock")
MIGRATION_DIR = Path(__file__).resolve().parent.parent / "db/migrations"


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
        cursor.execute("SELECT version FROM schema_migrations")
        return set(MIGRATIONS) <= {row[0] for row in cursor.fetchall()}


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
        applied = False
        with connection.cursor() as cursor:
            cursor.execute("SELECT version FROM schema_migrations")
            existing = {row[0] for row in cursor.fetchall()}
            for version in MIGRATIONS:
                if version in existing:
                    continue
                sql = "\n".join(
                    line
                    for line in (MIGRATION_DIR / f"{version}.sql").read_text().splitlines()
                    if not line.lstrip().startswith("--")
                )
                for statement in sql.split(";"):
                    if not statement.strip():
                        continue
                    if statement.strip().startswith("ALTER TABLE etl_runs ADD COLUMN stock_sha256"):
                        # DDL hace commit implícito: permite retomar F5 tras una interrupción.
                        cursor.execute(
                            "SELECT COUNT(*) FROM information_schema.columns "
                            "WHERE table_schema = DATABASE() AND table_name = 'etl_runs' "
                            "AND column_name = 'stock_sha256'"
                        )
                        if cursor.fetchone()[0]:
                            continue
                    cursor.execute(statement)
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
                connection.commit()
                applied = True
        return applied
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
        "Migraciones hasta %s: %s", MIGRATIONS[-1], "aplicadas" if applied else "ya aplicadas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
