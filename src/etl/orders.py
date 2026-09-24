"""Pedidos: lectura con procedencia y reglas puras, sin SQL ni llamadas HTTP."""

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.etl.normalize import (
    normalize_channel,
    normalize_identifier,
    normalize_status,
    normalize_text,
    parse_date,
    parse_discount,
    parse_money,
    parse_quantity,
)
from src.etl.records import Action, Issue, NormalizationError, ReasonCode, Severity, SourceRef

HEADER = (
    "id_pedido",
    "fecha_pedido",
    "cliente",
    "canal",
    "estado",
    "sku",
    "cantidad",
    "precio_unitario",
    "descuento_linea",
)
SOURCE = "orders_csv"
LINE_KEY_VERSION = "order-line-v1"


class OrdersReadError(ValueError):
    def __init__(self, code: ReasonCode, ref: SourceRef) -> None:
        self.code, self.ref = code, ref
        super().__init__(f"{code.value}: {ref.source} fila {ref.locator}")


@dataclass(frozen=True, slots=True)
class OrderRow:
    ref: SourceRef
    cells: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class OrdersBatch:
    rows: tuple[OrderRow, ...]
    issues: tuple[Issue, ...]
    rows_read: int


@dataclass(frozen=True, slots=True)
class OrderHeader:
    source_order_id: str
    order_date: date
    customer: str | None = field(repr=False)
    channel: str
    status: str


@dataclass(frozen=True, slots=True)
class OrderLine:
    sku: str
    quantity: int
    unit_price: Decimal
    discount: Decimal
    line_key: str
    ref: SourceRef


@dataclass(frozen=True, slots=True)
class Order:
    header: OrderHeader
    lines: tuple[OrderLine, ...]
    has_rejected_lines: bool


@dataclass(frozen=True, slots=True)
class OrdersSelection:
    orders: tuple[Order, ...]
    issues: tuple[Issue, ...]
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    rows_deduplicated: int


def _issue(
    row: OrderRow,
    code: ReasonCode,
    action: Action = Action.REJECT_ROW,
    field_name: str | None = None,
    detail: str | None = None,
) -> Issue:
    # No copiar clientes al extracto; con columnas desplazadas no copiar valores.
    excerpt = {"column_count": len(row.cells)}
    if len(row.cells) == len(HEADER):
        excerpt = {
            key: value[:100]
            for key, value in zip(HEADER, row.cells, strict=True)
            if key != "cliente"
        }
    severity = Severity.ERROR if action == Action.REJECT_ROW else Severity.WARNING
    if action == Action.DEDUPLICATE:
        severity = Severity.INFO
    return Issue(
        row.ref,
        code,
        action,
        severity,
        detail or code.value,
        field_name,
        json.dumps(excerpt, ensure_ascii=False)[:512],
    )


def extract_orders(path: Path) -> OrdersBatch:
    rows, issues = [], []
    rows_read = 0
    ref = SourceRef(SOURCE, "1")
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, delimiter=",", strict=True)
            if next(reader, None) != list(HEADER):
                raise OrdersReadError(ReasonCode.INVALID_HEADER, ref)
            while True:
                start = reader.line_num + 1
                ref = SourceRef(SOURCE, str(start))
                cells = next(reader, None)
                if cells is None:
                    break
                end = reader.line_num
                locator = str(start) if start == end else f"{start}-{end}"
                ref = SourceRef(SOURCE, locator)
                rows_read += 1
                try:
                    order_id = normalize_identifier(cells[0] if cells else None)
                    ref = SourceRef(SOURCE, locator, order_id)
                except NormalizationError:
                    issues.append(
                        _issue(
                            OrderRow(ref, tuple(cells)),
                            ReasonCode.INVALID_IDENTIFIER,
                            field_name="id_pedido",
                        )
                    )
                row = OrderRow(ref, tuple(cells))
                if len(cells) != len(HEADER):
                    issues.append(_issue(row, ReasonCode.INVALID_COLUMN_COUNT))
                elif ref.entity_key is not None:
                    rows.append(row)
    except UnicodeError:
        raise OrdersReadError(ReasonCode.INVALID_ENCODING, ref) from None
    except csv.Error:
        raise OrdersReadError(ReasonCode.INVALID_CSV, ref) from None
    except OSError:
        raise OrdersReadError(ReasonCode.SOURCE_READ_FAILED, ref) from None
    return OrdersBatch(tuple(rows), tuple(issues), rows_read)


def _header(rows: list[OrderRow], timezone: str) -> tuple[OrderHeader | None, list[Issue]]:
    parsers = (
        lambda value: parse_date(value, timezone),
        normalize_text,
        normalize_channel,
        normalize_status,
    )
    values = []
    errors: set[tuple[ReasonCode, str]] = set()
    missing: list[tuple[OrderRow, str]] = []
    for index, parser in enumerate(parsers, 1):
        field_name = HEADER[index]
        distinct = {}
        for row in rows:
            try:
                value = parser(row.cells[index])
                if value is None:
                    missing.append((row, field_name))
                else:
                    if (index == 1 and value.year < 1000) or (index == 2 and len(value) > 255):
                        raise NormalizationError(ReasonCode.INVALID_ORDER_HEADER)
                    # ADR 004: comparar cliente sin capitalización y conservar la
                    # primera etiqueta válida, sin eliminar tildes ni puntuación.
                    key = value.casefold() if index == 2 else value
                    distinct.setdefault(key, value)
            except NormalizationError as exc:
                errors.add((exc.code, field_name))
        if len(distinct) > 1:
            errors.add((ReasonCode.CONFLICTING_ORDER_HEADER, field_name))
        if not distinct and index != 2:
            code = (
                ReasonCode.MISSING_ORDER_DATE if index == 1 else ReasonCode.MISSING_REQUIRED_FIELD
            )
            errors.add((code, field_name))
        values.append(next(iter(distinct.values())) if len(distinct) == 1 else None)
    if errors:
        return None, [
            _issue(row, code, field_name=field_name)
            for row in rows
            for code, field_name in sorted(errors)
        ]
    inherited = [
        _issue(row, ReasonCode.HEADER_VALUE_INHERITED, Action.WARN, field_name)
        for row, field_name in missing
        if values[HEADER.index(field_name) - 1] is not None
    ]
    return OrderHeader(rows[0].ref.entity_key, *values), inherited


def line_key(order_id: str, sku: str, quantity: int, price: Decimal, discount: Decimal) -> str:
    """Firma sobre valores ya validados; independiente de fila, cabecera y escala textual."""
    encoded = json.dumps(
        [LINE_KEY_VERSION, order_id, sku, quantity, format(price, ".4f"), format(discount, ".6f")],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _line(row: OrderRow, header: OrderHeader) -> tuple[OrderLine | None, list[Issue]]:
    values = []
    issues = []
    for index, parser in (
        (5, normalize_identifier),
        (6, parse_quantity),
        (7, parse_money),
        (8, parse_discount),
    ):
        try:
            value = parser(row.cells[index])
            if value is None:
                if index == 8:
                    value = Decimal("0")
                    issues.append(
                        _issue(
                            row,
                            ReasonCode.MISSING_DISCOUNT_ASSUMED_ZERO,
                            Action.WARN,
                            HEADER[index],
                        )
                    )
                else:
                    raise NormalizationError(ReasonCode.MISSING_REQUIRED_FIELD)
            if index == 6 and value < 0 and header.status != "DEVUELTO":
                raise NormalizationError(ReasonCode.INVALID_QUANTITY_FOR_STATUS)
            values.append(value)
        except NormalizationError as exc:
            issues.append(_issue(row, exc.code, field_name=HEADER[index]))
    if any(issue.action == Action.REJECT_ROW for issue in issues):
        return None, issues
    sku, quantity, price, discount = values
    return OrderLine(
        sku,
        quantity,
        price,
        discount,
        line_key(header.source_order_id, sku, quantity, price, discount),
        row.ref,
    ), issues


def select_orders(batch: OrdersBatch, timezone: str = "Europe/Madrid") -> OrdersSelection:
    groups: dict[str, list[OrderRow]] = defaultdict(list)
    issues = list(batch.issues)
    malformed_ids = {issue.ref.entity_key for issue in issues if issue.action == Action.REJECT_ROW}
    for row in batch.rows:
        groups[row.ref.entity_key].append(row)
    orders = []
    for order_id, rows in sorted(groups.items()):
        header, header_issues = _header(rows, timezone)
        issues.extend(header_issues)
        if header is None:
            continue
        lines: dict[str, OrderLine] = {}
        partial = order_id in malformed_ids
        for row in rows:
            line, line_issues = _line(row, header)
            issues.extend(line_issues)
            if line is None:
                partial = True
            elif line.line_key in lines:
                issues.append(
                    _issue(
                        row,
                        ReasonCode.DUPLICATE_ORDER_LINE,
                        Action.DEDUPLICATE,
                        detail=f"Conservada fila {lines[line.line_key].ref.locator}",
                    )
                )
            else:
                lines[line.line_key] = line
        if lines:
            orders.append(Order(header, tuple(lines.values()), partial))
    rejected = {i.ref.locator for i in issues if i.action == Action.REJECT_ROW}
    deduplicated = {i.ref.locator for i in issues if i.action == Action.DEDUPLICATE}
    accepted = sum(len(order.lines) for order in orders)
    if batch.rows_read != accepted + len(rejected) + len(deduplicated):
        raise ValueError("Contadores de pedidos inconsistentes")
    return OrdersSelection(
        tuple(orders), tuple(issues), batch.rows_read, accepted, len(rejected), len(deduplicated)
    )
