"""Contratos pequeños para conservar procedencia e incidencias."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, TypeVar


class Action(StrEnum):
    NORMALIZE = "normalize"
    REJECT_ROW = "reject_row"
    DROP_FIELD = "drop_field"
    DEDUPLICATE = "deduplicate"
    WARN = "warn"
    FAIL_RUN = "fail_run"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReasonCode(StrEnum):
    INVALID_ENCODING = "INVALID_ENCODING"
    INVALID_CSV = "INVALID_CSV"
    INVALID_HEADER = "INVALID_HEADER"
    INVALID_COLUMN_COUNT = "INVALID_COLUMN_COUNT"
    SOURCE_READ_FAILED = "SOURCE_READ_FAILED"
    SOURCE_CHANGED = "SOURCE_CHANGED"
    EMPTY_CATALOG = "EMPTY_CATALOG"
    DATABASE_ERROR = "DATABASE_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    INVALID_DECIMAL = "INVALID_DECIMAL"
    INVALID_PRICE = "INVALID_PRICE"
    AMBIGUOUS_NUMBER = "AMBIGUOUS_NUMBER"
    NON_POSITIVE_PRICE = "NON_POSITIVE_PRICE"
    NUMERIC_OUT_OF_RANGE = "NUMERIC_OUT_OF_RANGE"
    INVALID_DISCOUNT = "INVALID_DISCOUNT"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_DATE = "INVALID_DATE"
    INVALID_EAN = "INVALID_EAN"
    UNSAFE_SCIENTIFIC_EAN = "UNSAFE_SCIENTIFIC_EAN"
    INVALID_TAX = "INVALID_TAX"
    INVALID_WEIGHT = "INVALID_WEIGHT"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    CONFLICTING_PRODUCT_SKU = "CONFLICTING_PRODUCT_SKU"
    INVALID_XML = "INVALID_XML"
    INVALID_TARIFF = "INVALID_TARIFF"
    CONFLICTING_TARIFF = "CONFLICTING_TARIFF"
    INVALID_EXCEPTION_PRICE = "INVALID_EXCEPTION_PRICE"
    UNKNOWN_PRODUCT_SKU = "UNKNOWN_PRODUCT_SKU"
    STOCK_FETCH_FAILED = "STOCK_FETCH_FAILED"
    INVALID_STOCK = "INVALID_STOCK"
    CONFLICTING_STOCK = "CONFLICTING_STOCK"
    SUPERSEDED_STOCK = "SUPERSEDED_STOCK"
    STOCK_NOT_OBSERVED = "STOCK_NOT_OBSERVED"
    RESERVED_EXCEEDS_QUANTITY = "RESERVED_EXCEEDS_QUANTITY"
    UNAPPLIED_TARIFF_TERM = "UNAPPLIED_TARIFF_TERM"
    UNKNOWN_ORDER_STATUS = "UNKNOWN_ORDER_STATUS"
    UNKNOWN_CHANNEL = "UNKNOWN_CHANNEL"
    EMPTY_ORDERS = "EMPTY_ORDERS"
    MISSING_ORDER_DATE = "MISSING_ORDER_DATE"
    CONFLICTING_ORDER_HEADER = "CONFLICTING_ORDER_HEADER"
    INVALID_ORDER_HEADER = "INVALID_ORDER_HEADER"
    HEADER_VALUE_INHERITED = "HEADER_VALUE_INHERITED"
    MISSING_DISCOUNT_ASSUMED_ZERO = "MISSING_DISCOUNT_ASSUMED_ZERO"
    INVALID_QUANTITY_FOR_STATUS = "INVALID_QUANTITY_FOR_STATUS"
    DUPLICATE_ORDER_LINE = "DUPLICATE_ORDER_LINE"
    HISTORICAL_PRODUCT_CREATED = "HISTORICAL_PRODUCT_CREATED"


@dataclass(frozen=True, slots=True)
class SourceRef:
    source: str
    locator: str
    entity_key: str | None = None


Payload = TypeVar("Payload")


@dataclass(frozen=True, slots=True)
class SourceRecord(Generic[Payload]):
    ref: SourceRef
    payload: Payload


@dataclass(frozen=True, slots=True)
class Issue:
    ref: SourceRef
    reason_code: ReasonCode | str
    action: Action
    severity: Severity
    detail: str
    field_name: str | None = None
    raw_excerpt: str | None = field(default=None, repr=False)


class NormalizationError(ValueError):
    """Error seguro: no incluye el valor de entrada en el mensaje."""

    def __init__(self, code: ReasonCode, field_name: str | None = None) -> None:
        self.code = code
        self.field_name = field_name
        super().__init__(code.value if field_name is None else f"{code.value}: {field_name}")
