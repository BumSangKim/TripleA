from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.features.backtests.sector_component_config import SectorComponentWeightSet
from api.features.backtests.sector_component_models import SectorComponentObservation, SectorComponentSnapshot
from api.features.backtests.sector_component_sensitivity import (
    SectorComponentSensitivityError,
    run_sector_component_sensitivity,
)


AVAILABLE_AT = datetime(2026, 5, 30, 9, tzinfo=UTC)


def observation(component: str, score: float, as_of: date) -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name=component,
        score=score,
        as_of_date=as_of,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id=f"raw-{component}-{as_of.isoformat()}",
    )


def snapshot(as_of: date, trade: float, demand: float) -> SectorComponentSnapshot:
    return SectorComponentSnapshot(
        sector_id="SEMICONDUCTOR",
        as_of_date=as_of,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id=f"snapshot-{as_of.isoformat()}",
        observations=(observation("trade", trade, as_of), observation("demand", demand, as_of)),
        required_components=("trade", "demand"),
    )


def snapshots():
    return (
        snapshot(date(2026, 3, 31), trade=0.8, demand=0.3),
        snapshot(date(2026, 4, 30), trade=0.7, demand=0.4),
        snapshot(date(2026, 5, 31), trade=0.2, demand=0.9),
    )


def weight_grid():
    return (
        SectorComponentWeightSet("demand_light", {"trade": 0.8, "demand": 0.2}),
        SectorComponentWeightSet("demand_heavy", {"trade": 0.2, "demand": 0.8}),
    )


def test_multiple_parameter_combinations_run() -> None:
    results = run_sector_component_sensitivity(snapshots(), weight_grid(), forward_returns={date(2026, 5, 31): 0.10})

    assert {result.parameter_set_id for result in results} == {"demand_light", "demand_heavy"}
    assert all(result.metric_summary.observation_count >= 1 for result in results)


def test_fixed_input_is_reproducible() -> None:
    first = run_sector_component_sensitivity(snapshots(), weight_grid())
    second = run_sector_component_sensitivity(tuple(reversed(snapshots())), tuple(reversed(weight_grid())))

    assert [result.to_dict() for result in first] == [result.to_dict() for result in second]


def test_parameter_version_is_preserved() -> None:
    results = run_sector_component_sensitivity(snapshots(), weight_grid())

    assert {result.parameter_version for result in results} == {"p1"}
    assert {result.model_version for result in results} == {"m1"}


def test_invalid_or_missing_parameter_grid_is_blocked() -> None:
    with pytest.raises(SectorComponentSensitivityError, match="weight_grid"):
        run_sector_component_sensitivity(snapshots(), ())
    with pytest.raises(SectorComponentSensitivityError, match="sum to 1.0"):
        run_sector_component_sensitivity(snapshots(), (SectorComponentWeightSet("bad", {"trade": 0.8}),))


def test_highest_return_parameter_set_is_not_auto_approved() -> None:
    results = run_sector_component_sensitivity(snapshots(), weight_grid(), forward_returns={date(2026, 5, 31): 0.20})

    assert min(result.rank for result in results if result.rank is not None) == 1
    assert all(result.approved_for_production is False for result in results)


def test_fragility_warning_on_large_dispersion() -> None:
    results = run_sector_component_sensitivity(snapshots(), weight_grid(), fragility_threshold=0.01)

    assert any(any(warning.code == "PARAMETER_FRAGILITY" for warning in result.warnings) for result in results)


def test_results_are_sector_and_component_decomposable() -> None:
    result = run_sector_component_sensitivity(snapshots(), weight_grid())[0]

    assert result.sector_id == "SEMICONDUCTOR"
    assert set(result.component_weights) == {"trade", "demand"}
    assert result.metric_summary.sector_id == "SEMICONDUCTOR"

