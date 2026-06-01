from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.features.backtests.sector_component_models import (
    SectorComponentBacktestResult,
    SectorComponentMetricSummary,
    SectorComponentValidationWarning,
)
from api.features.backtests.sector_component_scope import (
    SECTOR_COMPONENT_SCOPE_SEMANTICS,
    SectorComponentComparisonRow,
    SectorComponentScope,
    SectorComponentScopedBacktestResult,
)


AS_OF = date(2026, 5, 31)
AVAILABLE_AT = datetime(2026, 5, 30, 9, tzinfo=UTC)


def metric_summary() -> SectorComponentMetricSummary:
    return SectorComponentMetricSummary(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="metric-1",
        total_return=0.03,
        max_drawdown=-0.01,
        volatility=0.02,
        hit_rate=0.5,
        observation_count=2,
    )


def sector_result() -> SectorComponentBacktestResult:
    return SectorComponentBacktestResult(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="result-1",
        metric_summaries=(metric_summary(),),
        status="OK",
        reason_codes=("SECTOR_COMPONENT_BACKTEST_RUNNER_COMPLETED",),
    )


def warning() -> SectorComponentValidationWarning:
    return SectorComponentValidationWarning(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="warning-1",
        code="REVIEW_REQUIRED",
        message="review required",
    )


def comparison_row(status: str = "OK") -> SectorComponentComparisonRow:
    return SectorComponentComparisonRow(
        sector_id="SEMICONDUCTOR",
        display_name="Semiconductor",
        portfolio_id="sector_semiconductor_current_v1",
        status=status,
        total_return=0.03,
        max_drawdown=-0.01,
        volatility=0.02,
        hit_rate=0.5,
        observation_count=2,
        warning_count=0,
        reason_codes=("SECTOR_COMPONENT_SCOPE_RESULT",),
    )


def test_all_scope_creation() -> None:
    scope = SectorComponentScope(mode="all")

    assert scope.mode == "all"
    assert scope.sector_id is None


def test_single_scope_creation() -> None:
    scope = SectorComponentScope(mode="single", sector_id="SEMICONDUCTOR")

    assert scope.mode == "single"
    assert scope.sector_id == "SEMICONDUCTOR"


def test_single_without_sector_id_fails() -> None:
    with pytest.raises(ValueError, match="requires sector_id"):
        SectorComponentScope(mode="single")


def test_all_with_sector_id_fails() -> None:
    with pytest.raises(ValueError, match="must not include sector_id"):
        SectorComponentScope(mode="all", sector_id="SEMICONDUCTOR")


def test_invalid_mode_fails() -> None:
    with pytest.raises(ValueError, match="all or single"):
        SectorComponentScope(mode="selected", sector_id="SEMICONDUCTOR")


def test_conservative_status_only() -> None:
    assert comparison_row(status="REVIEW_REQUIRED").status == "REVIEW_REQUIRED"
    with pytest.raises(ValueError, match="status"):
        comparison_row(status="BUY")
    with pytest.raises(ValueError, match="status"):
        SectorComponentScopedBacktestResult(
            sector_scope=SectorComponentScope(mode="all"),
            parameter_version="p1",
            model_version="m1",
            data_snapshot_id="scope-1",
            status="AUTO_EXECUTE",
        )


def test_to_dict_serialization_matches_model_style() -> None:
    result = SectorComponentScopedBacktestResult(
        sector_scope=SectorComponentScope(mode="single", sector_id="SEMICONDUCTOR"),
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="scope-1",
        status="REVIEW_REQUIRED",
        comparison_rows=(comparison_row(status="REVIEW_REQUIRED"),),
        sector_results=(sector_result(),),
        warnings=(warning(),),
        reason_codes=("REVIEW_REQUIRED",),
    )

    payload = result.to_dict()

    assert payload["semantics"] == SECTOR_COMPONENT_SCOPE_SEMANTICS
    assert payload["sector_scope"] == {"mode": "single", "sector_id": "SEMICONDUCTOR"}
    assert payload["comparison_rows"][0]["sector_id"] == "SEMICONDUCTOR"
    assert payload["sector_results"][0]["metric_summaries"][0]["as_of_date"] == "2026-05-31"
    assert payload["warnings"][0]["available_at"] == "2026-05-30T09:00:00+00:00"
