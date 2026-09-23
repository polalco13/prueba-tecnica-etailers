"""Casos sintéticos independientes de los ficheros del proveedor."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.etl.normalize import (
    comparison_key,
    is_missing,
    normalize_channel,
    normalize_ean,
    normalize_identifier,
    normalize_status,
    normalize_text,
    parse_date,
    parse_decimal,
    parse_discount,
    parse_money,
    parse_quantity,
    parse_timestamp,
    require_text,
    round_decimal,
)
from src.etl.records import NormalizationError, ReasonCode


@pytest.mark.parametrize("raw", [None, "", "   ", "N/D", "NULL", "-", "n/a", " N/a "])
def test_missing_tokens_are_complete_values(raw: str | None) -> None:
    assert is_missing(raw)
    assert normalize_text(raw) is None


def test_text_and_identifier_normalization() -> None:
    assert normalize_text("  CAFE\u0301   DEL  NORTE  ") == "CAFÉ DEL NORTE"
    assert comparison_key("  FONTANERÍA ") == comparison_key("fontanería")
    assert normalize_identifier(" prv-012 ", "sku") == "PRV-012"
    assert not is_missing("PRV-012")
    assert require_text(" Tornillo ", "nombre") == "Tornillo"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("N/D", ReasonCode.MISSING_REQUIRED_FIELD),
        ("A" * 65, ReasonCode.INVALID_IDENTIFIER),
        ("PRV-1\nX", ReasonCode.INVALID_IDENTIFIER),
    ],
)
def test_identifier_rejects_missing_or_unsafe(raw: str, code: ReasonCode) -> None:
    with pytest.raises(NormalizationError) as error:
        normalize_identifier(raw, "sku")
    assert error.value.code == code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("17,022", Decimal("17.022")),
        ("1.997", Decimal("1.997")),
        ("-2,5", Decimal("-2.5")),
        ("0", Decimal("0")),
        ("n/a", None),
    ],
)
def test_decimal_without_money_grouping(raw: str, expected: Decimal | None) -> None:
    assert parse_decimal(raw) == expected


@pytest.mark.parametrize("raw", ["1.234,56", "NaN", "Infinity", "1e3", "12,34,56"])
def test_decimal_rejects_grouping_or_non_finite_values(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_decimal(raw)
    assert error.value.code == ReasonCode.INVALID_DECIMAL


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30,38", Decimal("30.38")),
        ("30.38", Decimal("30.38")),
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("1 234,56 €", Decimal("1234.56")),
        ("€ 123,45", Decimal("123.45")),
        ("123,45 EUR", Decimal("123.45")),
        ("250", Decimal("250")),
        ("0,0001", Decimal("0.0001")),
        ("N/D", None),
    ],
)
def test_money_uses_unambiguous_decimal_grammar(raw: str, expected: Decimal | None) -> None:
    assert parse_money(raw) == expected


@pytest.mark.parametrize("raw", ["1.234", "1,234"])
def test_money_rejects_single_ambiguous_separator(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_money(raw)
    assert error.value.code == ReasonCode.AMBIGUOUS_NUMBER


@pytest.mark.parametrize("raw", ["12,34,56", "$10", "1e3", "1.2.3", "1,23456", "NaN"])
def test_money_rejects_invalid_forms(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_money(raw)
    assert error.value.code == ReasonCode.INVALID_PRICE


@pytest.mark.parametrize("raw", ["0", "0,00", "-1,50"])
def test_non_positive_money_is_rejected(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_money(raw)
    assert error.value.code == ReasonCode.NON_POSITIVE_PRICE


def test_money_rejects_database_overflow() -> None:
    with pytest.raises(NormalizationError) as error:
        parse_money("100000000000000")
    assert error.value.code == ReasonCode.NUMERIC_OUT_OF_RANGE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10%", Decimal("0.10")),
        ("10", Decimal("0.10")),
        ("0,1", Decimal("0.1")),
        ("1", Decimal("0.01")),
        ("100%", Decimal("1")),
        ("0", Decimal("0")),
        ("0,5%", Decimal("0.005")),
        ("", None),
    ],
)
def test_discount_scales_are_explicit(raw: str, expected: Decimal | None) -> None:
    assert parse_discount(raw) == expected


@pytest.mark.parametrize("raw", ["101", "-1", "10%%", "NaN", "0,1234567"])
def test_discount_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_discount(raw)
    assert error.value.code == ReasonCode.INVALID_DISCOUNT


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2", 2), ("2,0", 2), ("2.0", 2), ("-3", -3), ("-3,0", -3), ("N/D", None)],
)
def test_quantity_keeps_only_exact_integers(raw: str, expected: int | None) -> None:
    assert parse_quantity(raw) == expected


@pytest.mark.parametrize("raw", ["0", "2,5", "2e0", "9223372036854775808", "9" * 5000])
def test_quantity_rejects_zero_fraction_or_overflow(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_quantity(raw)
    assert error.value.code == ReasonCode.INVALID_QUANTITY


def test_round_half_up_is_decimal_only() -> None:
    assert round_decimal(Decimal("1.005"), 2) == Decimal("1.01")
    assert round_decimal(Decimal("-1.005"), 2) == Decimal("-1.01")
    assert round_decimal(Decimal("1.23445"), 4) == Decimal("1.2345")
    with pytest.raises(ValueError):
        round_decimal(1.005, 2)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "raw",
    [
        "2025-04-19",
        "19/04/2025",
        "19-04-2025",
        "2025/04/19",
        "2025-04-19 19:57:00",
        "19-04-2025 19:57:00",
    ],
)
def test_order_date_formats_map_to_same_day(raw: str) -> None:
    assert parse_date(raw) == date(2025, 4, 19)


def test_date_with_offset_uses_business_timezone() -> None:
    assert parse_date("2026-09-23T23:30:00Z", "Europe/Madrid") == date(2026, 9, 24)
    assert parse_date("n/a") is None
    assert parse_date("29/02/2024") == date(2024, 2, 29)


@pytest.mark.parametrize("raw", ["31/02/2025", "04/19/2025", "2025-13-01", "unknown"])
def test_invalid_dates_are_not_guessed(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        parse_date(raw)
    assert error.value.code == ReasonCode.INVALID_DATE


def test_stock_timestamp_requires_zone_and_returns_utc() -> None:
    assert parse_timestamp("2026-09-23T12:00:00+02:00") == datetime(
        2026, 9, 23, 10, 0, tzinfo=timezone.utc
    )
    assert parse_timestamp("2026-09-23T10:00:00Z") == datetime(
        2026, 9, 23, 10, 0, tzinfo=timezone.utc
    )
    with pytest.raises(NormalizationError) as error:
        parse_timestamp("2026-09-23T10:00:00")
    assert error.value.code == ReasonCode.INVALID_DATE


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMPLETADO", "COMPLETADO"),
        ("Completado", "COMPLETADO"),
        ("completado", "COMPLETADO"),
        ("enviado", "ENVIADO"),
        ("PENDIENTE", "PENDIENTE"),
        ("cancelado", "CANCELADO"),
        ("DEVUELTO", "DEVUELTO"),
        ("N/D", None),
    ],
)
def test_observed_statuses(raw: str, expected: str | None) -> None:
    assert normalize_status(raw) == expected


@pytest.mark.parametrize("raw", ["facturado", "devolución parcial"])
def test_unknown_status_is_not_mapped_by_guessing(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        normalize_status(raw)
    assert error.value.code == ReasonCode.UNKNOWN_ORDER_STATUS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("B2B", "B2B"),
        ("b2b", "B2B"),
        ("B2C", "B2C"),
        ("b2c", "B2C"),
        ("Marketplace", "marketplace"),
        ("MARKETPLACE", "marketplace"),
        ("N/D", None),
    ],
)
def test_observed_channels(raw: str, expected: str | None) -> None:
    assert normalize_channel(raw) == expected


def test_unknown_channel_is_not_mapped_by_guessing() -> None:
    with pytest.raises(NormalizationError) as error:
        normalize_channel("tienda")
    assert error.value.code == ReasonCode.UNKNOWN_CHANNEL


@pytest.mark.parametrize(
    "raw",
    ["4006381333931", "'4006381333931", '"4006381333931"', "4006 3813 33931"],
)
def test_ean13_cleanup_and_checksum(raw: str) -> None:
    assert normalize_ean(raw) == "4006381333931"


def test_ean8_and_missing() -> None:
    assert normalize_ean("96385074") == "96385074"
    assert normalize_ean("N/D") is None


@pytest.mark.parametrize("raw", ["4006381333932", "400638133393", "abc", "１２３４５６７８"])
def test_invalid_ean_is_not_reconstructed(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        normalize_ean(raw)
    assert error.value.code == ReasonCode.INVALID_EAN


@pytest.mark.parametrize("raw", ["8,461061067530E+12", "8E12"])
def test_scientific_ean_has_distinct_reason(raw: str) -> None:
    with pytest.raises(NormalizationError) as error:
        normalize_ean(raw)
    assert error.value.code == ReasonCode.UNSAFE_SCIENTIFIC_EAN
