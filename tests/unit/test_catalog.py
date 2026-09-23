"""Catálogos sintéticos; nunca altera los ficheros originales del proveedor."""

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from src.etl.catalog import (
    HEADER,
    CatalogCandidate,
    CatalogReadError,
    extract_catalog,
    select_catalog_candidates,
)
from src.etl.records import Action, ReasonCode


def _row(**changes: str) -> list[str]:
    data = dict(
        zip(
            HEADER,
            [
                "prv-001",
                "4006381333931",
                "Llave básica",
                "Marca Ñ",
                "Fontanería",
                "30,38",
                "45,16",
                "21",
                "1.997",
                "2025-04-19",
                "Pieza útil",
            ],
            strict=True,
        )
    )
    data.update(changes)
    return [data[column] for column in HEADER]


def _write_catalog(path: Path, rows: list[list[str]], header: list[str] | None = None) -> Path:
    with path.open("w", encoding="latin-1", newline="") as stream:
        writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
        writer.writerow(list(HEADER) if header is None else header)
        writer.writerows(rows)
    return path


def _base_price_issue(candidate: CatalogCandidate) -> ReasonCode | None:
    return candidate.cost_problem


def test_latin1_quoting_multiline_and_provenance(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "catalog.csv",
        [_row(nombre="Piñón; útil", descripcion="Primera línea\nSegunda línea")],
    )
    batch = extract_catalog(path)
    assert batch.rows_read == 1
    assert batch.issues == ()
    candidate = batch.candidates[0]
    assert candidate.record.ref.locator == "2-3"
    assert candidate.record.ref.entity_key == "PRV-001"
    product = candidate.record.payload
    assert product.name == "Piñón; útil"
    assert product.description == "Primera línea Segunda línea"
    assert product.brand == "Marca Ñ"
    assert product.base_cost == Decimal("30.38")
    assert product.pvp == Decimal("45.16")
    assert product.tax_rate == Decimal("0.21")
    assert product.weight_kg == Decimal("1.997")


@pytest.mark.parametrize("row", [_row()[:-1], _row() + ["extra"], []])
def test_wrong_column_count_rejects_only_that_record(tmp_path: Path, row: list[str]) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [row, _row(sku="PRV-002")]))
    assert batch.rows_read == 2
    assert len(batch.candidates) == 1
    issue = batch.issues[0]
    assert issue.reason_code == ReasonCode.INVALID_COLUMN_COUNT
    assert issue.action == Action.REJECT_ROW
    assert issue.ref.locator == "2"
    assert issue.raw_excerpt is not None


def test_wrong_header_aborts_source(tmp_path: Path) -> None:
    header = list(HEADER)
    header[0] = "product_id"
    with pytest.raises(CatalogReadError) as error:
        extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row()], header))
    assert error.value.code == ReasonCode.INVALID_HEADER
    assert error.value.ref.locator == "1"


def test_unrecoverable_csv_quote_aborts_source(tmp_path: Path) -> None:
    path = tmp_path / "catalog.csv"
    _write_catalog(path, [_row()])
    with path.open("a", encoding="latin-1", newline="") as stream:
        stream.write('"fila sin cierre;otro campo\r\n')
    with pytest.raises(CatalogReadError) as error:
        extract_catalog(path)
    assert error.value.code == ReasonCode.INVALID_CSV
    assert error.value.ref.locator.startswith("3")


def test_missing_file_is_fatal_without_echoing_path(tmp_path: Path) -> None:
    path = tmp_path / "secret-local-name.csv"
    with pytest.raises(CatalogReadError) as error:
        extract_catalog(path)
    assert error.value.code == ReasonCode.SOURCE_READ_FAILED
    assert str(path) not in str(error.value)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("sku", "N/D", ReasonCode.MISSING_REQUIRED_FIELD),
        ("sku", "X" * 65, ReasonCode.INVALID_IDENTIFIER),
        ("nombre", "-", ReasonCode.MISSING_REQUIRED_FIELD),
        ("marca", "", ReasonCode.MISSING_REQUIRED_FIELD),
        ("categoria", "NULL", ReasonCode.MISSING_REQUIRED_FIELD),
        ("pvp_recomendado", "", ReasonCode.MISSING_REQUIRED_FIELD),
        ("pvp_recomendado", "0", ReasonCode.NON_POSITIVE_PRICE),
        ("pvp_recomendado", "1.234", ReasonCode.AMBIGUOUS_NUMBER),
    ],
)
def test_invalid_required_field_rejects_row(
    tmp_path: Path, field: str, value: str, code: ReasonCode
) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row(**{field: value})]))
    assert batch.rows_read == 1
    assert batch.candidates == ()
    assert any(issue.reason_code == code and issue.field_name == field for issue in batch.issues)
    assert all(issue.action == Action.REJECT_ROW for issue in batch.issues)


def test_multiple_bad_required_fields_count_one_rejected_row(tmp_path: Path) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row(sku="", nombre="-")]))
    assert len(batch.issues) == 2
    selected = select_catalog_candidates(batch, _base_price_issue)
    assert (selected.rows_read, selected.rows_accepted, selected.rows_rejected) == (1, 0, 1)


@pytest.mark.parametrize(
    ("ean", "expected", "reason"),
    [
        ("'4006381333931", "4006381333931", None),
        ("8,461061067530E+12", None, ReasonCode.UNSAFE_SCIENTIFIC_EAN),
        ("4006381333932", None, ReasonCode.INVALID_EAN),
    ],
)
def test_ean_keeps_product_and_only_discards_bad_field(
    tmp_path: Path, ean: str, expected: str | None, reason: ReasonCode | None
) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row(ean=ean)]))
    assert batch.candidates[0].record.payload.ean == expected
    if reason is None:
        assert batch.issues == ()
    else:
        assert [(i.reason_code, i.action, i.field_name) for i in batch.issues] == [
            (reason, Action.DROP_FIELD, "ean")
        ]


def test_optional_invalid_values_become_null_with_separate_issues(tmp_path: Path) -> None:
    batch = extract_catalog(
        _write_catalog(
            tmp_path / "catalog.csv",
            [_row(iva="NaN", peso_kg="-1", fecha_alta="31/02/2025")],
        )
    )
    product = batch.candidates[0].record.payload
    assert product.tax_rate is None
    assert product.weight_kg is None
    assert product.listed_on is None
    assert {i.reason_code for i in batch.issues} == {
        ReasonCode.INVALID_TAX,
        ReasonCode.INVALID_WEIGHT,
        ReasonCode.INVALID_DATE,
    }
    assert all(i.action == Action.DROP_FIELD for i in batch.issues)


def test_explicit_zero_weight_is_not_unknown(tmp_path: Path) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row(peso_kg="0")]))
    assert batch.candidates[0].record.payload.weight_kg == Decimal("0")


@pytest.mark.parametrize("cost", ["N/D", "0", "1.234", "no es un número"])
def test_bad_csv_cost_is_candidate_pending_xml_exception(tmp_path: Path, cost: str) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row(precio_coste=cost)]))
    assert batch.rows_read == 1
    assert len(batch.candidates) == 1
    assert batch.candidates[0].record.payload.base_cost is None
    assert batch.candidates[0].cost_problem is not None
    assert batch.issues == ()

    without_exception = select_catalog_candidates(batch, _base_price_issue)
    assert without_exception.winners == ()
    assert without_exception.rows_rejected == 1
    assert without_exception.issues[0].action == Action.REJECT_ROW

    with_valid_exception = select_catalog_candidates(batch, lambda _: None)
    assert len(with_valid_exception.winners) == 1
    assert with_valid_exception.rows_accepted == 1
    assert with_valid_exception.issues[0].action == Action.DROP_FIELD


def test_first_invalid_then_valid_candidate_wins(tmp_path: Path) -> None:
    batch = extract_catalog(
        _write_catalog(
            tmp_path / "catalog.csv",
            [
                _row(precio_coste="N/D"),
                _row(precio_coste="40,00", nombre="Segunda fila válida"),
            ],
        )
    )
    selected = select_catalog_candidates(batch, _base_price_issue)
    assert selected.winners[0].record.ref.locator == "3"
    assert selected.winners[0].record.payload.base_cost == Decimal("40.00")
    assert (selected.rows_read, selected.rows_accepted, selected.rows_rejected) == (2, 1, 1)
    assert selected.issues[0].ref.locator == "2"


def test_rejected_pvp_cannot_win_over_later_valid_sku(tmp_path: Path) -> None:
    batch = extract_catalog(
        _write_catalog(tmp_path / "catalog.csv", [_row(pvp_recomendado="0"), _row()])
    )
    selected = select_catalog_candidates(batch, _base_price_issue)
    assert selected.winners[0].record.ref.locator == "3"
    assert (selected.rows_read, selected.rows_accepted, selected.rows_rejected) == (2, 1, 1)


def test_same_normalized_product_but_different_csv_is_conflict(tmp_path: Path) -> None:
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [_row(), _row(sku="PRV-001")]))
    selected = select_catalog_candidates(batch, _base_price_issue)
    assert selected.winners[0].record.ref.locator == "2"
    assert selected.rows_rejected == 1
    assert selected.rows_deduplicated == 0
    assert selected.issues[0].reason_code == ReasonCode.CONFLICTING_PRODUCT_SKU


def test_only_exact_duplicate_does_not_increase_rejections(tmp_path: Path) -> None:
    row = _row()
    batch = extract_catalog(_write_catalog(tmp_path / "catalog.csv", [row, row]))
    selected = select_catalog_candidates(batch, _base_price_issue)
    assert (
        selected.rows_read,
        selected.rows_accepted,
        selected.rows_rejected,
        selected.rows_deduplicated,
    ) == (2, 1, 0, 1)


def test_price_verdict_runs_before_sku_selection(tmp_path: Path) -> None:
    batch = extract_catalog(
        _write_catalog(tmp_path / "catalog.csv", [_row(), _row(precio_coste="40,00")])
    )
    selected = select_catalog_candidates(
        batch,
        lambda candidate: ReasonCode.INVALID_PRICE if candidate.record.ref.locator == "2" else None,
    )
    assert selected.winners[0].record.ref.locator == "3"


def test_identical_and_conflicting_sku_keep_first_valid_with_provenance(tmp_path: Path) -> None:
    first = _row()
    batch = extract_catalog(
        _write_catalog(tmp_path / "catalog.csv", [first, first, _row(pvp_recomendado="50,00")])
    )
    selected = select_catalog_candidates(batch, _base_price_issue)
    assert len(selected.winners) == 1
    assert selected.winners[0].record.ref.locator == "2"
    assert (
        selected.rows_read,
        selected.rows_accepted,
        selected.rows_rejected,
        selected.rows_deduplicated,
    ) == (3, 1, 1, 1)
    assert [(i.ref.locator, i.reason_code, i.action) for i in selected.issues] == [
        ("3", ReasonCode.EXACT_DUPLICATE, Action.DEDUPLICATE),
        ("4", ReasonCode.CONFLICTING_PRODUCT_SKU, Action.REJECT_ROW),
    ]
    assert all("fila 2" in issue.detail for issue in selected.issues)
    assert selected.rows_read == (
        selected.rows_accepted + selected.rows_rejected + selected.rows_deduplicated
    )


def test_issue_excerpt_is_bounded(tmp_path: Path) -> None:
    batch = extract_catalog(
        _write_catalog(tmp_path / "catalog.csv", [_row(ean="bad", descripcion="x" * 1000)])
    )
    assert batch.issues[0].raw_excerpt is not None
    assert len(batch.issues[0].raw_excerpt) <= 512
