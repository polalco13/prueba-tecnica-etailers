"""Normalizadores puros para los formatos observados en las fuentes."""

import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from src.etl.records import NormalizationError, ReasonCode

_SENTINELS = frozenset({"", "n/d", "null", "-", "n/a"})
_SIMPLE_DECIMAL = re.compile(r"[+-]?\d+(?:[.,]\d+)?\Z")
_ISO_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z")
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")
_ORDER_STATUSES = frozenset({"COMPLETADO", "ENVIADO", "PENDIENTE", "CANCELADO", "DEVUELTO"})
_CHANNELS = {"b2b": "B2B", "b2c": "B2C", "marketplace": "marketplace"}
_MAX_MONEY = Decimal("99999999999999.9999")  # DECIMAL(18,4)
_MAX_QUANTITY = 2**63 - 1  # BIGINT firmado


def _text(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("Se esperaba texto o None")
    return value.strip()


def is_missing(value: str | None) -> bool:
    return _text(value).casefold() in _SENTINELS


def normalize_text(value: str | None) -> str | None:
    if is_missing(value):
        return None
    return " ".join(unicodedata.normalize("NFC", _text(value)).split())


def comparison_key(value: str | None) -> str | None:
    normalized = normalize_text(value)
    return None if normalized is None else normalized.casefold()


def require_text(value: str | None, field_name: str) -> str:
    normalized = normalize_text(value)
    if normalized is None:
        raise NormalizationError(ReasonCode.MISSING_REQUIRED_FIELD, field_name)
    return normalized


def normalize_identifier(value: str | None, field_name: str = "identifier") -> str:
    if value is not None and any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise NormalizationError(ReasonCode.INVALID_IDENTIFIER, field_name)
    normalized = require_text(value, field_name).upper()
    if len(normalized) > 64:
        raise NormalizationError(ReasonCode.INVALID_IDENTIFIER, field_name)
    return normalized


def parse_decimal(value: str | None) -> Decimal | None:
    """Decimal genérico, sin moneda ni separadores de miles."""

    if is_missing(value):
        return None
    raw = _text(value)
    if not _SIMPLE_DECIMAL.fullmatch(raw):
        raise NormalizationError(ReasonCode.INVALID_DECIMAL)
    try:
        number = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise NormalizationError(ReasonCode.INVALID_DECIMAL) from exc
    if not number.is_finite():
        raise NormalizationError(ReasonCode.INVALID_DECIMAL)
    return number


def _strip_currency(value: str) -> str:
    raw = value.strip()
    if raw.startswith("€"):
        raw = raw[1:].strip()
    elif raw[:3].upper() == "EUR":
        raw = raw[3:].strip()
    if raw.endswith("€"):
        raw = raw[:-1].strip()
    elif raw[-3:].upper() == "EUR":
        raw = raw[:-3].strip()
    return raw


def _money_digits(raw: str) -> str:
    raw = raw.replace("\u00a0", " ").replace("\u202f", " ")
    if " " in raw:
        if not re.fullmatch(r"[+-]?\d{1,3}(?: \d{3})+(?:[.,]\d{1,4})?", raw):
            raise NormalizationError(ReasonCode.INVALID_PRICE)
        raw = raw.replace(" ", "")

    if "," in raw and "." in raw:
        decimal_sep = "," if raw.rfind(",") > raw.rfind(".") else "."
        group_sep = "." if decimal_sep == "," else ","
        pattern = rf"[+-]?\d{{1,3}}(?:\{group_sep}\d{{3}})+\{decimal_sep}\d{{1,4}}"
        if not re.fullmatch(pattern, raw):
            raise NormalizationError(ReasonCode.INVALID_PRICE)
        return raw.replace(group_sep, "").replace(decimal_sep, ".")

    for separator in (",", "."):
        if separator not in raw:
            continue
        if raw.count(separator) > 1:
            pattern = rf"[+-]?\d{{1,3}}(?:\{separator}\d{{3}})+"
            if not re.fullmatch(pattern, raw):
                raise NormalizationError(ReasonCode.INVALID_PRICE)
            return raw.replace(separator, "")
        left, right = raw.split(separator)
        if len(right) == 3 and re.fullmatch(r"[+-]?\d+", left):
            raise NormalizationError(ReasonCode.AMBIGUOUS_NUMBER)
        if not re.fullmatch(r"[+-]?\d+", left) or not re.fullmatch(r"\d{1,4}", right):
            raise NormalizationError(ReasonCode.INVALID_PRICE)
        return left + "." + right

    if not re.fullmatch(r"[+-]?\d+", raw):
        raise NormalizationError(ReasonCode.INVALID_PRICE)
    return raw


def parse_money(value: str | None) -> Decimal | None:
    if is_missing(value):
        return None
    raw = _strip_currency(_text(value))
    number = Decimal(_money_digits(raw))
    if number <= 0:
        raise NormalizationError(ReasonCode.NON_POSITIVE_PRICE)
    if number > _MAX_MONEY:
        raise NormalizationError(ReasonCode.NUMERIC_OUT_OF_RANGE)
    return number


def parse_discount(value: str | None) -> Decimal | None:
    """Sin %: 0 <= x < 1 es ratio; 1 <= x <= 100 son puntos porcentuales."""

    if is_missing(value):
        return None
    raw = _text(value)
    marked_percent = raw.endswith("%")
    if marked_percent:
        raw = raw[:-1].strip()
    try:
        amount = parse_decimal(raw)
    except NormalizationError as exc:
        raise NormalizationError(ReasonCode.INVALID_DISCOUNT) from exc
    if amount is None or amount < 0 or amount > 100:
        raise NormalizationError(ReasonCode.INVALID_DISCOUNT)
    ratio = amount / 100 if marked_percent or amount >= 1 else amount
    if ratio > 1 or ratio != ratio.quantize(Decimal("0.000001")):
        raise NormalizationError(ReasonCode.INVALID_DISCOUNT)
    return ratio


def parse_quantity(value: str | None) -> int | None:
    if is_missing(value):
        return None
    try:
        amount = parse_decimal(value)
    except NormalizationError as exc:
        raise NormalizationError(ReasonCode.INVALID_QUANTITY) from exc
    if (
        amount is None
        or amount != amount.to_integral_value()
        or amount == 0
        or abs(amount) > _MAX_QUANTITY
    ):
        raise NormalizationError(ReasonCode.INVALID_QUANTITY)
    return int(amount)


def round_decimal(value: Decimal, places: int) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or not 0 <= places <= 6:
        raise ValueError("Decimal finito y escala entre 0 y 6 requeridos")
    unit = Decimal(1).scaleb(-places)
    return value.quantize(unit, rounding=ROUND_HALF_UP)


def parse_date(value: str | None, business_timezone: str = "Europe/Madrid") -> date | None:
    if is_missing(value):
        return None
    raw = _text(value)
    if _ISO_TIMESTAMP.fullmatch(raw):
        try:
            return (
                datetime.fromisoformat(raw.replace("Z", "+00:00"))
                .astimezone(ZoneInfo(business_timezone))
                .date()
            )
        except (ValueError, OverflowError) as exc:
            raise NormalizationError(ReasonCode.INVALID_DATE) from exc
    for fmt in _DATE_FORMATS:
        for suffix in ("", " %H:%M:%S", "T%H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt + suffix).date()
            except ValueError:
                continue
    raise NormalizationError(ReasonCode.INVALID_DATE)


def parse_timestamp(value: str | None) -> datetime | None:
    """Instante ISO con zona explícita, normalizado a UTC para el stock."""

    if is_missing(value):
        return None
    raw = _text(value)
    if not _ISO_TIMESTAMP.fullmatch(raw):
        raise NormalizationError(ReasonCode.INVALID_DATE)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise NormalizationError(ReasonCode.INVALID_DATE) from exc


def normalize_status(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    status = normalized.upper()
    if status not in _ORDER_STATUSES:
        raise NormalizationError(ReasonCode.UNKNOWN_ORDER_STATUS)
    return status


def normalize_channel(value: str | None) -> str | None:
    key = comparison_key(value)
    if key is None:
        return None
    try:
        return _CHANNELS[key]
    except KeyError as exc:
        raise NormalizationError(ReasonCode.UNKNOWN_CHANNEL) from exc


def normalize_ean(value: str | None) -> str | None:
    if is_missing(value):
        return None
    raw = _text(value)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    elif raw.startswith("'"):
        raw = raw[1:]
    raw = "".join(raw.split())
    if re.fullmatch(r"\d+(?:[.,]\d+)?[Ee][+-]?\d+", raw):
        raise NormalizationError(ReasonCode.UNSAFE_SCIENTIFIC_EAN)
    if not raw.isascii() or not raw.isdigit() or len(raw) not in (8, 13):
        raise NormalizationError(ReasonCode.INVALID_EAN)
    digits = [int(char) for char in raw]
    weights = (3, 1) if len(raw) == 8 else (1, 3)
    checksum = (
        10 - sum(digit * weights[index % 2] for index, digit in enumerate(digits[:-1])) % 10
    ) % 10
    if checksum != digits[-1]:
        raise NormalizationError(ReasonCode.INVALID_EAN)
    return raw
