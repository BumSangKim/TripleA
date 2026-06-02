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
)
from api.score_pipeline.contracts import ConservativeAction
from api.score_pipeline.plugins.ai_capex_token_scenario import (
    AICapexTokenAdaptiveScenarioInput,
    evaluate_adaptive_ai_capex_token_scenario,
)


def test_all_nine_scenarios_are_represented_and_sum_to_one():
    distribution = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(
            as_of_date=date(2026, 1, 31),
            token_delta=_value(0.9),
            capex_acceleration=_value(0.9),
        )
    )

    assert set(distribution.probabilities) == {f"S{i}" for i in range(1, 10)}
    assert sum(distribution.probabilities.values()) == pytest.approx(1.0)
    assert distribution.dominant_scenario == "S1"
    assert distribution.dominant_scenario_explanation_only is True


def test_tiny_changes_near_stable_do_not_create_large_distribution_shift():
    positive_tiny = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(
            as_of_date=date(2026, 1, 31),
            token_delta=_value(0.51),
            capex_acceleration=_value(0.51),
        )
    )
    negative_tiny = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(
            as_of_date=date(2026, 1, 31),
            token_delta=_value(0.49),
            capex_acceleration=_value(0.49),
        )
    )

    shift = sum(abs(positive_tiny.probabilities[key] - negative_tiny.probabilities[key]) for key in positive_tiny.probabilities)
    assert shift < 0.2
    assert positive_tiny.dominant_scenario == "S5"
    assert negative_tiny.dominant_scenario == "S5"


def test_poor_data_quality_lowers_confidence():
    high_quality = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(date(2026, 1, 31), _value(0.9), _value(0.9))
    )
    poor_quality = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(date(2026, 1, 31), _value(0.9, data_quality=0.4), _value(0.9, data_quality=0.4))
    )

    assert poor_quality.confidence < high_quality.confidence
    assert poor_quality.data_quality == 0.4


def test_insufficient_calibration_returns_review_required_neutral_distribution():
    distribution = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(
            as_of_date=date(2026, 1, 31),
            token_delta=_value(0.9, usable=False),
            capex_acceleration=_value(0.9),
        )
    )

    assert distribution.fallback_state is not None
    assert distribution.fallback_state.value == ConservativeAction.REVIEW_REQUIRED
    assert len(set(distribution.probabilities.values())) == 1
    assert distribution.confidence == 0.0


def test_exponential_smoothing_reduces_distribution_turnover_without_changing_availability():
    previous = {f"S{i}": 0.0 for i in range(1, 10)}
    previous["S7"] = 1.0
    scenario_input = AICapexTokenAdaptiveScenarioInput(
        as_of_date=date(2026, 1, 31),
        token_delta=_value(0.9),
        capex_acceleration=_value(0.9),
        previous_distribution=previous,
    )
    unsmoothed = evaluate_adaptive_ai_capex_token_scenario(scenario_input)
    smoothed = evaluate_adaptive_ai_capex_token_scenario(
        scenario_input,
        config={"scenario_smoothing": {"method": "exponential", "ewma_alpha": 0.5}},
    )

    unsmoothed_turnover = _distribution_distance(unsmoothed.probabilities, previous)
    smoothed_turnover = _distribution_distance(smoothed.probabilities, previous)

    assert smoothed_turnover < unsmoothed_turnover
    assert smoothed.as_of_date == unsmoothed.as_of_date


def test_output_contains_no_direct_action_or_target_weight_mapping():
    distribution = evaluate_adaptive_ai_capex_token_scenario(
        AICapexTokenAdaptiveScenarioInput(date(2026, 1, 31), _value(0.9), _value(0.9))
    )
    payload = asdict(distribution)

    forbidden = {"action", "buy", "sell", "target_weight", "order", "execution"}
    assert forbidden.isdisjoint(payload)
    assert all(forbidden.isdisjoint(str(key).lower() for key in nested) for nested in [payload["probabilities"]])


def _value(
    normalized_value: float,
    *,
    data_quality: float = 0.95,
    confidence: float = 0.9,
    usable: bool = True,
) -> AdaptiveNormalizedValue:
    config = AdaptiveNormalizationConfig(
        method=AdaptiveNormalizationMethod.ROLLING_PERCENTILE,
        lookback_periods=36,
        lookback_months=36,
        min_observations=24,
        parameter_version="adaptive-params-v1",
        model_version="adaptive-model-v1",
    )
    window = AdaptiveCalibrationWindow(
        fit_start_date=date(2024, 1, 31),
        fit_end_date=date(2026, 1, 31),
        decision_date=date(2026, 1, 31),
        observation_count=24 if usable else 12,
        available_at_cutoff=datetime(2026, 1, 31, 23, 59, 59),
        parameter_version=config.parameter_version,
        model_version=config.model_version,
    )
    report = AdaptiveCalibrationReport.from_window(config, window)
    return AdaptiveNormalizedValue(
        raw_value=normalized_value,
        normalized_value=normalized_value,
        method=config.method,
        calibration_report=report,
        confidence=confidence if usable else 0.0,
        data_quality=data_quality,
        parameter_version=config.parameter_version,
        model_version=config.model_version,
        fallback_state=None if usable else ConservativeAction.REVIEW_REQUIRED,
    )


def _distribution_distance(left, right) -> float:
    return sum(abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0))) for key in set(left) | set(right))
