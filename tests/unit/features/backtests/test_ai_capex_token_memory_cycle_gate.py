from __future__ import annotations

from dataclasses import dataclass

from api.features.backtests.ai_capex_token_memory_cycle_gate import (
    PASS_STATUS,
    REVIEW_STATUS,
    validate_two_memory_cycle_coverage,
)


@dataclass(frozen=True)
class SnapshotObject:
    metadata: dict[str, str]


def test_two_explicit_cycles_pass():
    result = validate_two_memory_cycle_coverage(
        (
            {"metadata": {"memory_cycle_id": "cycle_a"}},
            {"metadata": {"memory_cycle_id": "cycle_b"}},
            {"metadata": {"memory_cycle_id": "cycle_b"}},
        )
    )

    assert result.status == PASS_STATUS
    assert result.distinct_cycle_count == 2
    assert result.cycle_ids == ("cycle_a", "cycle_b")
    assert result.historical_tuning_allowed is True
    assert "TWO_MEMORY_CYCLE_COVERAGE_PASSED" in result.reason_codes


def test_one_cycle_returns_review_required():
    result = validate_two_memory_cycle_coverage(
        (
            {"metadata": {"memory_cycle_id": "cycle_a"}},
            {"metadata": {"memory_cycle_id": "cycle_a"}},
        )
    )

    assert result.status == REVIEW_STATUS
    assert result.distinct_cycle_count == 1
    assert result.historical_tuning_allowed is False
    assert result.reason_codes == ("INSUFFICIENT_MEMORY_CYCLE_COVERAGE",)


def test_missing_cycle_id_returns_review_required():
    result = validate_two_memory_cycle_coverage(({"metadata": {"period": "2025Q1"}}, {"as_of_date": "2025-04-01"}))

    assert result.status == REVIEW_STATUS
    assert result.distinct_cycle_count == 0
    assert result.cycle_ids == ()
    assert result.reason_codes == ("MEMORY_CYCLE_ID_MISSING",)


def test_empty_snapshots_return_review_required():
    result = validate_two_memory_cycle_coverage(())

    assert result.status == REVIEW_STATUS
    assert result.distinct_cycle_count == 0
    assert result.reason_codes == ("MEMORY_CYCLE_SNAPSHOTS_MISSING",)


def test_object_metadata_and_row_metadata_are_supported_without_date_inference():
    result = validate_two_memory_cycle_coverage(
        (
            SnapshotObject(metadata={"memory_cycle_id": "cycle_object"}),
            {"row_metadata": {"cycle_id": "cycle_row"}},
        )
    )

    assert result.status == PASS_STATUS
    assert result.cycle_ids == ("cycle_object", "cycle_row")
