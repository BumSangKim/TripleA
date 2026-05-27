from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.strategy.macro_engine import MacroRegimeDecision


@dataclass(frozen=True)
class MacroRegimeDistribution:
    as_of_date: date
    distribution: dict[str, float]
    dominant_regime: str
    confidence: float
    data_quality: float
    macro_change_score: float
    macro_change_speed: float
    reason_codes: list[str]


def distribution_from_macro_decision(decision: MacroRegimeDecision, previous_score: int | None = None) -> MacroRegimeDistribution:
    mapping = {
        "risk_on": "risk_on_growth",
        "neutral": "neutral",
        "cautious": "inflation_pressure",
        "risk_off": "volatility_stress",
    }
    dominant = mapping.get(decision.regime, "neutral")
    base = {key: 0.1 for key in ["risk_on_growth", "neutral", "inflation_pressure", "recession_risk", "volatility_stress"]}
    base[dominant] = 0.6
    total = sum(base.values())
    distribution = {key: value / total for key, value in base.items()}
    score_change = 0.0 if previous_score is None else abs(decision.score - previous_score) / 100.0
    return MacroRegimeDistribution(decision.as_of_date, distribution, dominant, 0.7, 0.7, score_change, score_change, decision.reasons)
