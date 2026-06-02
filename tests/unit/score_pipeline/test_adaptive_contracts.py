from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

import pytest

from api.score_pipeline.adaptive import (
    AdaptiveCalibrationReport,
    AdaptiveCalibrationWindow,
    AdaptiveNormalizationConfig,
    AdaptiveNormalizationMethod,
    AdaptiveNormalizedValue,
    StaticValueAuditResult,
    to_serializable_dict,
)
from api.score_pipeline.contracts import ConservativeAction, PipelineContractError


def test_adaptive_normalization_config_validates_fields():
    config = _config()

    assert config.method == AdaptiveNormalizationMethod.ROLLING_PERCENTILE
    assert config.min_observations == 24


def test_invalid_method_is_rejected():
    with pytest.raises(PipelineContractError):
        AdaptiveNormalizationConfig(
            method="rolling_percentile",  # type: ignore[arg-type]
            lookback_periods=24,
            lookback_months=24,
            min_observations=24,
            parameter_version="params-v1",
            model_version="adaptive-v1",
        )


def test_insufficient_observations_produce_conservative_fallback_report():
    report = AdaptiveCalibrationReport.from_window(
        _config(min_observations=24),
        _window(observation_count=12),
    )

    assert report.is_usable is False
    assert report.fallback_state == ConservativeAction.REVIEW_REQUIRED
    assert "INSUFFICIENT_ADAPTIVE_CALIBRATION_OBSERVATIONS" in report.reason_codes


def test_normalized_value_requires_conservative_fallback_when_calibration_unusable():
    report = AdaptiveCalibrationReport.from_window(
        _config(min_observations=24),
        _window(observation_count=12),
    )

    with pytest.raises(PipelineContractError):
        AdaptiveNormalizedValue(
            raw_value=1.2,
            normalized_value=0.5,
            method=AdaptiveNormalizationMethod.ROLLING_PERCENTILE,
            calibration_report=report,
            confidence=0.5,
            data_quality=0.5,
            parameter_version="params-v1",
            model_version="adaptive-v1",
        )

    value = AdaptiveNormalizedValue(
        raw_value=1.2,
        normalized_value=0.5,
        method=AdaptiveNormalizationMethod.ROLLING_PERCENTILE,
        calibration_report=report,
        confidence=0.5,
        data_quality=0.5,
        parameter_version="params-v1",
        model_version="adaptive-v1",
        fallback_state=ConservativeAction.HOLD,
        reason_codes=("UNUSABLE_CALIBRATION_HOLD",),
    )

    assert value.fallback_state == ConservativeAction.HOLD


def test_fit_window_cannot_extend_beyond_decision_date_or_available_cutoff():
    with pytest.raises(PipelineContractError):
        _window(
            fit_start_date=date(2025, 1, 31),
            fit_end_date=date(2026, 2, 28),
            decision_date=date(2026, 1, 31),
        )

    with pytest.raises(PipelineContractError):
        _window(
            decision_date=date(2026, 1, 31),
            available_at_cutoff=datetime(2026, 2, 1, 0, 0, 0),
        )


def test_static_value_audit_flags_hardcoded_action_mappings():
    result = StaticValueAuditResult.audit_mapping(
        "ai_capex_token_test_mapping",
        {
            "S1": {"fixed_weight": 0.6, "action": "BUY"},
            "S7": {"fallback": "REVIEW_REQUIRED"},
        },
    )

    assert result.is_blocking is True
    assert result.action_mapping_terms == ("S1.action",)
    assert "S1.fixed_weight" in result.static_values_found


def test_static_value_audit_allows_metadata_values_without_actions():
    result = StaticValueAuditResult.audit_mapping(
        "parameter_metadata",
        {"lookback_months": 36, "min_observations": 24, "method": "rolling_percentile"},
    )

    assert result.is_blocking is False
    assert result.action_mapping_terms == ()
    assert result.static_values_found == ("lookback_months", "method", "min_observations")


def test_contracts_are_serializable_with_existing_dataclass_style():
    report = AdaptiveCalibrationReport.from_window(_config(), _window())
    payload = to_serializable_dict(report)

    assert payload == asdict(report)
    assert payload["parameter_version"] == "params-v1"


def _config(*, min_observations: int = 24) -> AdaptiveNormalizationConfig:
    return AdaptiveNormalizationConfig(
        method=AdaptiveNormalizationMethod.ROLLING_PERCENTILE,
        lookback_periods=36,
        lookback_months=36,
        min_observations=min_observations,
        parameter_version="params-v1",
        model_version="adaptive-v1",
    )


def _window(
    *,
    fit_start_date: date = date(2023, 2, 28),
    fit_end_date: date = date(2026, 1, 31),
    decision_date: date = date(2026, 1, 31),
    observation_count: int = 36,
    available_at_cutoff: datetime = datetime(2026, 1, 31, 23, 59, 59),
) -> AdaptiveCalibrationWindow:
    return AdaptiveCalibrationWindow(
        fit_start_date=fit_start_date,
        fit_end_date=fit_end_date,
        decision_date=decision_date,
        observation_count=observation_count,
        available_at_cutoff=available_at_cutoff,
        parameter_version="params-v1",
        model_version="adaptive-v1",
    )
