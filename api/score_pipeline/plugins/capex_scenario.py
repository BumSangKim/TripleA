from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from api.score_pipeline.contracts import DecisionWarning, ReasonCode, ScenarioDistribution
from api.score_pipeline.plugins.capex_common import clamp, score_from_z


SCENARIOS = (
    "ai_buildout_continues",
    "ai_monetization_rotation",
    "overbuild_demand_gap",
    "rate_shock_non_recession",
    "credit_stress",
)


@dataclass(frozen=True)
class CapexScenarioEngine:
    parameter_version: str = "capex_scenario_v0"
    model_version: str = "capex_scenario_engine_v0"
    low_quality_threshold: float = 0.70

    def evaluate(
        self,
        *,
        as_of_date: date,
        ai_capex_cycle_score: float | None,
        tcr: float | None,
        tce: float | None,
        capex_acceleration: float | None,
        macro_multiplier: float | None,
        data_quality: float,
    ) -> ScenarioDistribution:
        warnings: list[DecisionWarning] = []
        reason_codes = [ReasonCode("CAPEX_SCENARIO_DISTRIBUTION_COMPUTED", "scenario")]
        quality = clamp(data_quality)
        inputs = [ai_capex_cycle_score, tcr, tce, capex_acceleration, macro_multiplier]
        if any(value is None or not _is_finite(value) for value in inputs):
            reason_codes.append(ReasonCode("CAPEX_SCENARIO_INPUT_MISSING", "scenario"))
            warnings.append(DecisionWarning("CAPEX_SCENARIO_REVIEW_REQUIRED", "WARNING", "scenario", "missing or invalid input"))
            distribution = _normalize({scenario: 1.0 for scenario in SCENARIOS})
            return ScenarioDistribution(
                as_of_date=as_of_date,
                distribution=distribution,
                dominant_scenario=_dominant(distribution),
                confidence=0.0,
                data_quality=quality,
                reason_codes=reason_codes,
                warnings=warnings,
                parameter_version=self.parameter_version,
                model_version=self.model_version,
            )

        ai_score = clamp(ai_capex_cycle_score)
        token_change_score = score_from_z(tcr)
        efficiency_score = score_from_z(tce)
        acceleration_score = score_from_z(capex_acceleration)
        macro_score = clamp(macro_multiplier)
        if quality < self.low_quality_threshold:
            reason_codes.append(ReasonCode("CAPEX_SCENARIO_LOW_DATA_QUALITY", "scenario"))
            warnings.append(
                DecisionWarning(
                    "CAPEX_SCENARIO_LOW_DATA_QUALITY",
                    "WARNING",
                    "scenario",
                    f"quality={quality:.4f}",
                )
            )
        raw = {
            "ai_buildout_continues": 0.20 + ai_score + token_change_score + acceleration_score + macro_score,
            "ai_monetization_rotation": 0.20 + ai_score + efficiency_score + (1.0 - acceleration_score),
            "overbuild_demand_gap": 0.20 + acceleration_score + (1.0 - token_change_score) + (1.0 - efficiency_score),
            "rate_shock_non_recession": 0.20 + (1.0 - macro_score) + 0.5 * ai_score,
            "credit_stress": 0.20 + (1.0 - macro_score) + (1.0 - quality),
        }
        distribution = _normalize(raw)
        return ScenarioDistribution(
            as_of_date=as_of_date,
            distribution=distribution,
            dominant_scenario=_dominant(distribution),
            confidence=quality,
            data_quality=quality,
            reason_codes=reason_codes,
            warnings=warnings,
            parameter_version=self.parameter_version,
            model_version=self.model_version,
        )


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    cleaned = {key: max(0.0, float(value)) if _is_finite(value) else 0.0 for key, value in raw.items()}
    total = sum(cleaned.values())
    if total <= 0:
        equal = 1.0 / len(cleaned)
        return {key: equal for key in cleaned}
    return {key: value / total for key, value in cleaned.items()}


def _dominant(distribution: dict[str, float]) -> str:
    return max(distribution.items(), key=lambda item: item[1])[0]


def _is_finite(value: float | int | None) -> bool:
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
