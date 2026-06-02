from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from api.score_pipeline.contracts import PipelineContractError
from api.score_pipeline.memory_cycle import (
    MemoryCycleCoverageStatus,
    MemoryCycleProxyPoint,
    evaluate_memory_cycle_coverage,
)


def test_synthetic_two_cycle_sequence_passes():
    report = evaluate_memory_cycle_coverage(
        _points([100, 70, 102, 68, 105]),
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 5, 31),
        decision_date=date(2024, 5, 31),
        min_points=5,
    )

    assert report.status == MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES
    assert report.complete_cycle_count == 2
    assert report.tuning_allowed is True
    assert report.proxy_names_used == ("dram_asp_index",)


def test_one_complete_cycle_fails_hard_gate():
    report = evaluate_memory_cycle_coverage(
        _points([100, 70, 102]),
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 3, 31),
        decision_date=date(2024, 3, 31),
        min_points=3,
    )

    assert report.status == MemoryCycleCoverageStatus.INSUFFICIENT_MEMORY_CYCLE_COVERAGE
    assert report.complete_cycle_count == 1
    assert report.tuning_allowed is False


def test_noisy_valid_two_cycle_sequence_passes_with_conservative_swing_filter():
    values = [100, 97, 72, 75, 101, 96, 69, 73, 106]
    report = evaluate_memory_cycle_coverage(
        _points(values),
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 9, 30),
        decision_date=date(2024, 9, 30),
        min_points=8,
        min_swing_ratio=0.18,
    )

    assert report.status == MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES
    assert report.complete_cycle_count == 2


def test_ambiguous_boundary_sequence_fails():
    report = evaluate_memory_cycle_coverage(
        _points([100, 102, 104, 106, 108, 110]),
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 6, 30),
        decision_date=date(2024, 6, 30),
        min_points=6,
    )

    assert report.status == MemoryCycleCoverageStatus.AMBIGUOUS_CYCLE_BOUNDARIES
    assert report.complete_cycle_count == 0


def test_insufficient_proxy_data_fails_before_boundary_detection():
    report = evaluate_memory_cycle_coverage(
        _points([100, 70]),
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 2, 29),
        decision_date=date(2024, 2, 29),
        min_points=3,
    )

    assert report.status == MemoryCycleCoverageStatus.INSUFFICIENT_PROXY_DATA
    assert report.complete_cycle_count == 0


def test_future_proxy_points_are_excluded_from_cycle_proof():
    safe = _points([100, 70, 102, 68, 105])
    future = MemoryCycleProxyPoint(
        proxy_name="dram_asp_index",
        observed_on=date(2024, 6, 30),
        value=60.0,
        available_at=datetime(2024, 7, 1, 0, 0, 0),
    )

    report = evaluate_memory_cycle_coverage(
        [*safe, future],
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 6, 30),
        decision_date=date(2024, 6, 30),
        min_points=5,
    )

    assert report.status == MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES
    assert "FUTURE_PROXY_POINTS_EXCLUDED" in report.reason_codes
    assert all(segment.end_date <= date(2024, 6, 30) for segment in report.cycle_boundaries)


def test_unknown_memory_proxy_is_rejected():
    with pytest.raises(PipelineContractError):
        MemoryCycleProxyPoint(
            proxy_name="not_a_memory_proxy",
            observed_on=date(2024, 1, 31),
            value=1.0,
            available_at=datetime(2024, 1, 31, 0, 0, 0),
        )


def test_gate_source_does_not_prove_cycles_with_hardcoded_calendar_dates():
    source = Path("api/score_pipeline/memory_cycle.py").read_text(encoding="utf-8")

    for forbidden_year in ("2018", "2020", "2021", "2022", "2023", "2024", "2025", "2026"):
        assert forbidden_year not in source


def _points(values: list[float], *, proxy_name: str = "dram_asp_index") -> list[MemoryCycleProxyPoint]:
    points: list[MemoryCycleProxyPoint] = []
    for index, value in enumerate(values, start=1):
        month = index
        observed_on = date(2024, month, 29 if month == 2 else 30 if month in {4, 6, 9, 11} else 31)
        points.append(
            MemoryCycleProxyPoint(
                proxy_name=proxy_name,
                observed_on=observed_on,
                value=value,
                available_at=datetime(2024, month, 29 if month == 2 else 30 if month in {4, 6, 9, 11} else 31, 0, 0, 0),
            )
        )
    return points
