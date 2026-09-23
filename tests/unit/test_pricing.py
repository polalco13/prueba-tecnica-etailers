"""Tarifas y productos de prueba sintéticos; no son resultados del proveedor."""

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from src.etl.catalog import HEADER, extract_catalog
from src.etl.pricing import (
    PriceValidationError,
    TariffReadError,
    load_tariffs,
    price_catalog,
    quote_candidate,
)
from src.etl.records import Action, ReasonCode

FIXTURE = Path(__file__).parents[1] / "fixtures" / "pricing_example.xml"


def _xml(
    tmp_path: Path,
    discounts: str = "",
    exceptions: str = "",
    conditions: str = "",
) -> Path:
    path = tmp_path / "tariffs.xml"
    path.write_text(
        f"<TarifasProveedor>{conditions}<Descuentos>{discounts}</Descuentos>"
        f"<Excepciones>{exceptions}</Excepciones></TarifasProveedor>",
        encoding="utf-8",
    )
    return path


def _discount(kind: str, label: str, ratio: str, extra: str = "") -> str:
    return (
        f'<Descuento tipo="{kind}" valor="{label}">'
        f"<PorcentajeBase>{ratio}</PorcentajeBase>{extra}</Descuento>"
    )


def _exception(sku: str, price: str, flag: str = "false") -> str:
    return (
        f'<Producto sku="{sku}"><PrecioNetoAcordado>{price}</PrecioNetoAcordado>'
        f"<AplicaDescuentoAdicional>{flag}</AplicaDescuentoAdicional></Producto>"
    )


def _row(**changes: str) -> list[str]:
    fields = dict(
        zip(
            HEADER,
            [
                "PRV-001",
                "N/D",
                "Producto sintético",
                "Marca Prueba",
                "Ejemplo",
                "100",
                "120",
                "21",
                "0",
                "2025-04-01",
                "N/D",
            ],
            strict=True,
        )
    )
    fields.update(changes)
    return [fields[column] for column in HEADER]


def _catalog(tmp_path: Path, rows: list[list[str]]) -> Path:
    path = tmp_path / "catalog.csv"
    with path.open("w", encoding="latin-1", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def test_fixture_reads_utf8_and_normalizes_keys() -> None:
    tariffs = load_tariffs(FIXTURE)
    assert tariffs.category["ejemplo"].ratio == Decimal("0.10")
    assert tariffs.brand["marca prueba"].ratio == Decimal("0.05")
    assert tariffs.exceptions["EX-001"].price == Decimal("42.22")
    assert tariffs.issues == ()


def test_identical_rules_are_deduplicated_without_changing_rate(tmp_path: Path) -> None:
    discounts = _discount("categoria", "FONTANERÍA", "10%") + _discount(
        "categoria", " Fontanería ", "10"
    )
    exceptions = _exception("EX-001", "42.22") + _exception("ex-001", "42,22")
    tariffs = load_tariffs(_xml(tmp_path, discounts, exceptions))
    assert len(tariffs.category) == 1
    assert len(tariffs.exceptions) == 1
    assert [i.reason_code for i in tariffs.issues] == [
        ReasonCode.EXACT_DUPLICATE,
        ReasonCode.EXACT_DUPLICATE,
    ]
    assert all(i.action == Action.DEDUPLICATE for i in tariffs.issues)
    assert "Descuento[1]" in tariffs.issues[0].detail


def test_conflicting_general_rule_aborts_without_first_wins(tmp_path: Path) -> None:
    discounts = _discount("categoria", "Ejemplo", "10") + _discount("categoria", "ejemplo", "20")
    with pytest.raises(TariffReadError) as error:
        load_tariffs(_xml(tmp_path, discounts))
    assert error.value.code == ReasonCode.CONFLICTING_TARIFF
    assert error.value.related_ref is not None
    assert error.value.ref.locator.endswith("Descuento[2]")


def test_conflicting_exceptions_abort(tmp_path: Path) -> None:
    exceptions = _exception("EX-001", "10") + _exception("ex-001", "20")
    with pytest.raises(TariffReadError) as error:
        load_tariffs(_xml(tmp_path, exceptions=exceptions))
    assert error.value.code == ReasonCode.CONFLICTING_TARIFF


@pytest.mark.parametrize(
    "discounts",
    [
        _discount("categoria", "Ejemplo", "NaN"),
        _discount("categoria", "Ejemplo", "101"),
        _discount("categoria", "Ejemplo", ""),
        _discount("zona", "Ejemplo", "10"),
        '<Descuento tipo="marca" valor="N/D"><PorcentajeBase>10</PorcentajeBase></Descuento>',
        '<Descuento tipo="marca" valor="X"></Descuento>',
        '<Descuento tipo="marca" valor="X"><PorcentajeBase>10<Otro>20</Otro></PorcentajeBase></Descuento>',
    ],
)
def test_invalid_general_rule_fails_run(tmp_path: Path, discounts: str) -> None:
    with pytest.raises(TariffReadError) as error:
        load_tariffs(_xml(tmp_path, discounts))
    assert error.value.code == ReasonCode.INVALID_TARIFF


@pytest.mark.parametrize("price", ["0", "N/D", "NaN", "100000000000000"])
def test_invalid_exception_is_kept_to_block_product(tmp_path: Path, price: str) -> None:
    tariffs = load_tariffs(_xml(tmp_path, exceptions=_exception("EX-001", price)))
    entry = tariffs.exceptions["EX-001"]
    assert entry.price is None
    assert entry.problem == ReasonCode.INVALID_EXCEPTION_PRICE
    assert tariffs.issues[0].reason_code == ReasonCode.INVALID_EXCEPTION_PRICE


def test_true_additional_discount_flag_is_invalid_exception(tmp_path: Path) -> None:
    tariffs = load_tariffs(_xml(tmp_path, exceptions=_exception("EX-001", "10", "true")))
    assert tariffs.exceptions["EX-001"].problem == ReasonCode.INVALID_EXCEPTION_PRICE


def test_nested_content_in_exception_price_cannot_be_partially_parsed(tmp_path: Path) -> None:
    exception = '<Producto sku="EX-001"><PrecioNetoAcordado>10<Otro>20</Otro></PrecioNetoAcordado></Producto>'
    tariffs = load_tariffs(_xml(tmp_path, exceptions=exception))
    assert tariffs.exceptions["EX-001"].problem == ReasonCode.INVALID_EXCEPTION_PRICE


def test_volume_and_commercial_terms_are_visible_but_not_pricing_rules(tmp_path: Path) -> None:
    discount = _discount(
        "marca", "Marca Prueba", "5", '<PorVolumen desdeUnidades="10">20</PorVolumen>'
    )
    conditions = "<Condiciones><PortesGratisDesde>250</PortesGratisDesde></Condiciones>"
    tariffs = load_tariffs(_xml(tmp_path, discount, conditions=conditions))
    assert tariffs.brand["marca prueba"].ratio == Decimal("0.05")
    assert [i.reason_code for i in tariffs.issues] == [
        ReasonCode.UNAPPLIED_TARIFF_TERM,
        ReasonCode.UNAPPLIED_TARIFF_TERM,
    ]


@pytest.mark.parametrize("document", ["<TarifasProveedor>", "<wrong/>", "<TarifasProveedor/>"])
def test_broken_or_missing_xml_sections_abort(tmp_path: Path, document: str) -> None:
    path = tmp_path / "tariffs.xml"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(TariffReadError) as error:
        load_tariffs(path)
    assert error.value.code == ReasonCode.INVALID_XML


def test_non_utf8_bytes_abort_with_encoding_reason(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.xml"
    path.write_bytes(b"<TarifasProveedor>\xff</TarifasProveedor>")
    with pytest.raises(TariffReadError) as error:
        load_tariffs(path)
    assert error.value.code == ReasonCode.INVALID_ENCODING


def test_non_utf8_xml_declaration_is_rejected_even_if_bytes_decode(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.xml"
    path.write_text(
        '<?xml version="1.0" encoding="ISO-8859-1"?><TarifasProveedor/>',
        encoding="utf-8",
    )
    with pytest.raises(TariffReadError) as error:
        load_tariffs(path)
    assert error.value.code == ReasonCode.INVALID_ENCODING


def test_doctype_is_not_accepted(tmp_path: Path) -> None:
    path = tmp_path / "tariffs.xml"
    path.write_text('<!DOCTYPE x [<!ENTITY e "term">]><TarifasProveedor/>', encoding="utf-8")
    with pytest.raises(TariffReadError) as error:
        load_tariffs(path)
    assert error.value.code == ReasonCode.INVALID_XML


def test_additive_10_and_5_percent_gives_85_not_sequential_85_5(tmp_path: Path) -> None:
    batch = extract_catalog(_catalog(tmp_path, [_row()]))
    result = price_catalog(batch, load_tariffs(FIXTURE))
    assert len(result.products) == 1
    quote = result.products[0].quote
    assert quote.net_cost == Decimal("85.0000")
    assert quote.net_cost != Decimal("85.5")
    assert quote.origin == "base_with_discounts"
    assert quote.category_ratio == Decimal("0.10")
    assert quote.brand_ratio == Decimal("0.05")
    assert len(quote.rule_refs) == 2
    assert result.selection.rows_accepted == 1


@pytest.mark.parametrize(
    ("category", "brand", "expected"),
    [
        ("Ejemplo", "Sin marca", Decimal("90.0000")),
        ("Sin categoría", "Marca Prueba", Decimal("95.0000")),
        ("Sin categoría", "Sin marca", Decimal("100.0000")),
    ],
)
def test_one_or_no_general_rules_have_zero_for_absent_discounts(
    tmp_path: Path, category: str, brand: str, expected: Decimal
) -> None:
    batch = extract_catalog(_catalog(tmp_path, [_row(categoria=category, marca=brand)]))
    result = price_catalog(batch, load_tariffs(FIXTURE))
    assert result.products[0].quote.net_cost == expected


def test_general_lookup_normalizes_case_spaces_and_accents(tmp_path: Path) -> None:
    discounts = _discount("categoria", " FONTANERÍA ", "10")
    tariffs = load_tariffs(_xml(tmp_path, discounts))
    batch = extract_catalog(
        _catalog(tmp_path, [_row(categoria="  fontanería  ", marca="Sin marca")])
    )
    assert price_catalog(batch, tariffs).products[0].quote.net_cost == Decimal("90.0000")


def test_exception_overrides_all_discounts_and_invalid_csv_cost(tmp_path: Path) -> None:
    batch = extract_catalog(_catalog(tmp_path, [_row(sku="EX-001", precio_coste="N/D")]))
    result = price_catalog(batch, load_tariffs(FIXTURE))
    assert result.products[0].quote.net_cost == Decimal("42.2200")
    assert result.products[0].quote.origin == "exception"
    assert result.products[0].quote.category_ratio == Decimal(0)
    assert result.products[0].quote.brand_ratio == Decimal(0)
    assert len(result.products[0].quote.rule_refs) == 1
    assert any(
        i.action == Action.DROP_FIELD and i.field_name == "precio_coste" for i in result.issues
    )


def test_invalid_csv_cost_without_exception_rejects_product(tmp_path: Path) -> None:
    batch = extract_catalog(_catalog(tmp_path, [_row(precio_coste="N/D")]))
    result = price_catalog(batch, load_tariffs(FIXTURE))
    assert result.products == ()
    assert result.selection.rows_rejected == 1
    assert any(
        i.reason_code == ReasonCode.MISSING_REQUIRED_FIELD and i.action == Action.REJECT_ROW
        for i in result.issues
    )


def test_invalid_exception_cannot_fall_back_to_base_cost(tmp_path: Path) -> None:
    tariffs = load_tariffs(_xml(tmp_path, exceptions=_exception("PRV-001", "0")))
    batch = extract_catalog(_catalog(tmp_path, [_row()]))
    result = price_catalog(batch, tariffs)
    assert result.products == ()
    assert result.selection.rows_rejected == 1
    assert any(
        i.reason_code == ReasonCode.INVALID_EXCEPTION_PRICE and i.action == Action.REJECT_ROW
        for i in result.issues
    )


def test_first_row_invalid_after_pricing_leaves_later_valid_row_to_win(tmp_path: Path) -> None:
    tariffs = load_tariffs(_xml(tmp_path, _discount("categoria", "Cien", "100")))
    batch = extract_catalog(
        _catalog(
            tmp_path,
            [
                _row(categoria="Cien"),
                _row(categoria="Ejemplo", precio_coste="70"),
            ],
        )
    )
    result = price_catalog(batch, tariffs)
    assert result.products[0].candidate.record.ref.locator == "3"
    assert result.products[0].quote.net_cost == Decimal("70.0000")
    assert (
        result.selection.rows_read,
        result.selection.rows_accepted,
        result.selection.rows_rejected,
    ) == (2, 1, 1)


@pytest.mark.parametrize("rate", ["100", "100%"])
def test_total_discount_of_100_percent_rejects_product(tmp_path: Path, rate: str) -> None:
    tariffs = load_tariffs(_xml(tmp_path, _discount("categoria", "Ejemplo", rate)))
    batch = extract_catalog(_catalog(tmp_path, [_row()]))
    result = price_catalog(batch, tariffs)
    assert result.products == ()
    assert any(
        i.reason_code == ReasonCode.NON_POSITIVE_PRICE and i.action == Action.REJECT_ROW
        for i in result.issues
    )


def test_additive_combination_over_100_percent_rejects_product(tmp_path: Path) -> None:
    discounts = _discount("categoria", "Ejemplo", "60") + _discount("marca", "Marca Prueba", "50")
    batch = extract_catalog(_catalog(tmp_path, [_row()]))
    result = price_catalog(batch, load_tariffs(_xml(tmp_path, discounts)))
    assert result.products == ()
    assert result.selection.rows_rejected == 1


def test_net_cost_uses_half_up_four_places_and_must_remain_positive(tmp_path: Path) -> None:
    discounts = _discount("categoria", "Ejemplo", "50")
    tariffs = load_tariffs(_xml(tmp_path, discounts))
    batch = extract_catalog(_catalog(tmp_path, [_row(precio_coste="1,2345")]))
    assert price_catalog(batch, tariffs).products[0].quote.net_cost == Decimal("0.6173")
    tiny = extract_catalog(_catalog(tmp_path, [_row(precio_coste="0,0001")]))
    steep_tariffs = load_tariffs(_xml(tmp_path, _discount("categoria", "Ejemplo", "60")))
    with pytest.raises(PriceValidationError) as error:
        quote_candidate(tiny.candidates[0], steep_tariffs)
    assert error.value.code == ReasonCode.NON_POSITIVE_PRICE


def test_orphan_exception_has_warning_and_does_not_create_product(tmp_path: Path) -> None:
    batch = extract_catalog(_catalog(tmp_path, [_row()]))
    result = price_catalog(batch, load_tariffs(FIXTURE))
    orphan = [i for i in result.issues if i.reason_code == ReasonCode.UNKNOWN_PRODUCT_SKU]
    assert len(orphan) == 1
    assert orphan[0].ref.entity_key == "EX-001"
    assert orphan[0].action == Action.WARN
    assert len(result.products) == 1


def test_exact_catalog_duplicate_does_not_count_as_rejection(tmp_path: Path) -> None:
    row = _row()
    batch = extract_catalog(_catalog(tmp_path, [row, row]))
    result = price_catalog(batch, load_tariffs(FIXTURE))
    assert (
        result.selection.rows_read,
        result.selection.rows_accepted,
        result.selection.rows_rejected,
        result.selection.rows_deduplicated,
    ) == (2, 1, 0, 1)
