from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Mapping

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenFallbackState, AICapexTokenScenarioDistribution
from api.score_pipeline.adaptive import AdaptiveNormalizedValue
from api.score_pipeline.contracts import clamp_ratio


SCENARIO_GRID = {
    "S1": ("increase", "acceleration"),
    "S2": ("increase", "stable"),
    "S3": ("increase", "deceleration"),
    "S4": ("stable", "acceleration"),
    "S5": ("stable", "stable"),
    "S6": ("stable", "deceleration"),
    "S7": ("decrease", "acceleration"),
    "S8": ("decrease", "stable"),
    "S9": ("decrease", "deceleration"),
}

TOKEN_AXIS_CENTERS = {"decrease": 0.0, "stable": 0.5, "increase": 1.0}
CAPEX_AXIS_CENTERS = {"deceleration": 0.0, "stable": 0.5, "acceleration": 1.0}


@dataclass(frozen=True)
class AICapexTokenAdaptiveScenarioInput:
    as_of_date: date
    token_delta: AdaptiveNormalizedValue
    capex_acceleration: AdaptiveNormalizedValue
    previous_distribution: Mapping[str, float] | None = None


def evaluate_adaptive_ai_capex_token_scenario(
    scenario_input: AICapexTokenAdaptiveScenarioInput,
    *,
    config: Mapping[str, object] | None = None,
) -> AICapexTokenScenarioDistribution:
    if not scenario_input.token_delta.calibration_report.is_usable or not scenario_input.capex_acceleration.calibration_report.is_usable:
        return _fallback_distribution(scenario_input, "SCENARIO_CALIBRATION_REVIEW_REQUIRED")
    token_width = _membership_width(scenario_input.token_delta)
    capex_width = _membership_width(scenario_input.capex_acceleration)
    token_membership = _axis_membership(scenario_input.token_delta.normalized_value, TOKEN_AXIS_CENTERS, token_width)
    capex_membership = _axis_membership(scenario_input.capex_acceleration.normalized_value, CAPEX_AXIS_CENTERS, capex_width)
    raw = {
        scenario: token_membership[token_state] * capex_membership[capex_state]
        for scenario, (token_state, capex_state) in SCENARIO_GRID.items()
    }
    probabilities = _normalize(raw)
    probabilities = _smooth(probabilities, scenario_input.previous_distribution, config)
    dominant = max(probabilities, key=lambda key: (probabilities[key], key))
    confidence = _confidence(scenario_input, probabilities)
    return AICapexTokenScenarioDistribution(
        as_of_date=scenario_input.as_of_date,
        probabilities=probabilities,
        dominant_scenario=dominant,
        dominant_scenario_explanation_only=True,
        data_quality=min(scenario_input.token_delta.data_quality, scenario_input.capex_acceleration.data_quality),
        confidence=confidence,
        reason_codes=("AI_CAPEX_TOKEN_ADAPTIVE_SCENARIO_DISTRIBUTION",),
        warnings=(),
        parameter_version=scenario_input.token_delta.parameter_version,
        model_version=scenario_input.token_delta.model_version,
    )


def _membership_width(value: AdaptiveNormalizedValue) -> float:
    report = value.calibration_report
    if report.observation_count <= 0:
        return 0.5
    coverage_ratio = min(1.0, report.observation_count / max(report.min_observations, 1))
    return max(0.18, min(0.45, 0.45 - 0.17 * coverage_ratio))


def _axis_membership(value: float, centers: Mapping[str, float], width: float) -> dict[str, float]:
    raw = {name: max(0.0, 1.0 - abs(clamp_ratio(value) - center) / width) for name, center in centers.items()}
    if sum(raw.values()) <= 0:
        closest = min(centers, key=lambda name: abs(clamp_ratio(value) - centers[name]))
        raw[closest] = 1.0
    return _normalize(raw)


def _smooth(
    probabilities: dict[str, float],
    previous_distribution: Mapping[str, float] | None,
    config: Mapping[str, object] | None,
) -> dict[str, float]:
    if not previous_distribution:
        return probabilities
    smoothing = config.get("scenario_smoothing") if isinstance(config, Mapping) else None
    if not isinstance(smoothing, Mapping) or smoothing.get("method") in {None, "none"}:
        return probabilities
    if smoothing.get("method") == "exponential":
        alpha = clamp_ratio(float(smoothing.get("ewma_alpha", 0.5)))
        return _normalize(
            {
                scenario: alpha * probabilities[scenario] + (1.0 - alpha) * float(previous_distribution.get(scenario, 0.0))
                for scenario in SCENARIO_GRID
            }
        )
    if smoothing.get("method") == "rolling_mean":
        return _normalize(
            {
                scenario: (probabilities[scenario] + float(previous_distribution.get(scenario, 0.0))) / 2.0
                for scenario in SCENARIO_GRID
            }
        )
    return probabilities


def _confidence(
    scenario_input: AICapexTokenAdaptiveScenarioInput,
    probabilities: Mapping[str, float],
) -> float:
    concentration = max(probabilities.values()) if probabilities else 0.0
    data_quality = min(scenario_input.token_delta.data_quality, scenario_input.capex_acceleration.data_quality)
    input_confidence = min(scenario_input.token_delta.confidence, scenario_input.capex_acceleration.confidence)
    return clamp_ratio(concentration * data_quality * input_confidence)


def _fallback_distribution(
    scenario_input: AICapexTokenAdaptiveScenarioInput,
    reason_code: str,
) -> AICapexTokenScenarioDistribution:
    probabilities = {scenario: 1.0 / len(SCENARIO_GRID) for scenario in SCENARIO_GRID}
    return AICapexTokenScenarioDistribution(
        as_of_date=scenario_input.as_of_date,
        probabilities=probabilities,
        dominant_scenario="S9",
        dominant_scenario_explanation_only=True,
        data_quality=min(scenario_input.token_delta.data_quality, scenario_input.capex_acceleration.data_quality),
        confidence=0.0,
        fallback_state=AICapexTokenFallbackState.REVIEW_REQUIRED,
        reason_codes=(reason_code,),
        warnings=("adaptive_scenario_distribution_diagnostic_only",),
        parameter_version=scenario_input.token_delta.parameter_version,
        model_version=scenario_input.token_delta.model_version,
    )


def _normalize(raw: Mapping[str, float]) -> dict[str, float]:
    total = sum(value for value in raw.values() if isfinite(value) and value >= 0.0)
    if total <= 0:
        return {key: 1.0 / len(raw) for key in raw}
    return {key: max(0.0, value) / total for key, value in raw.items()}
