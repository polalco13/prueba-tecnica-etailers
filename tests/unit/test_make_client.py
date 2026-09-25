"""F10: transporte completamente simulado, sin webhook ni destinatarios reales."""

import json
from types import SimpleNamespace

import httpx
import pytest

from src.config import MakeOptions
from src.etl import __main__ as cli
from src.etl.make_client import DeliveryError, DeliveryResult, post_summary
from src.etl.reporting import needs_alert


@pytest.mark.parametrize(
    "rejected,low_stock,threshold,expected",
    [(0, 0, 0, False), (1, 0, 0, True), (10, 0, 10, False), (11, 0, 10, True), (0, 1, 10, True)],
)
def test_alert_uses_strict_rejections_or_low_stock(
    rejected: int, low_stock: int, threshold: int, expected: bool
) -> None:
    assert needs_alert(rejected, low_stock, threshold) is expected


@pytest.mark.parametrize("values", [(-1, 0, 0), (0, -1, 0), (0, 0, -1)])
def test_negative_alert_inputs_are_invalid(values: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        needs_alert(*values)


@pytest.mark.parametrize("status", [200, 202, 204, 301, 302, 400, 401, 403, 429, 500])
def test_single_post_and_http_status_without_following_redirects(status: int) -> None:
    seen = []
    payload = {"run_id": "synthetic", "revenue_previous_month": "1234567890123456.78"}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.method == "POST"
        assert request.headers["content-type"] == "application/json"
        return httpx.Response(
            status, headers={"location": "https://other.invalid/secret"}, text="secret-response"
        )

    result = post_summary(
        MakeOptions("https://example.invalid/synthetic-secret"),
        payload,
        httpx.MockTransport(handler),
    )
    assert seen == [payload]
    assert result.status == ("accepted" if status < 300 else "failed")
    assert result.error_code == (None if status < 300 else f"MAKE_HTTP_{status}")
    assert "secret" not in repr(result)


@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError, httpx.WriteError])
def test_network_outcome_is_uncertain_and_is_not_retried_automatically(exception: type) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise exception("synthetic-secret-url")

    result = post_summary(
        MakeOptions("https://example.invalid/synthetic-secret"), {}, httpx.MockTransport(handler)
    )
    assert len(calls) == 1
    assert result == DeliveryResult("uncertain", "MAKE_NETWORK_ERROR")
    assert "secret" not in repr(result)


def test_disabled_url_cannot_accidentally_send() -> None:
    with pytest.raises(DeliveryError, match="no configurada"):
        post_summary(MakeOptions(), {})


def test_invalid_url_is_a_delivery_failure_without_exposing_it() -> None:
    result = post_summary(MakeOptions("https://example.invalid:bad/secret"), {})
    assert result == DeliveryResult("failed", "MAKE_INVALID_URL")


def test_httpx_logging_cannot_expose_secret_webhook(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="httpx"):
        result = post_summary(
            MakeOptions("https://example.invalid/secret-webhook-path"),
            {},
            httpx.MockTransport(lambda _: httpx.Response(200)),
        )
    assert result.status == "accepted"
    assert "URL omitida" in caplog.text
    assert "secret-webhook-path" not in caplog.text
    # El filtro no oculta los logs de otros clientes HTTP fuera de la entrega Make.
    caplog.clear()
    with (
        caplog.at_level("INFO", logger="httpx"),
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client,
    ):
        client.get("https://example.invalid/public")
    assert "/public" in caplog.text


@pytest.mark.parametrize("status,exit_code", [("accepted", 0), ("failed", 2), ("uncertain", 2)])
def test_resend_cli_does_not_execute_etl(
    monkeypatch: pytest.MonkeyPatch, status: str, exit_code: int
) -> None:
    calls = []
    monkeypatch.setattr(cli, "load_settings", lambda: SimpleNamespace(log_level="ERROR"))
    monkeypatch.setattr(cli, "run_etl", lambda *_: pytest.fail("Reenvío no debe cargar fuentes"))

    def deliver(settings: object, run_id: str, force: bool) -> DeliveryResult:
        calls.append((run_id, force))
        return DeliveryResult(status)

    monkeypatch.setattr(cli, "deliver_run", deliver)
    assert cli.main(["--resend-make", "synthetic", "--force"]) == exit_code
    assert calls == [("synthetic", True)]


def test_cli_delivery_failure_is_distinct_from_etl_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_settings", lambda: SimpleNamespace(log_level="ERROR"))
    counts = SimpleNamespace(rows_read=1, rows_accepted=1, rows_rejected=0, rows_deduplicated=0)
    result = SimpleNamespace(
        run_id="synthetic",
        counters=counts,
        stock_counters=counts,
        make_status="failed",
        orders_counters={
            "rows_read": 1,
            "rows_accepted": 1,
            "rows_rejected": 0,
            "rows_deduplicated": 0,
            "orders_loaded": 1,
            "partial_orders": 0,
        },
    )
    monkeypatch.setattr(cli, "run_etl", lambda _: result)
    assert cli.main([]) == 2

    def fail(_: object) -> None:
        raise RuntimeError("synthetic-secret")

    monkeypatch.setattr(cli, "run_etl", fail)
    assert cli.main([]) == 1
