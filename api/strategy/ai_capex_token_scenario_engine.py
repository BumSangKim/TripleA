from __future__ import annotations

from math import isfinite
from typing import Mapping

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenFallbackState,
    AICapexTokenFeatureSet,
    AICapexTokenScenarioDistribution,
    CapexAccelerationDirection,
    TokenConsumptionDirection,
)


SCENARIO_GRID = {
    "S1": (TokenConsumptionDirection.EXPANDING, CapexAccelerationDirection.ACCELERATING),
    "S2": (TokenConsumptionDirection.EXPANDING, CapexAccelerationDirection.STABLE),
    "S3": (TokenConsumptionDirection.EXPANDING, CapexAccelerationDirection.DECELERATING),
    "S4": (TokenConsumptionDirection.STABLE, CapexAccelerationDirection.ACCELERATING),
    "S5": (TokenConsumptionDirection.STABLE, CapexAccelerationDirection.STABLE),
    "S6": (TokenConsumptionDirection.STABLE, CapexAccelerationDirection.DECELERATING),
    "S7": (TokenConsumptionDirection.CONTRACTING, CapexAccelerationDirection.ACCELERATING),
    "S8": (TokenConsumptionDirection.CONTRACTING, CapexAccelerationDirection.STABLE),
    "S9": (TokenConsumptionDirection.CONTRACTING, CapexAccelerationDirection.DECELERATING),
}


class AICapexTokenScenarioEngine:
    def evaluate(
        self,
        features: AICapexTokenFeatureSet,
        *,
        config: Mapping[str, object] | None = None,
    ) -> AICapexTokenScenarioDistribution:
        strength = _membership_strength(config)
        if strength is None or features.fallback_state is not None:
            return _neutral_distribution(features, "SCENARIO_PARAMETERS_REVIEW_REQUIRED")
        token_membership = _membership(features.token_direction, list(TokenConsumptionDirection), strength)
        capex_membership = _membership(features.capex_direction, list(CapexAccelerationDirection), strength)
        raw = {
            scenario: token_membership[token_direction] * capex_membership[capex_direction]
            for scenario, (token_direction, capex_direction) in SCENARIO_GRID.items()
        }
        probabilities = _normalize(raw)
        dominant = max(probabilities, key=lambda key: (probabilities[key], key))
        return AICapexTokenScenarioDistribution(
            as_of_date=features.as_of_date,
            probabilities=probabilities,
            dominant_scenario=dominant,
            dominant_scenario_explanation_only=True,
            data_quality=features.data_quality,
            confidence=min(features.data_quality, strength),
            reason_codes=("AI_CAPEX_TOKEN_SCENARIO_DISTRIBUTION",),
        )


def evaluate_ai_capex_token_scenario(
    features: AICapexTokenFeatureSet,
    *,
    config: Mapping[str, object] | None = None,
) -> AICapexTokenScenarioDistribution:
    return AICapexTokenScenarioEngine().evaluate(features, config=config)


def _membership(direction, directions: list, strength: float) -> dict:
    remainder = max(0.0, 1.0 - strength)
    other = remainder / (len(directions) - 1)
    return {candidate: strength if candidate == direction else other for candidate in directions}


def _membership_strength(config: Mapping[str, object] | None) -> float | None:
    if not config:
        return None
    params = config.get("scenario_probability_parameters")
    if not isinstance(params, Mapping):
        return None
    value = params.get("membership_strength")
    if value is None:
        return None
    value = float(value)
    if not isfinite(value) or not 0.0 < value < 1.0:
        return None
    return value


def _normalize(raw: Mapping[str, float]) -> dict[str, float]:
    total = sum(value for value in raw.values() if isfinite(value) and value >= 0.0)
    if total <= 0:
        return {scenario: 1.0 / len(SCENARIO_GRID) for scenario in SCENARIO_GRID}
    return {scenario: max(value, 0.0) / total for scenario, value in raw.items()}


def _neutral_distribution(features: AICapexTokenFeatureSet, reason_code: str) -> AICapexTokenScenarioDistribution:
    probabilities = {scenario: 1.0 / len(SCENARIO_GRID) for scenario in SCENARIO_GRID}
    return AICapexTokenScenarioDistribution(
        as_of_date=features.as_of_date,
        probabilities=probabilities,
        dominant_scenario="S9",
        dominant_scenario_explanation_only=True,
        data_quality=features.data_quality,
        confidence=0.0,
        fallback_state=AICapexTokenFallbackState.REVIEW_REQUIRED,
        reason_codes=(reason_code,),
        warnings=("scenario_distribution_diagnostic_only",),
    )
