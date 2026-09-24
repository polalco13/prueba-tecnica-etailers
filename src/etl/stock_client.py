"""Descarga completa de stock, sin SQL; fallos saneados y esperas acotadas."""

import hashlib
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime

import httpx

from src.config import Settings, get_run_logger
from src.etl.records import ReasonCode, SourceRecord, SourceRef


class StockFetchError(ValueError):
    code = ReasonCode.STOCK_FETCH_FAILED

    def __init__(self, page: int, detail: str) -> None:
        self.ref = SourceRef("stock_api", f"page:{page}")
        super().__init__(f"STOCK_FETCH_FAILED: {detail}")


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    rows: tuple[SourceRecord[object], ...]
    sha256: str


def _retry_after(value: str | None, now: datetime) -> float:
    if value is None:
        return 0
    if value.strip().isascii() and value.strip().isdigit():
        return float(value.strip())
    try:
        instant = parsedate_to_datetime(value)
        if instant.tzinfo is None:
            return 0
        return max(0, (instant - now).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return 0


def _page_data(response: httpx.Response, page: int, size: int) -> tuple[list[object], int]:
    try:
        body = response.json(parse_float=Decimal)
    except (ValueError, UnicodeError):
        raise StockFetchError(page, "JSON inválido") from None
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise StockFetchError(page, "estructura inválida")
    meta = body.get("meta")
    if not isinstance(meta, dict) or any(
        type(meta.get(key)) is not int
        for key in ("page", "per_page", "total_records", "total_pages")
    ):
        raise StockFetchError(page, "metadatos inválidos")
    total = meta["total_records"]
    pages = (total + size - 1) // size
    expected_size = min(size, max(0, total - (page - 1) * size))
    if (
        total < 0
        or meta["page"] != page
        or meta["per_page"] != size
        or meta["total_pages"] != pages
        or page > max(1, pages)
        or type(meta.get("has_next")) is not bool
        or meta["has_next"] != (page < pages)
        or len(body["data"]) != expected_size
    ):
        raise StockFetchError(page, "página incompleta o metadatos contradictorios")
    return body["data"], total


def fetch_stock(
    settings: Settings,
    run_id: str,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    jitter: Callable[[], float] = random.random,
) -> StockSnapshot:
    options = settings.stock
    logger = get_run_logger("stock", run_id)
    deadline = monotonic() + options.budget_seconds
    next_request = monotonic()
    digest = hashlib.sha256()
    rows: list[SourceRecord[object]] = []
    seen_pages: set[str] = set()
    expected_total: int | None = None
    page = 1
    with httpx.Client(
        headers={"Authorization": f"Bearer {settings.stock_api_token}"},
        follow_redirects=False,
        transport=transport,
        trust_env=False,
    ) as client:
        while True:
            for attempt in range(options.attempts):
                wait = max(0, next_request - monotonic())
                if monotonic() + wait >= deadline:
                    raise StockFetchError(page, "presupuesto de tiempo agotado")
                if wait:
                    sleep(wait)
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise StockFetchError(page, "presupuesto de tiempo agotado")
                next_request = monotonic() + 60 / options.requests_per_minute
                response = None
                try:
                    response = client.get(
                        settings.stock_api_url,
                        params={"page": page, "per_page": options.per_page},
                        timeout=httpx.Timeout(
                            min(options.read_timeout, remaining),
                            connect=min(options.connect_timeout, remaining),
                        ),
                    )
                except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                    pass
                except httpx.HTTPError:
                    raise StockFetchError(page, "respuesta o transporte no recuperable") from None
                if monotonic() >= deadline:
                    raise StockFetchError(page, "presupuesto de tiempo agotado")
                if response is not None and response.status_code == 200:
                    break
                if response is not None and response.status_code not in {429, 500}:
                    raise StockFetchError(page, f"HTTP {response.status_code}")
                if attempt + 1 == options.attempts:
                    raise StockFetchError(page, "reintentos agotados")
                delay = min(30, 2**attempt + jitter())
                if response is not None and response.status_code == 429:
                    delay = max(delay, _retry_after(response.headers.get("Retry-After"), now()))
                next_request = max(next_request, monotonic() + delay)
                logger.warning("Reintento de stock: página=%d intento=%d", page, attempt + 2)
            data, total = _page_data(response, page, options.per_page)
            if expected_total is not None and total != expected_total:
                raise StockFetchError(page, "total cambió entre páginas")
            expected_total = total
            fingerprint = hashlib.sha256(
                json.dumps(data, sort_keys=True, default=str).encode()
            ).hexdigest()
            if fingerprint in seen_pages:
                raise StockFetchError(page, "respuesta repetida")
            seen_pages.add(fingerprint)
            digest.update(len(response.content).to_bytes(8, "big"))
            digest.update(response.content)
            rows.extend(
                SourceRecord(SourceRef("stock_api", f"page:{page}/row:{index}"), row)
                for index, row in enumerate(data, 1)
            )
            if len(rows) == total:
                logger.info("Stock descargado: páginas=%d filas=%d", page, total)
                return StockSnapshot(tuple(rows), digest.hexdigest())
            page += 1
