from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.features.backtests.sector_component_models import (
    SectorComponentAttributionRow,
    SectorComponentBacktestRequest,
    SectorComponentBacktestResult,
    SectorComponentMetricSummary,
    SectorComponentObservation,
    SectorComponentSensitivityResult,
    SectorComponentSnapshot,
    SectorComponentValidationWarning,
)


AS_OF = date(2026, 5, 31)
AVAILABLE_AT = datetime(2026, 5, 30, 9, tzinfo=UTC)
FUTURE_AVAILABLE_AT = datetime(2026, 6, 1, 9, tzinfo=UTC)


def observation(component_name: str = "trade", score: float | None = 0.7) -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name=component_name,
        score=score,
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        data_snapshot_id="snapshot-1",
        reason_codes=("COMPONENT_OBSERVED",),
        confidence=0.8,
        data_quality=0.9,
        source="fixture",
    )


def metric_summary() -> SectorComponentMetricSummary:
    return SectorComponentMetricSummary(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        data_snapshot_id="snapshot-1",
        total_return=0.12,
        annualized_return=0.08,
        max_drawdown=-0.04,
        volatility=0.11,
        observation_count=3,
    )


def test_contracts_preserve_dates_versions_and_snapshot_id() -> None:
    snapshot = SectorComponentSnapshot(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        data_snapshot_id="snapshot-1",
        observations=(observation("trade"), observation("demand")),
        required_components=("trade", "demand"),
    )

    assert snapshot.as_of_date == AS_OF
    assert snapshot.available_at == AVAILABLE_AT
    assert snapshot.parameter_version == "sector_component_v1"
    assert snapshot.model_version == "sector_component_model_v1"
    assert snapshot.data_snapshot_id == "snapshot-1"
    assert not snapshot.requires_review


def test_out_of_range_score_is_warning_not_risk_increasing_default() -> None:
    obs = observation(score=1.5)

    assert obs.requires_review
    assert obs.warnings[0].code == "COMPONENT_SCORE_OUT_OF_RANGE"
    assert obs.warnings[0].fallback_state == "REVIEW_REQUIRED"


def test_future_available_at_can_be_represented_for_later_filtering() -> None:
    obs = SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name="trade",
        score=0.6,
        as_of_date=AS_OF,
        available_at=FUTURE_AVAILABLE_AT,
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        data_snapshot_id="snapshot-future",
        warnings=(
            SectorComponentValidationWarning(
                sector_id="SEMICONDUCTOR",
                component_name="trade",
                as_of_date=AS_OF,
                available_at=FUTURE_AVAILABLE_AT,
                parameter_version="sector_component_v1",
                model_version="sector_component_model_v1",
                data_snapshot_id="snapshot-future",
                code="FUTURE_DATA_FILTER_REQUIRED",
                message="available_at is after decision date",
            ),
        ),
    )

    assert obs.available_at > datetime.combine(AS_OF, datetime.min.time(), tzinfo=UTC)
    assert obs.warnings[0].code == "FUTURE_DATA_FILTER_REQUIRED"


def test_missing_component_stays_review_required() -> None:
    snapshot = SectorComponentSnapshot(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        data_snapshot_id="snapshot-missing",
        observations=(observation("trade"),),
        required_components=("trade", "demand"),
    )

    assert snapshot.requires_review
    assert snapshot.fallback_state == "HOLD"
    assert snapshot.warnings[0].code == "COMPONENT_REQUIRED_INPUT_MISSING"


def test_backtest_request_rejects_invalid_dates() -> None:
    with pytest.raises(ValueError, match="start_date"):
        SectorComponentBacktestRequest(
            sector_id="SEMICONDUCTOR",
            as_of_date=AS_OF,
            available_at=AVAILABLE_AT,
            parameter_version="sector_component_v1",
            model_version="sector_component_model_v1",
            data_snapshot_id="snapshot-1",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 5, 1),
            enabled_components=("trade",),
        )


def test_sensitivity_result_never_auto_approves_production() -> None:
    with pytest.raises(ValueError, match="auto-approve"):
        SectorComponentSensitivityResult(
            sector_id="SEMICONDUCTOR",
            as_of_date=AS_OF,
            available_at=AVAILABLE_AT,
            parameter_version="sector_component_v1",
            model_version="sector_component_model_v1",
            data_snapshot_id="snapshot-1",
            parameter_set_id="param-best-return",
            component_weights={"trade": 1.0},
            metric_summary=metric_summary(),
            approved_for_production=True,
        )


def test_serialization_matches_project_dict_style() -> None:
    result = SectorComponentBacktestResult(
        sector_id="SEMICONDUCTOR",
        as_of_date=AS_OF,
        available_at=AVAILABLE_AT,
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        data_snapshot_id="snapshot-1",
        metric_summaries=(metric_summary(),),
        attribution_rows=(
            SectorComponentAttributionRow(
                sector_id="SEMICONDUCTOR",
                component_name="trade",
                as_of_date=AS_OF,
                available_at=AVAILABLE_AT,
                parameter_version="sector_component_v1",
                model_version="sector_component_model_v1",
                data_snapshot_id="snapshot-1",
                score=0.7,
                weight=0.6,
                weighted_contribution=0.42,
                contribution_share=1.0,
            ),
        ),
        status="OK",
    )

    payload = result.to_dict()

    assert payload["as_of_date"] == "2026-05-31"
    assert payload["available_at"] == "2026-05-30T09:00:00+00:00"
    assert payload["metric_summaries"][0]["data_snapshot_id"] == "snapshot-1"
    assert payload["attribution_rows"][0]["component_name"] == "trade"

