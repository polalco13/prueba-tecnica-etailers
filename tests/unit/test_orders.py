"""Pedidos sintéticos: resultados esperados sin utilizar clientes del fichero real."""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.etl.orders import HEADER, OrdersReadError, OrdersSelection, extract_orders, select_orders


def row(**changes: str) -> list[str]:
    fields = dict(
        zip(
            HEADER,
            [
                "PED-01",
                "2026-01-02",
                "Cliente sintético",
                "b2b",
                "Completado",
                "PRV-001",
                "2",
                "10,50",
                "10%",
            ],
            strict=True,
        )
    )
    fields.update(changes)
    return [fields[key] for key in HEADER]


def write(path: Path, rows: list[list[str]], encoding: str = "utf-8-sig") -> Path:
    with path.open("w", encoding=encoding, newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def parse(tmp_path: Path, rows: list[list[str]]) -> OrdersSelection:
    return select_orders(extract_orders(write(tmp_path / "orders.csv", rows)))


def test_bom_multiline_customer_and_normalized_header(tmp_path: Path) -> None:
    result = parse(
        tmp_path, [row(cliente="Cliente,\n Sintético", id_pedido=" ped-01 ", sku=" prv-001 ")]
    )
    order = result.orders[0]
    assert order.header.source_order_id == "PED-01"
    assert order.header.customer == "Cliente, Sintético"
    assert order.header.order_date == date(2026, 1, 2)
    assert order.header.channel == "B2B" and order.header.status == "COMPLETADO"
    assert order.lines[0].ref.locator == "2-3"
    assert order.lines[0].unit_price == Decimal("10.50")
    assert order.lines[0].discount == Decimal("0.10")


def test_header_inheritance_compatible_dates_and_missing_customer(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            row(fecha_pedido="", cliente="", canal="", estado=""),
            row(fecha_pedido="02/01/2026 12:00:00", sku="B"),
        ],
    )
    assert len(result.orders) == 1 and len(result.orders[0].lines) == 2
    assert result.orders[0].header.order_date == date(2026, 1, 2)
    assert len(result.issues) == 4
    assert all(i.reason_code == "HEADER_VALUE_INHERITED" for i in result.issues)
    same_day = parse(tmp_path, [row(), row(fecha_pedido="2026-01-02T12:00:00", sku="B")])
    assert same_day.rows_accepted == 2
    missing = parse(tmp_path, [row(cliente="NULL")])
    assert missing.orders[0].header.customer is None


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"fecha_pedido": "2026-01-03"}, "CONFLICTING_ORDER_HEADER"),
        ({"cliente": "Otro cliente sintético"}, "CONFLICTING_ORDER_HEADER"),
        ({"cliente": "CLIENTE SINTÉTICO"}, "CONFLICTING_ORDER_HEADER"),
        ({"canal": "B2C"}, "CONFLICTING_ORDER_HEADER"),
        ({"estado": "ENVIADO"}, "CONFLICTING_ORDER_HEADER"),
        ({"estado": "completadoo"}, "UNKNOWN_ORDER_STATUS"),
        ({"canal": "web"}, "UNKNOWN_CHANNEL"),
        ({"fecha_pedido": "2026-02-30"}, "INVALID_DATE"),
        ({"cliente": "C" * 256}, "INVALID_ORDER_HEADER"),
    ],
)
def test_bad_nonempty_header_rejects_whole_order(tmp_path: Path, changes: dict, code: str) -> None:
    result = parse(tmp_path, [row(), row(**changes)])
    assert result.orders == () and result.rows_rejected == 2
    assert code in {i.reason_code for i in result.issues}


@pytest.mark.parametrize(
    "field,code",
    [
        ("fecha_pedido", "MISSING_ORDER_DATE"),
        ("canal", "MISSING_REQUIRED_FIELD"),
        ("estado", "MISSING_REQUIRED_FIELD"),
    ],
)
def test_missing_header_without_valid_donor(tmp_path: Path, field: str, code: str) -> None:
    result = parse(tmp_path, [row(**{field: ""})])
    assert result.rows_rejected == 1 and not result.orders
    assert code in {i.reason_code for i in result.issues}


@pytest.mark.parametrize(
    "quantity,status,accepted",
    [
        ("2,0", "COMPLETADO", True),
        ("2.0", "COMPLETADO", True),
        ("2,5", "COMPLETADO", False),
        ("0", "COMPLETADO", False),
        ("-2", "COMPLETADO", False),
        ("-2", "DEVUELTO", True),
        ("2", "DEVUELTO", True),
        ("-1", "PENDIENTE", False),
        ("9223372036854775808", "DEVUELTO", False),
        ("NULL", "COMPLETADO", False),
    ],
)
def test_quantities_keep_sign_only_for_returns(
    tmp_path: Path, quantity: str, status: str, accepted: bool
) -> None:
    result = parse(tmp_path, [row(cantidad=quantity, estado=status)])
    assert result.rows_accepted == int(accepted)
    assert result.rows_rejected == int(not accepted)
    if accepted:
        assert result.orders[0].lines[0].quantity == int(Decimal(quantity.replace(",", ".")))


@pytest.mark.parametrize(
    "discount,expected",
    [("10%", "0.10"), ("10", "0.10"), ("0,1", "0.10"), ("100%", "1"), ("", "0"), ("1", "0.01")],
)
def test_discount_rules(tmp_path: Path, discount: str, expected: str) -> None:
    result = parse(tmp_path, [row(descuento_linea=discount)])
    assert result.orders[0].lines[0].discount == Decimal(expected)
    assert bool(result.issues) == (discount == "")


@pytest.mark.parametrize(
    "changes",
    [
        {"precio_unitario": "0"},
        {"precio_unitario": ""},
        {"precio_unitario": "1.234"},
        {"descuento_linea": "101%"},
        {"sku": ""},
        {"sku": "S" * 65},
    ],
)
def test_invalid_line_does_not_discard_valid_sibling(tmp_path: Path, changes: dict) -> None:
    result = parse(tmp_path, [row(), row(**changes)])
    assert result.rows_accepted == result.rows_rejected == 1
    assert result.orders[0].has_rejected_lines


def test_exact_normalized_line_signature_is_stable_but_prices_can_differ(tmp_path: Path) -> None:
    result = parse(
        tmp_path,
        [
            row(),
            row(cantidad="2,0", precio_unitario="10.50", descuento_linea="0,1"),
            row(precio_unitario="12"),
        ],
    )
    assert result.rows_read == 3 and result.rows_accepted == 2
    assert result.rows_deduplicated == 1 and result.rows_rejected == 0
    assert not result.orders[0].has_rejected_lines
    key = result.orders[0].lines[0].line_key
    altered_header = parse(tmp_path, [row(cliente="Otro", fecha_pedido="2026-01-03", canal="B2C")])
    assert altered_header.orders[0].lines[0].line_key == key
    assert len(key) == 64
    assert result.orders[0].lines[1].line_key != key


def test_bad_columns_mark_identifiable_order_partial_and_errors_count_once(tmp_path: Path) -> None:
    result = parse(
        tmp_path, [row(), row()[:-1], row() + ["extra"], row(cantidad="0", precio_unitario="0")]
    )
    assert result.rows_read == 4 and result.rows_accepted == 1 and result.rows_rejected == 3
    assert result.orders[0].has_rejected_lines
    assert sum(i.action == "reject_row" for i in result.issues) == 4
    assert all("Cliente sintético" not in (i.raw_excerpt or "") for i in result.issues)


def test_empty_and_invalid_id_are_not_orders(tmp_path: Path) -> None:
    assert parse(tmp_path, []).orders == ()
    result = parse(tmp_path, [row(id_pedido=""), []])
    assert not result.orders and result.rows_rejected == 2


@pytest.mark.parametrize(
    "content,code", [(b"bad,header\n", "INVALID_HEADER"), (b"\xff", "INVALID_ENCODING")]
)
def test_structural_failures(tmp_path: Path, content: bytes, code: str) -> None:
    path = tmp_path / "orders.csv"
    path.write_bytes(content)
    with pytest.raises(OrdersReadError, match=code):
        extract_orders(path)


def test_broken_quoting_and_missing_file(tmp_path: Path) -> None:
    path = write(tmp_path / "orders.csv", [])
    with path.open("a") as stream:
        stream.write('"unterminated\n')
    with pytest.raises(OrdersReadError, match="INVALID_CSV"):
        extract_orders(path)
    with pytest.raises(OrdersReadError, match="SOURCE_READ_FAILED"):
        extract_orders(tmp_path / "missing.csv")
