"""Reglas puras de stock; una observación inválida impide publicar un total parcial."""

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal

from src.etl.normalize import normalize_identifier, parse_decimal, parse_timestamp
from src.etl.records import Action, Issue, NormalizationError, ReasonCode, Severity, SourceRef
from src.etl.stock_client import StockSnapshot

MAX_STOCK = 2**63 - 1


@dataclass(frozen=True, slots=True)
class Observation:
    sku: str
    warehouse: str
    quantity: int
    reserved: int
    updated_at: datetime
    ref: SourceRef


@dataclass(frozen=True, slots=True)
class StockTotal:
    sku: str
    quantity: int | None
    status: str
    as_of: datetime | None


@dataclass(frozen=True, slots=True)
class StockCounters:
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    rows_deduplicated: int
    quality_warnings: int
    discarded_fields: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReconciledStock:
    observations: tuple[Observation, ...]
    totals: tuple[StockTotal, ...]
    issues: tuple[Issue, ...]
    counters: StockCounters


def _identifier(value: object) -> str:
    if not isinstance(value, str):
        raise NormalizationError(ReasonCode.INVALID_STOCK)
    result = normalize_identifier(value)
    if result is None:
        raise NormalizationError(ReasonCode.INVALID_STOCK)
    return result


def _quantity(value: object) -> int:
    # bool no es una cantidad; Decimal procede del JSON sin pasar por float.
    if type(value) not in (str, int, Decimal):
        raise NormalizationError(ReasonCode.INVALID_STOCK)
    amount = parse_decimal(str(value))
    if amount is None or not 0 <= amount <= MAX_STOCK or amount != amount.to_integral_value():
        raise NormalizationError(ReasonCode.INVALID_STOCK)
    return int(amount)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise NormalizationError(ReasonCode.INVALID_DATE)
    stamp = parse_timestamp(value)
    if stamp is None or stamp.year < 1000:  # DATETIME de MySQL
        raise NormalizationError(ReasonCode.INVALID_DATE)
    return stamp


def _issue(ref: SourceRef, code: ReasonCode, action: Action, field: str | None = None) -> Issue:
    severity = Severity.WARNING if action == Action.WARN else Severity.ERROR
    if action == Action.DEDUPLICATE:
        severity = Severity.INFO
    return Issue(ref, code, action, severity, code.value, field)


def _excerpt(raw: object) -> str:
    """Solo campos de stock escalares; nunca copiar cabeceras ni claves ajenas."""
    if not isinstance(raw, dict):
        return f"Tipo de registro inválido: {type(raw).__name__}"
    fields = {}
    for key in ("sku", "warehouse", "quantity", "reserved", "updated_at"):
        value = raw.get(key)
        fields[key] = (
            str(value)[:70]
            if type(value) in (str, int, Decimal, float, bool)
            else None
            if value is None
            else "[tipo inválido]"
        )
    return json.dumps(fields, ensure_ascii=False)[:512]


def reconcile_stock(snapshot: StockSnapshot, catalog_skus: set[str]) -> ReconciledStock:
    issues: list[Issue] = []
    invalid: set[str] = set()
    groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    rejected = deduplicated = 0
    for record in snapshot.rows:
        raw = record.payload
        try:
            if not isinstance(raw, dict):
                raise NormalizationError(ReasonCode.INVALID_STOCK)
            sku = _identifier(raw.get("sku"))
        except NormalizationError:
            issues.append(_issue(record.ref, ReasonCode.INVALID_STOCK, Action.REJECT_ROW, "sku"))
            rejected += 1
            continue
        ref = replace(record.ref, entity_key=sku)
        if sku not in catalog_skus:
            issues.append(_issue(ref, ReasonCode.UNKNOWN_PRODUCT_SKU, Action.REJECT_ROW))
            rejected += 1
            continue
        values = {}
        for field, parser in (
            ("warehouse", _identifier),
            ("quantity", _quantity),
            ("reserved", _quantity),
            ("updated_at", _timestamp),
        ):
            try:
                values[field] = parser(raw.get(field))
            except NormalizationError:
                code = (
                    ReasonCode.INVALID_DATE if field == "updated_at" else ReasonCode.INVALID_STOCK
                )
                issues.append(_issue(ref, code, Action.REJECT_ROW, field))
        if len(values) != 4:
            invalid.add(sku)
            rejected += 1
            continue
        observation = Observation(sku=sku, ref=ref, **values)
        if observation.reserved > observation.quantity:
            issues.append(_issue(ref, ReasonCode.RESERVED_EXCEEDS_QUANTITY, Action.WARN))
        groups[(sku, observation.warehouse)].append(observation)

    accepted: list[Observation] = []
    for (sku, _warehouse), observations in sorted(groups.items()):
        instants: dict[datetime, list[Observation]] = defaultdict(list)
        signatures: set[tuple[int, int, datetime]] = set()
        for observation in observations:
            signature = (observation.quantity, observation.reserved, observation.updated_at)
            if signature in signatures:
                issues.append(
                    _issue(observation.ref, ReasonCode.EXACT_DUPLICATE, Action.DEDUPLICATE)
                )
                deduplicated += 1
            else:
                signatures.add(signature)
                instants[observation.updated_at].append(observation)
        latest = max(instants)
        for instant, versions in instants.items():
            if len(versions) > 1:
                invalid.add(sku)
                for observation in versions:
                    issues.append(
                        _issue(observation.ref, ReasonCode.CONFLICTING_STOCK, Action.REJECT_ROW)
                    )
                    rejected += 1
                issues.append(
                    _issue(
                        SourceRef(
                            "stock_api", f"conflict:{sku}:{_warehouse}:{instant.isoformat()}", sku
                        ),
                        ReasonCode.CONFLICTING_STOCK,
                        Action.WARN,
                    )
                )
            elif instant != latest:
                issues.append(
                    _issue(versions[0].ref, ReasonCode.SUPERSEDED_STOCK, Action.DEDUPLICATE)
                )
                deduplicated += 1
            else:
                accepted.append(versions[0])

    by_sku: dict[str, list[Observation]] = defaultdict(list)
    for observation in accepted:
        by_sku[observation.sku].append(observation)
    totals = []
    for sku in sorted(catalog_skus):
        observations = by_sku[sku]
        total = sum(observation.quantity for observation in observations)
        ref = SourceRef("stock_api", f"sku:{sku}", sku)
        if total > MAX_STOCK:
            invalid.add(sku)
            issues.append(_issue(ref, ReasonCode.NUMERIC_OUT_OF_RANGE, Action.WARN))
        if sku in invalid:
            totals.append(StockTotal(sku, None, "invalid", None))
        elif not observations:
            totals.append(StockTotal(sku, None, "unknown", None))
            issues.append(_issue(ref, ReasonCode.STOCK_NOT_OBSERVED, Action.WARN))
        else:
            totals.append(
                StockTotal(sku, total, "known", max(row.updated_at for row in observations))
            )
    counters = StockCounters(
        len(snapshot.rows),
        len(accepted),
        rejected,
        deduplicated,
        sum(issue.action == Action.WARN for issue in issues),
    )
    if counters.rows_read != counters.rows_accepted + rejected + deduplicated:
        raise ValueError("Contadores de stock inconsistentes")
    excerpts = {row.ref.locator: _excerpt(row.payload) for row in snapshot.rows}
    audited = tuple(replace(issue, raw_excerpt=excerpts.get(issue.ref.locator)) for issue in issues)
    return ReconciledStock(tuple(accepted), tuple(totals), audited, counters)
