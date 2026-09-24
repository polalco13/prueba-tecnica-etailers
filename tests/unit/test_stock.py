"""Observaciones y resultados esperados sintéticos, independientes de la API real."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.etl.records import SourceRecord, SourceRef
from src.etl.stock import reconcile_stock
from src.etl.stock_client import StockSnapshot


def row(**changes: object) -> dict:
    return {
        "sku": "A",
        "warehouse": "MAD",
        "quantity": 5,
        "reserved": 2,
        "updated_at": "2026-01-01T00:00:00Z",
        **changes,
    }


def reconcile(rows: list, skus: set[str] | None = None):
    snapshot = StockSnapshot(
        tuple(
            SourceRecord(SourceRef("stock_api", f"page:1/row:{i}"), value)
            for i, value in enumerate(rows, 1)
        ),
        "synthetic",
    )
    return reconcile_stock(snapshot, {"A"} if skus is None else skus)


def test_totals_are_physical_stock_reservations_separate_and_zero_is_known() -> None:
    result = reconcile(
        [
            row(sku=" a ", warehouse=" mad ", quantity="2,0", reserved=3),
            row(warehouse="BCN", quantity=Decimal("3.0")),
            row(sku="B", quantity=0, reserved=0),
        ],
        {"A", "B", "C"},
    )
    assert [(t.sku, t.quantity, t.status) for t in result.totals] == [
        ("A", 5, "known"),
        ("B", 0, "known"),
        ("C", None, "unknown"),
    ]
    assert sum(o.reserved for o in result.observations if o.sku == "A") == 5
    assert {i.reason_code for i in result.issues} == {
        "RESERVED_EXCEEDS_QUANTITY",
        "STOCK_NOT_OBSERVED",
    }
    assert result.counters.quality_warnings == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", -1),
        ("reserved", -1),
        ("quantity", "2,5"),
        ("quantity", None),
        ("reserved", "NULL"),
        ("quantity", True),
        ("quantity", float("nan")),
        ("quantity", "NaN"),
        ("quantity", 2**63),
        ("warehouse", ""),
        ("warehouse", "X" * 65),
        ("warehouse", []),
        ("updated_at", "2026-02-30T00:00:00Z"),
        ("updated_at", "2026-01-01T00:00:00"),
        ("updated_at", None),
        ("updated_at", "0999-01-01T00:00:00Z"),
    ],
)
def test_any_invalid_known_observation_prevents_partial_total(field: str, value: object) -> None:
    result = reconcile(
        [row(), row(warehouse="BCN", **{field: value})]
        if field != "warehouse"
        else [row(), row(warehouse=value)]
    )
    assert result.totals[0].status == "invalid"
    assert result.totals[0].quantity is None
    assert result.counters.rows_rejected == 1
    assert len(result.observations) == 1


def test_multiple_errors_count_one_rejected_row_and_keep_provenance() -> None:
    result = reconcile([row(quantity=-1, reserved=-2, updated_at="bad")])
    assert result.counters.rows_read == result.counters.rows_rejected == 1
    assert len(result.issues) == 3
    assert {issue.field_name for issue in result.issues} == {"quantity", "reserved", "updated_at"}
    assert all(
        issue.ref.entity_key == "A" and issue.ref.locator == "page:1/row:1"
        for issue in result.issues
    )


def test_exact_duplicates_and_older_versions_do_not_raise_rejected_count() -> None:
    result = reconcile([row(), row(), row(quantity=8, updated_at="2026-01-02T01:00:00+01:00")])
    assert result.totals[0].quantity == 8
    assert result.totals[0].as_of == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert result.counters.as_dict() == {
        "rows_read": 3,
        "rows_accepted": 1,
        "rows_rejected": 0,
        "rows_deduplicated": 2,
        "quality_warnings": 0,
        "discarded_fields": 0,
    }
    assert {i.reason_code for i in result.issues} == {"EXACT_DUPLICATE", "SUPERSEDED_STOCK"}


def test_conflict_same_instant_cannot_choose_first_or_sum_other_warehouse() -> None:
    result = reconcile([row(), row(quantity=9), row(warehouse="BCN", quantity=10)])
    assert result.totals[0].status == "invalid"
    assert result.counters.rows_rejected == 2
    assert result.counters.rows_accepted == 1
    assert result.counters.quality_warnings == 1
    assert all(o.warehouse != "MAD" for o in result.observations)


def test_even_older_conflict_is_not_silently_hidden() -> None:
    result = reconcile([row(), row(quantity=9), row(updated_at="2026-01-02T00:00:00Z")])
    assert result.totals[0].status == "invalid"
    assert result.counters.rows_accepted == 1
    assert result.counters.rows_rejected == 2


def test_unknown_sku_and_unidentifiable_rows_never_create_products() -> None:
    result = reconcile([row(sku="UNKNOWN"), row(sku=""), None])
    assert result.observations == ()
    assert [total.sku for total in result.totals] == ["A"]
    assert result.totals[0].status == "unknown"
    assert result.counters.rows_rejected == 3


def test_sum_overflow_makes_total_invalid_but_keeps_valid_observations() -> None:
    result = reconcile([row(quantity=2**63 - 1), row(warehouse="BCN", quantity=1)])
    assert result.totals[0].status == "invalid"
    assert result.counters.rows_accepted == 2
    assert "NUMERIC_OUT_OF_RANGE" in {issue.reason_code for issue in result.issues}


def test_complete_empty_stock_is_unknown_for_every_catalog_product() -> None:
    result = reconcile([], {"A", "B"})
    assert all(total.quantity is None and total.status == "unknown" for total in result.totals)
    assert result.counters.rows_read == 0
    assert result.counters.quality_warnings == 2


def test_audit_excerpt_keeps_stock_fields_but_excludes_unrelated_secrets() -> None:
    result = reconcile(
        [row(quantity=-1, token="synthetic-secret", headers={"Authorization": "secret"})]
    )
    excerpt = result.issues[0].raw_excerpt
    assert '"quantity": "-1"' in excerpt
    assert '"sku": "A"' in excerpt
    assert "secret" not in excerpt and "Authorization" not in excerpt
    assert len(excerpt) <= 512
