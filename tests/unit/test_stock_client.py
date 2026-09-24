"""HTTP completamente sintético, reloj controlado; nunca usa token ni API locales."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from src.config import Settings, StockOptions
from src.etl.stock_client import StockFetchError, fetch_stock


def settings(**options: int) -> Settings:
    return Settings(
        "unused",
        3306,
        "unused",
        "unused",
        "synthetic-db-secret",
        "https://stock.example.test/api/v1/stock",
        "synthetic-token",
        Path("unused"),
        Path("unused"),
        Path("unused"),
        "UTC",
        "ERROR",
        replace(StockOptions(), **options),
    )


def page(rows: list, number: int = 1, size: int = 50, total: int | None = None) -> dict:
    count = len(rows) if total is None else total
    pages = (count + size - 1) // size
    return {
        "data": rows,
        "meta": {
            "page": number,
            "per_page": size,
            "total_records": count,
            "total_pages": pages,
            "has_next": number < pages,
        },
    }


class Clock:
    elapsed = 0.0

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.elapsed += seconds

    def monotonic(self) -> float:
        return self.elapsed

    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=self.elapsed)


def fetch(handler, clock: Clock | None = None, **options: int):
    clock = clock or Clock()
    return fetch_stock(
        settings(**options),
        "synthetic-run",
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=clock.now,
        jitter=lambda: 0,
    )


def test_complete_pages_auth_rate_and_hash() -> None:
    requests = []
    clock = Clock()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request, clock.elapsed))
        number = int(request.url.params["page"])
        assert request.headers["Authorization"] == "Bearer synthetic-token"
        assert "updated_since" not in request.url.params
        assert request.extensions["timeout"]["connect"] == 5
        assert request.extensions["timeout"]["read"] == 15
        return httpx.Response(200, json=page([{"sku": str(number)}], number, 1, 3))

    result = fetch(handler, clock, per_page=1)
    assert [row.payload["sku"] for row in result.rows] == ["1", "2", "3"]
    assert [row.ref.locator for row in result.rows] == [f"page:{n}/row:1" for n in (1, 2, 3)]
    assert [instant for _, instant in requests] == [0, 2, 4]
    assert len(result.sha256) == 64
    assert fetch(handler, per_page=1).sha256 == result.sha256


def test_complete_empty_snapshot() -> None:
    assert fetch(lambda _: httpx.Response(200, json=page([]))).rows == ()


@pytest.mark.parametrize("status", [401, 403, 404, 302])
def test_permanent_errors_do_not_retry_or_leak_response(status: int) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status, text="synthetic-token", headers={"Location": "https://other.test"}
        )

    with pytest.raises(StockFetchError, match=f"HTTP {status}") as error:
        fetch(handler)
    assert len(calls) == 1
    assert "synthetic-token" not in str(error.value)


@pytest.mark.parametrize("failure", [500, 429, "timeout", "network"])
def test_transient_errors_retry_with_pacing(failure: int | str) -> None:
    clock = Clock()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(clock.elapsed)
        if len(calls) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("synthetic-token", request=request)
            if failure == "network":
                raise httpx.ConnectError("synthetic-token", request=request)
            return httpx.Response(failure, headers={"Retry-After": "5"})
        return httpx.Response(200, json=page([]))

    fetch(handler, clock)
    assert calls == [0, 5 if failure == 429 else 2]


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Thu, 01 Jan 2026 00:00:45 GMT", 45),
        ("45", 45),
        ("bad", 2),
        ("-10", 2),
        ("Thu, 01 Jan 2020 00:00:00 GMT", 2),
    ],
)
def test_retry_after_is_a_minimum_not_capped(header: str, expected: int) -> None:
    clock = Clock()
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": header}),
            httpx.Response(200, json=page([])),
        ]
    )
    fetch(lambda _: next(responses), clock)
    assert clock.elapsed == expected


def test_retry_after_exceeding_budget_fails_without_early_request() -> None:
    clock = Clock()
    with pytest.raises(StockFetchError, match="presupuesto"):
        fetch(lambda _: httpx.Response(429, headers={"Retry-After": "301"}), clock)
    assert clock.elapsed == 0


def test_exhausted_retries_are_bounded() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    with pytest.raises(StockFetchError, match="reintentos agotados"):
        fetch(handler)
    assert len(calls) == 5


@pytest.mark.parametrize(
    "changes",
    [
        {"page": 2},
        {"per_page": 49},
        {"total_records": -1},
        {"total_pages": 2},
        {"has_next": True},
        {"has_next": 0},
        {"page": True},
    ],
)
def test_inconsistent_metadata(changes: dict) -> None:
    body = page([{}])
    body["meta"].update(changes)
    with pytest.raises(StockFetchError):
        fetch(lambda _: httpx.Response(200, json=body))


@pytest.mark.parametrize(
    "body", [{}, [], {"data": {}}, {"data": [], "meta": {}}, page([], total=1)]
)
def test_invalid_shape_or_incomplete_page(body: object) -> None:
    with pytest.raises(StockFetchError):
        fetch(lambda _: httpx.Response(200, json=body))


def test_malformed_json() -> None:
    with pytest.raises(StockFetchError, match="JSON"):
        fetch(lambda _: httpx.Response(200, text="not-json"))


@pytest.mark.parametrize("repeated", [True, False])
def test_repeated_page_or_changed_total_fails(repeated: bool) -> None:
    responses = iter(
        [
            page([{"sku": "A"}], 1, 1, 2),
            page([{"sku": "A" if repeated else "B"}], 2, 1, 2 if repeated else 3),
        ]
    )
    with pytest.raises(StockFetchError):
        fetch(lambda _: httpx.Response(200, json=next(responses)), per_page=1)


def test_budget_includes_successful_request_time() -> None:
    clock = Clock()

    def handler(_: httpx.Request) -> httpx.Response:
        clock.sleep(301)
        return httpx.Response(200, json=page([]))

    with pytest.raises(StockFetchError, match="presupuesto"):
        fetch(handler, clock)


def test_oversleep_does_not_start_a_request_after_deadline() -> None:
    clock = Clock()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    with pytest.raises(StockFetchError, match="presupuesto"):
        fetch_stock(
            settings(),
            "synthetic-run",
            transport=httpx.MockTransport(handler),
            sleep=lambda _: clock.sleep(301),
            monotonic=clock.monotonic,
            jitter=lambda: 0,
        )
    assert len(calls) == 1


def test_json_decimal_quantity_keeps_exact_value() -> None:
    from decimal import Decimal

    result = fetch(
        lambda _: httpx.Response(
            200,
            text=(
                '{"data":[{"quantity":9007199254740993.0}],"meta":'
                '{"page":1,"per_page":50,"total_records":1,"total_pages":1,"has_next":false}}'
            ),
        )
    )
    assert result.rows[0].payload["quantity"] == Decimal("9007199254740993")
