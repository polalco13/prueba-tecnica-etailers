"""Tarifas XML y precio neto de compra, sin persistencia ni I/O de negocio."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from src.etl.catalog import (
    CatalogBatch,
    CatalogCandidate,
    CatalogSelection,
    select_catalog_candidates,
)
from src.etl.normalize import (
    comparison_key,
    normalize_identifier,
    normalize_text,
    parse_discount,
    parse_money,
    round_decimal,
)
from src.etl.records import (
    Action,
    Issue,
    NormalizationError,
    ReasonCode,
    Severity,
    SourceRef,
)

SOURCE = "tariffs_xml"
_EXCERPT_LIMIT = 512
_MAX_MONEY = Decimal("99999999999999.9999")


class TariffReadError(ValueError):
    """Una tarifa estructuralmente insegura impide publicar cualquier coste."""

    def __init__(
        self, code: ReasonCode, ref: SourceRef, related_ref: SourceRef | None = None
    ) -> None:
        self.code = code
        self.ref = ref
        self.related_ref = related_ref
        related = f"; anterior {related_ref.locator}" if related_ref else ""
        super().__init__(f"{code.value}: {ref.source} {ref.locator}{related}")


@dataclass(frozen=True, slots=True)
class DiscountRule:
    key: str
    ratio: Decimal
    ref: SourceRef


@dataclass(frozen=True, slots=True)
class PriceException:
    sku: str
    price: Decimal | None
    problem: ReasonCode | None
    ref: SourceRef
    raw_price: str | None
    discount_flag: str | None


@dataclass(frozen=True, slots=True)
class Tariffs:
    category: dict[str, DiscountRule]
    brand: dict[str, DiscountRule]
    exceptions: dict[str, PriceException]
    issues: tuple[Issue, ...]


@dataclass(frozen=True, slots=True)
class PriceQuote:
    net_cost: Decimal
    origin: str
    category_ratio: Decimal
    brand_ratio: Decimal
    rule_refs: tuple[SourceRef, ...]


@dataclass(frozen=True, slots=True)
class PricedProduct:
    candidate: CatalogCandidate
    quote: PriceQuote


@dataclass(frozen=True, slots=True)
class PricedCatalog:
    products: tuple[PricedProduct, ...]
    selection: CatalogSelection
    issues: tuple[Issue, ...]


class PriceValidationError(ValueError):
    """Precio de un candidato inválido; no aborta otras filas."""

    def __init__(self, code: ReasonCode) -> None:
        self.code = code
        super().__init__(code.value)


def _ref(locator: str, key: str | None = None) -> SourceRef:
    return SourceRef(SOURCE, locator, key)


def _excerpt(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode")[:_EXCERPT_LIMIT]


def _issue(
    ref: SourceRef,
    code: ReasonCode,
    action: Action,
    detail: str,
    element: ET.Element,
) -> Issue:
    severity = Severity.INFO if action in {Action.DEDUPLICATE, Action.WARN} else Severity.ERROR
    return Issue(ref, code, action, severity, detail, raw_excerpt=_excerpt(element))


def _parse_general(
    element: ET.Element,
    ref: SourceRef,
    category: dict[str, DiscountRule],
    brand: dict[str, DiscountRule],
    issues: list[Issue],
) -> None:
    if element.tag != "Descuento":
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref)
    kind = element.get("tipo")
    raw_label = element.get("valor")
    label = normalize_text(raw_label)
    key = comparison_key(raw_label)
    if kind not in {"categoria", "marca"} or label is None or key is None:
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref)
    children = list(element)
    bases = [child for child in children if child.tag == "PorcentajeBase"]
    if (
        len(bases) != 1
        or any(child.tag not in {"PorcentajeBase", "PorVolumen"} for child in children)
        or len(bases[0]) != 0
    ):
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref)
    try:
        ratio = parse_discount(bases[0].text)
    except NormalizationError:
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref) from None
    if ratio is None:
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref)

    keyed_ref = _ref(ref.locator, f"{kind}:{key}")
    target = category if kind == "categoria" else brand
    previous = target.get(key)
    if previous is not None:
        if previous.ratio != ratio:
            raise TariffReadError(ReasonCode.CONFLICTING_TARIFF, keyed_ref, previous.ref)
        issues.append(
            _issue(
                keyed_ref,
                ReasonCode.EXACT_DUPLICATE,
                Action.DEDUPLICATE,
                f"Regla idéntica; conservada {previous.ref.locator}",
                element,
            )
        )
    else:
        target[key] = DiscountRule(key, ratio, keyed_ref)
    volume_index = 0
    for child in children:
        if child.tag == "PorVolumen":
            volume_index += 1
            issues.append(
                _issue(
                    _ref(f"{ref.locator}/PorVolumen[{volume_index}]", keyed_ref.entity_key),
                    ReasonCode.UNAPPLIED_TARIFF_TERM,
                    Action.WARN,
                    "Descuento por volumen no aplicado sin compra conocida",
                    child,
                )
            )


def _parse_exception(element: ET.Element, ref: SourceRef) -> PriceException:
    if element.tag != "Producto":
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref)
    try:
        sku = normalize_identifier(element.get("sku"), "sku")
    except NormalizationError:
        raise TariffReadError(ReasonCode.INVALID_TARIFF, ref) from None
    keyed_ref = _ref(ref.locator, sku)
    children = list(element)
    prices = [child for child in children if child.tag == "PrecioNetoAcordado"]
    flags = [child for child in children if child.tag == "AplicaDescuentoAdicional"]
    if (
        len(prices) > 1
        or len(flags) > 1
        or any(
            child.tag not in {"PrecioNetoAcordado", "AplicaDescuentoAdicional"}
            for child in children
        )
    ):
        raise TariffReadError(ReasonCode.INVALID_TARIFF, keyed_ref)

    raw_price = prices[0].text if prices else None
    try:
        price = parse_money(raw_price)
        problem = ReasonCode.INVALID_EXCEPTION_PRICE if price is None else None
    except NormalizationError:
        price = None
        problem = ReasonCode.INVALID_EXCEPTION_PRICE
    if prices and len(prices[0]) != 0:
        price = None
        problem = ReasonCode.INVALID_EXCEPTION_PRICE
    discount_flag = (flags[0].text or "").strip().casefold() if flags else None
    if discount_flag not in {None, "false"}:
        price = None
        problem = ReasonCode.INVALID_EXCEPTION_PRICE
    return PriceException(sku, price, problem, keyed_ref, raw_price, discount_flag)


def load_tariffs(path: Path) -> Tariffs:
    """Lee UTF-8; XML roto o reglas generales ambiguas fallan por completo."""

    try:
        document = path.read_bytes().decode("utf-8-sig")
    except UnicodeError:
        raise TariffReadError(ReasonCode.INVALID_ENCODING, _ref("/")) from None
    except OSError:
        raise TariffReadError(ReasonCode.SOURCE_READ_FAILED, _ref("/")) from None
    declaration = re.match(r"\s*<\?xml\s+[^?]*\?>", document)
    if declaration is not None:
        encoding = re.search(r"\bencoding\s*=\s*(['\"])(.*?)\1", declaration.group(0))
        if encoding is not None and encoding.group(2).casefold() not in {"utf-8", "utf8"}:
            raise TariffReadError(ReasonCode.INVALID_ENCODING, _ref("/"))
    if re.search(r"<!DOCTYPE", document, re.IGNORECASE):
        raise TariffReadError(ReasonCode.INVALID_XML, _ref("/"))
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        raise TariffReadError(ReasonCode.INVALID_XML, _ref("/")) from None
    if root.tag != "TarifasProveedor":
        raise TariffReadError(ReasonCode.INVALID_XML, _ref("/"))
    sections = {child.tag: child for child in root}
    if (
        len(sections) != len(root)
        or set(sections) - {"Condiciones", "Descuentos", "Excepciones"}
        or "Descuentos" not in sections
        or "Excepciones" not in sections
    ):
        raise TariffReadError(ReasonCode.INVALID_XML, _ref("/TarifasProveedor"))

    category: dict[str, DiscountRule] = {}
    brand: dict[str, DiscountRule] = {}
    exceptions: dict[str, PriceException] = {}
    issues: list[Issue] = []
    conditions = sections.get("Condiciones")
    if conditions is not None:
        for index, child in enumerate(conditions, 1):
            ref = _ref(f"/TarifasProveedor/Condiciones/*[{index}]")
            issues.append(
                _issue(
                    ref,
                    ReasonCode.UNAPPLIED_TARIFF_TERM,
                    Action.WARN,
                    "Condición comercial no aplicada al coste unitario",
                    child,
                )
            )

    for index, element in enumerate(sections["Descuentos"], 1):
        ref = _ref(f"/TarifasProveedor/Descuentos/Descuento[{index}]")
        _parse_general(element, ref, category, brand, issues)

    for index, element in enumerate(sections["Excepciones"], 1):
        ref = _ref(f"/TarifasProveedor/Excepciones/Producto[{index}]")
        entry = _parse_exception(element, ref)
        previous = exceptions.get(entry.sku)
        if previous is not None:
            same_valid_price = (
                previous.problem is None and entry.problem is None and previous.price == entry.price
            )
            same_invalid_input = (
                previous.problem is not None
                and entry.problem is not None
                and previous.raw_price == entry.raw_price
                and previous.discount_flag == entry.discount_flag
            )
            if not (same_valid_price or same_invalid_input):
                raise TariffReadError(ReasonCode.CONFLICTING_TARIFF, entry.ref, previous.ref)
            issues.append(
                _issue(
                    entry.ref,
                    ReasonCode.EXACT_DUPLICATE,
                    Action.DEDUPLICATE,
                    f"Excepción idéntica; conservada {previous.ref.locator}",
                    element,
                )
            )
        else:
            exceptions[entry.sku] = entry
            if entry.problem is not None:
                issues.append(
                    _issue(
                        entry.ref,
                        ReasonCode.INVALID_EXCEPTION_PRICE,
                        Action.WARN,
                        "Excepción inválida; producto afectado se rechazará",
                        element,
                    )
                )

    return Tariffs(category, brand, exceptions, tuple(issues))


def quote_candidate(candidate: CatalogCandidate, tariffs: Tariffs) -> PriceQuote:
    """Aplica excepción absoluta o descuento aditivo y redondea a cuatro decimales."""

    product = candidate.record.payload
    exception = tariffs.exceptions.get(product.sku)
    if exception is not None:
        if exception.problem is not None or exception.price is None:
            raise PriceValidationError(ReasonCode.INVALID_EXCEPTION_PRICE)
        return PriceQuote(
            round_decimal(exception.price, 4), "exception", Decimal(0), Decimal(0), (exception.ref,)
        )

    if product.base_cost is None:
        raise PriceValidationError(candidate.cost_problem or ReasonCode.MISSING_REQUIRED_FIELD)
    category_key = comparison_key(product.category)
    brand_key = comparison_key(product.brand)
    category_rule = tariffs.category.get(category_key) if category_key is not None else None
    brand_rule = tariffs.brand.get(brand_key) if brand_key is not None else None
    category_ratio = category_rule.ratio if category_rule else Decimal(0)
    brand_ratio = brand_rule.ratio if brand_rule else Decimal(0)
    combined = category_ratio + brand_ratio
    if combined >= 1:
        raise PriceValidationError(ReasonCode.NON_POSITIVE_PRICE)
    net_cost = round_decimal(product.base_cost * (1 - combined), 4)
    if net_cost <= 0:
        raise PriceValidationError(ReasonCode.NON_POSITIVE_PRICE)
    if net_cost > _MAX_MONEY:
        raise PriceValidationError(ReasonCode.NUMERIC_OUT_OF_RANGE)
    refs = tuple(rule.ref for rule in (category_rule, brand_rule) if rule is not None)
    return PriceQuote(net_cost, "base_with_discounts", category_ratio, brand_ratio, refs)


def price_catalog(batch: CatalogBatch, tariffs: Tariffs) -> PricedCatalog:
    """Valida precios de todas las filas antes de resolver duplicados por SKU."""

    quotes: dict[str, PriceQuote] = {}

    def price_issue_for(candidate: CatalogCandidate) -> ReasonCode | None:
        try:
            quotes[candidate.record.ref.locator] = quote_candidate(candidate, tariffs)
        except PriceValidationError as exc:
            return exc.code
        return None

    selection = select_catalog_candidates(batch, price_issue_for)
    products = tuple(
        PricedProduct(candidate, quotes[candidate.record.ref.locator])
        for candidate in selection.winners
    )
    tariff_issues = list(tariffs.issues)
    known_skus = {candidate.record.payload.sku for candidate in batch.candidates}
    for sku, exception in tariffs.exceptions.items():
        if sku not in known_skus:
            tariff_issues.append(
                Issue(
                    exception.ref,
                    ReasonCode.UNKNOWN_PRODUCT_SKU,
                    Action.WARN,
                    Severity.WARNING,
                    "Excepción sin candidato de catálogo",
                )
            )
    return PricedCatalog(products, selection, selection.issues + tuple(tariff_issues))
