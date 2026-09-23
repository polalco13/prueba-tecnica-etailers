"""Lectura y validación del catálogo; el precio neto se resuelve en F3."""

import csv
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.etl.normalize import (
    normalize_ean,
    normalize_identifier,
    normalize_text,
    parse_date,
    parse_decimal,
    parse_discount,
    parse_money,
    require_text,
)
from src.etl.records import (
    Action,
    Issue,
    NormalizationError,
    ReasonCode,
    Severity,
    SourceRecord,
    SourceRef,
)

HEADER = (
    "sku",
    "ean",
    "nombre",
    "marca",
    "categoria",
    "precio_coste",
    "pvp_recomendado",
    "iva",
    "peso_kg",
    "fecha_alta",
    "descripcion",
)
SOURCE = "catalog_csv"
_EXCERPT_LIMIT = 512


class CatalogReadError(ValueError):
    """Fallo estructural: no se puede publicar un catálogo parcial."""

    def __init__(self, code: ReasonCode, ref: SourceRef) -> None:
        self.code = code
        self.ref = ref
        super().__init__(f"{code.value}: {ref.source} fila {ref.locator}")


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    sku: str
    ean: str | None
    name: str
    brand: str
    category: str
    base_cost: Decimal | None
    pvp: Decimal
    tax_rate: Decimal | None
    weight_kg: Decimal | None
    listed_on: date | None
    description: str | None


@dataclass(frozen=True, slots=True)
class CatalogCandidate:
    record: SourceRecord[CatalogProduct]
    raw_cells: tuple[str, ...]
    cost_problem: ReasonCode | None


@dataclass(frozen=True, slots=True)
class CatalogBatch:
    candidates: tuple[CatalogCandidate, ...]
    issues: tuple[Issue, ...]
    rows_read: int


@dataclass(frozen=True, slots=True)
class CatalogSelection:
    winners: tuple[CatalogCandidate, ...]
    issues: tuple[Issue, ...]
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    rows_deduplicated: int


def _ref(start_line: int, end_line: int, entity_key: str | None = None) -> SourceRef:
    locator = str(start_line) if start_line == end_line else f"{start_line}-{end_line}"
    return SourceRef(SOURCE, locator, entity_key)


def _excerpt(row: list[str] | tuple[str, ...]) -> str:
    return json.dumps(row, ensure_ascii=False)[:_EXCERPT_LIMIT]


def _issue(
    ref: SourceRef,
    code: ReasonCode,
    action: Action,
    detail: str,
    row: list[str] | tuple[str, ...],
    field_name: str | None = None,
) -> Issue:
    severity = (
        Severity.ERROR if action in {Action.REJECT_ROW, Action.FAIL_RUN} else Severity.WARNING
    )
    if action == Action.DEDUPLICATE:
        severity = Severity.INFO
    return Issue(ref, code, action, severity, detail, field_name, _excerpt(row))


def _parse_row(row: list[str], ref: SourceRef) -> tuple[CatalogCandidate | None, list[Issue]]:
    fields = dict(zip(HEADER, row, strict=True))
    errors: list[Issue] = []

    def required_text(field_name: str) -> str | None:
        try:
            return require_text(fields[field_name], field_name)
        except NormalizationError as exc:
            errors.append(
                _issue(
                    ref, exc.code, Action.REJECT_ROW, "Campo obligatorio inválido", row, field_name
                )
            )
            return None

    try:
        sku = normalize_identifier(fields["sku"], "sku")
        ref = SourceRef(ref.source, ref.locator, sku)
    except NormalizationError as exc:
        sku = None
        errors.append(_issue(ref, exc.code, Action.REJECT_ROW, "SKU inválido", row, "sku"))
    name = required_text("nombre")
    brand = required_text("marca")
    category = required_text("categoria")

    try:
        pvp = parse_money(fields["pvp_recomendado"])
        if pvp is None:
            raise NormalizationError(ReasonCode.MISSING_REQUIRED_FIELD, "pvp_recomendado")
    except NormalizationError as exc:
        errors.append(
            _issue(
                ref, exc.code, Action.REJECT_ROW, "PVP obligatorio inválido", row, "pvp_recomendado"
            )
        )
        pvp = None

    if errors:
        return None, errors

    assert sku is not None and name is not None and brand is not None
    assert category is not None and pvp is not None

    try:
        base_cost = parse_money(fields["precio_coste"])
        cost_problem = ReasonCode.MISSING_REQUIRED_FIELD if base_cost is None else None
    except NormalizationError as exc:
        base_cost = None
        cost_problem = exc.code

    optional_issues: list[Issue] = []
    try:
        ean = normalize_ean(fields["ean"])
    except NormalizationError as exc:
        ean = None
        optional_issues.append(
            _issue(ref, exc.code, Action.DROP_FIELD, "EAN descartado", row, "ean")
        )

    try:
        tax_rate = parse_discount(fields["iva"])
    except NormalizationError:
        tax_rate = None
        optional_issues.append(
            _issue(ref, ReasonCode.INVALID_TAX, Action.DROP_FIELD, "IVA descartado", row, "iva")
        )

    try:
        weight_kg = parse_decimal(fields["peso_kg"])
        if weight_kg is not None and weight_kg < 0:
            raise NormalizationError(ReasonCode.INVALID_WEIGHT)
    except NormalizationError:
        weight_kg = None
        optional_issues.append(
            _issue(
                ref, ReasonCode.INVALID_WEIGHT, Action.DROP_FIELD, "Peso descartado", row, "peso_kg"
            )
        )

    try:
        listed_on = parse_date(fields["fecha_alta"])
    except NormalizationError:
        listed_on = None
        optional_issues.append(
            _issue(
                ref,
                ReasonCode.INVALID_DATE,
                Action.DROP_FIELD,
                "Fecha de alta descartada",
                row,
                "fecha_alta",
            )
        )

    product = CatalogProduct(
        sku,
        ean,
        name,
        brand,
        category,
        base_cost,
        pvp,
        tax_rate,
        weight_kg,
        listed_on,
        normalize_text(fields["descripcion"]),
    )
    candidate = CatalogCandidate(SourceRecord(ref, product), tuple(row), cost_problem)
    return candidate, optional_issues


def extract_catalog(path: Path) -> CatalogBatch:
    """Lee Latin-1/`;`; aborta estructura corrupta y aísla filas inválidas."""

    candidates: list[CatalogCandidate] = []
    issues: list[Issue] = []
    rows_read = 0
    try:
        with path.open("r", encoding="latin-1", newline="") as stream:
            reader = csv.reader(stream, delimiter=";", strict=True)
            try:
                header = next(reader, None)
            except csv.Error:
                raise CatalogReadError(ReasonCode.INVALID_CSV, _ref(1, 1)) from None
            if header != list(HEADER):
                raise CatalogReadError(ReasonCode.INVALID_HEADER, _ref(1, reader.line_num or 1))
            while True:
                start_line = reader.line_num + 1
                try:
                    row = next(reader, None)
                except csv.Error:
                    raise CatalogReadError(
                        ReasonCode.INVALID_CSV, _ref(start_line, reader.line_num)
                    ) from None
                if row is None:
                    break
                ref = _ref(start_line, reader.line_num)
                rows_read += 1
                if len(row) != len(HEADER):
                    if row:
                        try:
                            ref = SourceRef(
                                ref.source, ref.locator, normalize_identifier(row[0], "sku")
                            )
                        except NormalizationError:
                            pass
                    issues.append(
                        _issue(
                            ref,
                            ReasonCode.INVALID_COLUMN_COUNT,
                            Action.REJECT_ROW,
                            "Número de columnas incorrecto",
                            row,
                        )
                    )
                    continue
                candidate, row_issues = _parse_row(row, ref)
                issues.extend(row_issues)
                if candidate is not None:
                    candidates.append(candidate)
    except UnicodeError:
        raise CatalogReadError(ReasonCode.INVALID_ENCODING, _ref(1, 1)) from None
    except OSError:
        raise CatalogReadError(ReasonCode.SOURCE_READ_FAILED, _ref(1, 1)) from None
    return CatalogBatch(tuple(candidates), tuple(issues), rows_read)


def select_catalog_candidates(
    batch: CatalogBatch,
    price_issue_for: Callable[[CatalogCandidate], ReasonCode | None],
) -> CatalogSelection:
    """Selecciona solo tras validar el coste neto de cada candidato (F3).

    El callback devuelve None si el precio final es válido; si no, su motivo.
    Así una excepción XML válida puede rescatar un coste CSV inválido antes
    de escoger la primera fila válida del SKU.
    """

    winners: dict[str, CatalogCandidate] = {}
    issues = list(batch.issues)
    for candidate in batch.candidates:
        ref = candidate.record.ref
        reason = price_issue_for(candidate)
        if reason is not None:
            issues.append(
                _issue(
                    ref,
                    reason,
                    Action.REJECT_ROW,
                    "Precio final inválido",
                    candidate.raw_cells,
                    "precio_coste" if reason == candidate.cost_problem else None,
                )
            )
            continue
        if candidate.cost_problem is not None:
            issues.append(
                _issue(
                    ref,
                    candidate.cost_problem,
                    Action.DROP_FIELD,
                    "Coste CSV sustituido por precio válido",
                    candidate.raw_cells,
                    "precio_coste",
                )
            )
        previous = winners.get(candidate.record.payload.sku)
        if previous is None:
            winners[candidate.record.payload.sku] = candidate
            continue
        if candidate.raw_cells == previous.raw_cells:
            code, action, detail = ReasonCode.EXACT_DUPLICATE, Action.DEDUPLICATE, "Fila idéntica"
        else:
            code, action, detail = (
                ReasonCode.CONFLICTING_PRODUCT_SKU,
                Action.REJECT_ROW,
                "SKU conflictivo",
            )
        issues.append(
            _issue(
                ref,
                code,
                action,
                f"{detail}; conservada fila {previous.record.ref.locator}",
                candidate.raw_cells,
            )
        )

    rejected = {issue.ref.locator for issue in issues if issue.action == Action.REJECT_ROW}
    deduplicated = {issue.ref.locator for issue in issues if issue.action == Action.DEDUPLICATE}
    return CatalogSelection(
        tuple(winners.values()),
        tuple(issues),
        batch.rows_read,
        len(winners),
        len(rejected),
        len(deduplicated),
    )
