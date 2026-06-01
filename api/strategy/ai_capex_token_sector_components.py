from __future__ import annotations

from typing import Mapping

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenFallbackState,
    AICapexTokenFeatureSet,
    AICapexTokenScenarioDistribution,
    AICapexTokenSectorComponentScore,
)


class AICapexTokenSectorComponentBuilder:
    def score_bigtech_platform(
        self,
        distribution: AICapexTokenScenarioDistribution,
        features: AICapexTokenFeatureSet,
        sector_metrics: Mapping[str, float],
        *,
        parameter_version: str = "ai_capex_token_v0_diagnostic",
    ) -> AICapexTokenSectorComponentScore:
        score, confidence, reasons = _weighted_score(
            positives=[
                distribution.probabilities["S2"],
                distribution.probabilities["S3"],
                _metric(sector_metrics, "ai_monetization_score", reasons := []),
                _metric(sector_metrics, "fcf_margin_improvement_score", reasons),
                1.0 - _metric(sector_metrics, "capex_burden_score", reasons),
                1.0 - _metric(sector_metrics, "valuation_burden_score", reasons),
            ],
            base_confidence=distribution.confidence,
            reasons=reasons,
        )
        return _component("bigtech_platform", distribution, score, confidence, features, reasons, parameter_version)

    def score_power_equipment(
        self,
        distribution: AICapexTokenScenarioDistribution,
        features: AICapexTokenFeatureSet,
        sector_metrics: Mapping[str, float],
        *,
        parameter_version: str = "ai_capex_token_v0_diagnostic",
    ) -> AICapexTokenSectorComponentScore:
        reasons: list[str] = []
        adverse_probability = distribution.probabilities["S4"] + distribution.probabilities["S7"]
        penalty = _average(
            [
                _metric(sector_metrics, "backlog_slowdown_score", reasons),
                _metric(sector_metrics, "asp_slowdown_score", reasons),
                adverse_probability,
                _metric(sector_metrics, "valuation_burden_score", reasons),
            ]
        )
        positive = _average(
            [
                distribution.probabilities["S1"],
                _metric(sector_metrics, "backlog_growth_score", reasons),
                _metric(sector_metrics, "asp_growth_score", reasons),
            ]
        )
        score = _clamp(positive * 0.65 + (1.0 - penalty) * 0.35)
        confidence = _confidence(distribution.confidence, reasons)
        return _component("power_equipment", distribution, score, confidence, features, reasons, parameter_version)

    def score_semiconductor_hbm(
        self,
        distribution: AICapexTokenScenarioDistribution,
        features: AICapexTokenFeatureSet,
        sector_metrics: Mapping[str, float],
        *,
        parameter_version: str = "ai_capex_token_v0_diagnostic",
    ) -> AICapexTokenSectorComponentScore:
        reasons: list[str] = []
        stagnation_or_contraction = sum(distribution.probabilities[key] for key in ("S4", "S5", "S6", "S7", "S8", "S9"))
        penalty = _average(
            [
                _metric(sector_metrics, "hbm_supply_growth_score", reasons),
                _metric(sector_metrics, "hbm_inventory_risk_score", reasons),
                1.0 - _metric(sector_metrics, "hbm_asp_growth_score", reasons),
                stagnation_or_contraction,
                _metric(sector_metrics, "valuation_burden_score", reasons),
            ]
        )
        positive = _average([distribution.probabilities["S1"], _metric(sector_metrics, "hbm_asp_growth_score", reasons)])
        score = _clamp(positive * 0.6 + (1.0 - penalty) * 0.4)
        confidence = _confidence(distribution.confidence, reasons)
        return _component("semiconductor_hbm", distribution, score, confidence, features, reasons, parameter_version)

    def score_cash_short_duration(
        self,
        distribution: AICapexTokenScenarioDistribution,
        features: AICapexTokenFeatureSet,
        macro_stress_score: float,
        *,
        parameter_version: str = "ai_capex_token_v0_diagnostic",
    ) -> AICapexTokenSectorComponentScore:
        defensive_probability = distribution.probabilities["S4"] + distribution.probabilities["S7"] + distribution.probabilities["S8"]
        score = _clamp(_average([defensive_probability, 1.0 - features.data_quality, macro_stress_score]))
        return _component(
            "cash_short_duration",
            distribution,
            score,
            min(distribution.confidence, features.data_quality),
            features,
            ["cash_defensive_diagnostic"],
            parameter_version,
        )

    def score_inverse_hedge_diagnostic(
        self,
        distribution: AICapexTokenScenarioDistribution,
        features: AICapexTokenFeatureSet,
        *,
        parameter_version: str = "ai_capex_token_v0_diagnostic",
    ) -> AICapexTokenSectorComponentScore:
        score = _clamp(distribution.probabilities["S7"])
        return _component(
            "inverse_hedge_diagnostic",
            distribution,
            score,
            min(distribution.confidence, features.data_quality),
            features,
            ["inverse_hedge_diagnostic_only", "requires_existing_hedge_policy"],
            parameter_version,
        )


def _component(
    sector_id: str,
    distribution: AICapexTokenScenarioDistribution,
    score: float,
    confidence: float,
    features: AICapexTokenFeatureSet,
    reasons: list[str],
    parameter_version: str,
) -> AICapexTokenSectorComponentScore:
    fallback = AICapexTokenFallbackState.REVIEW_REQUIRED if reasons and any(reason.startswith("missing_") for reason in reasons) else None
    return AICapexTokenSectorComponentScore(
        sector_id=sector_id,
        as_of_date=distribution.as_of_date,
        component_score=score,
        confidence=confidence,
        data_quality=min(distribution.data_quality, features.data_quality),
        diagnostic_only=True,
        scenario_distribution=distribution,
        fallback_state=fallback,
        reason_codes=tuple(["ai_capex_token_sector_component", *reasons]),
        parameter_version=parameter_version,
        model_version="ai_capex_token_sector_component_v1",
    )


def _metric(metrics: Mapping[str, float], key: str, reasons: list[str]) -> float:
    if key not in metrics:
        reasons.append(f"missing_{key}_review_required")
        return 0.5
    return _clamp(float(metrics[key]))


def _weighted_score(positives: list[float], base_confidence: float, reasons: list[str]) -> tuple[float, float, list[str]]:
    return _clamp(_average(positives)), _confidence(base_confidence, reasons), reasons


def _average(values: list[float]) -> float:
    return sum(_clamp(value) for value in values) / len(values) if values else 0.5


def _confidence(base: float, reasons: list[str]) -> float:
    return _clamp(base * (0.6 if any(reason.startswith("missing_") for reason in reasons) else 1.0))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
