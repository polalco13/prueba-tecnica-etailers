"""Entrega posterior al commit: cada invocación hace como máximo un POST.

Un timeout puede haber ejecutado destinos. El reenvío es explícito, con el
mismo resumen/run_id; no prometer exactamente una vez ni ocultar duplicados.
"""

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

import httpx

from src import db
from src.config import MakeOptions, Settings, get_run_logger
from src.etl.reporting import SUMMARY_VERSION

_POSTING_WEBHOOK: ContextVar[bool] = ContextVar("posting_make_webhook", default=False)


class _WebhookLogFilter(logging.Filter):
    """HTTPX registra la URL a INFO; ocultarla aunque el host active ese logger."""

    def filter(self, record: logging.LogRecord) -> bool:
        if _POSTING_WEBHOOK.get():
            record.msg = "Solicitud HTTP Make (URL omitida)"
            record.args = ()
        return True


logging.getLogger("httpx").addFilter(_WebhookLogFilter())


class DeliveryError(ValueError):
    """Error de precondición, con mensaje fijo sin valores externos."""


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str
    error_code: str | None = None


def post_summary(
    options: MakeOptions,
    payload: dict,
    transport: httpx.BaseTransport | None = None,
) -> DeliveryResult:
    """2xx acredita recepción HTTP, nunca la ejecución de Sheets/email."""

    if not options.webhook_url:
        raise DeliveryError("MAKE_WEBHOOK_URL no configurada")
    log_context = _POSTING_WEBHOOK.set(True)
    try:
        with httpx.Client(
            timeout=httpx.Timeout(options.timeout),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            with client.stream("POST", options.webhook_url, json=payload) as response:
                status = response.status_code
    except httpx.InvalidURL:
        return DeliveryResult("failed", "MAKE_INVALID_URL")
    except httpx.RequestError:
        # No registrar exc, request/response ni URL: contienen secretos del webhook.
        return DeliveryResult("uncertain", "MAKE_NETWORK_ERROR")
    finally:
        _POSTING_WEBHOOK.reset(log_context)
    if 200 <= status < 300:
        return DeliveryResult("accepted")
    return DeliveryResult("failed", f"MAKE_HTTP_{status}")


def deliver_run(
    settings: Settings,
    run_id: str,
    *,
    force: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> DeliveryResult:
    """Reenvía solo el JSON almacenado, sin recalcular métricas ni ejecutar ETL.

    Lock por run evita dos POST concurrentes; no hay transacción SQL abierta
    mientras se espera HTTP. Estado pending + intentos > 0 tras una caída
    implica resultado desconocido, revisable antes de reintentar.
    """

    try:
        run_id = str(UUID(run_id))
    except ValueError:
        raise DeliveryError("run_id debe ser un UUID") from None
    if not settings.make.webhook_url:
        raise DeliveryError("MAKE_WEBHOOK_URL no configurada")
    lock = "make:" + run_id
    with db.connect(settings) as connection:
        if not db.schema_is_current(connection):
            raise DeliveryError("Esquema pendiente: ejecutar python -m src.db migrate")
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", (lock,))
            if cursor.fetchone()[0] != 1:
                raise DeliveryError("Ya hay una entrega en curso para este run")
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT status, make_summary, make_status FROM etl_runs WHERE id = %s",
                    (run_id,),
                )
                row = cursor.fetchone()
                if row is None or row[0] != "completed" or row[1] is None:
                    raise DeliveryError("Run no completado o sin resumen F10 almacenado")
                payload = json.loads(row[1])
                if (
                    payload.get("schema_version") != SUMMARY_VERSION
                    or payload.get("run_id") != run_id
                ):
                    raise DeliveryError("Versión o identidad del resumen incompatible")
                if row[2] == "accepted" and not force:
                    get_run_logger("make", run_id).info(
                        "Recepción HTTP ya registrada; no se repite el POST sin --force"
                    )
                    return DeliveryResult("accepted")
                cursor.execute(
                    "UPDATE etl_runs SET make_status = 'pending', "
                    "make_attempts = make_attempts + 1, make_last_attempt_at = UTC_TIMESTAMP(6), "
                    "make_error_code = NULL WHERE id = %s",
                    (run_id,),
                )
            connection.commit()
            result = post_summary(settings.make, payload, transport)
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE etl_runs SET make_status = %s, make_error_code = %s, "
                    "make_accepted_at = CASE WHEN %s = 'accepted' THEN UTC_TIMESTAMP(6) "
                    "ELSE make_accepted_at END WHERE id = %s",
                    (result.status, result.error_code, result.status, run_id),
                )
            connection.commit()
            logger = get_run_logger("make", run_id)
            if result.status == "accepted":
                logger.info("Resumen recibido por HTTP; destinos pendientes de verificar en Make")
            else:
                logger.warning(
                    "Entrega %s (%s); reenvío explícito disponible",
                    result.status,
                    result.error_code,
                )
            return result
        finally:
            connection.rollback()
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (lock,))
