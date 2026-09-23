"""Incremento F4: catálogo y tarifas; publicación atómica con auditoría durable."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pymysql import MySQLError

from src import db
from src.config import Settings, get_run_logger
from src.etl import repository
from src.etl.catalog import CatalogReadError, extract_catalog
from src.etl.pricing import TariffReadError, load_tariffs, price_catalog
from src.etl.records import Action, Issue, ReasonCode, Severity, SourceRef
from src.etl.reporting import CatalogCounters, catalog_counters

LOCK_NAME = "prueba_tecnica_catalog_pricing"


class RunValidationError(ValueError):
    """Snapshot no publicable, sin incluir datos de las fuentes en el error."""

    def __init__(self, code: ReasonCode, ref: SourceRef) -> None:
        self.code = code
        self.ref = ref
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str
    counters: CatalogCounters


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_hash(path: Path, source: str) -> str:
    try:
        return _sha256(path)
    except OSError:
        raise RunValidationError(ReasonCode.SOURCE_READ_FAILED, SourceRef(source, "/")) from None


def _failure_issue(exc: Exception) -> Issue:
    if isinstance(exc, (CatalogReadError, TariffReadError, RunValidationError)):
        ref = exc.ref
        code = exc.code
    elif isinstance(exc, MySQLError):
        ref = SourceRef("mysql", "/")
        code = ReasonCode.DATABASE_ERROR
    else:
        ref = SourceRef("etl", "/")
        code = ReasonCode.UNEXPECTED_ERROR
    return Issue(ref, code, Action.FAIL_RUN, Severity.ERROR, f"Ejecución fallida: {code}")


def run_catalog_pricing(settings: Settings) -> RunResult:
    """Un único escritor; crea run durable y publica catálogo/ítems juntos."""

    run_id = str(uuid4())
    logger = get_run_logger("etl", run_id)
    with db.connect(settings) as connection:
        if not db.schema_is_current(connection):
            raise RuntimeError("Esquema pendiente: ejecutar python -m src.db migrate")
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", (LOCK_NAME,))
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Ya hay una carga de catálogo en curso")
        try:
            repository.start_run(connection, run_id)
            issues: tuple[Issue, ...] = ()
            try:
                csv_hash = _source_hash(settings.csv_path, "catalog_csv")
                xml_hash = _source_hash(settings.xml_path, "tariffs_xml")
                batch = extract_catalog(settings.csv_path)
                issues = batch.issues
                tariffs = load_tariffs(settings.xml_path)
                priced = price_catalog(batch, tariffs)
                issues = priced.issues
                if not priced.products:
                    raise RunValidationError(
                        ReasonCode.EMPTY_CATALOG, SourceRef("catalog_csv", "/")
                    )
                counters = catalog_counters(priced)
                if csv_hash != _source_hash(settings.csv_path, "catalog_csv"):
                    raise RunValidationError(
                        ReasonCode.SOURCE_CHANGED, SourceRef("catalog_csv", "/")
                    )
                if xml_hash != _source_hash(settings.xml_path, "tariffs_xml"):
                    raise RunValidationError(
                        ReasonCode.SOURCE_CHANGED, SourceRef("tariffs_xml", "/")
                    )
                logger.info("Extracción validada: %d productos", len(priced.products))
                repository.mark_publishing(connection, run_id, csv_hash, xml_hash)
                repository.publish_catalog(connection, run_id, priced)
                repository.insert_issues(connection, run_id, issues)
                repository.complete_run(connection, run_id, counters, csv_hash, xml_hash)
                connection.commit()
                logger.info("Catálogo publicado")
                return RunResult(run_id, counters)
            except Exception as exc:
                connection.rollback()
                failure = _failure_issue(exc)
                try:
                    repository.fail_run(
                        connection, run_id, str(failure.reason_code), (*issues, failure)
                    )
                except Exception:
                    connection.rollback()
                    logger.error("No se pudo completar la auditoría del fallo")
                logger.error("Carga fallida: %s", failure.reason_code)
                raise
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
