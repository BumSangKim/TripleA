from __future__ import annotations

from dataclasses import dataclass

from api.domain.strategy_inputs import MacroSnapshotInput
from api.score_pipeline.contracts import DecisionWarning, MacroRegimeDistribution, ReasonCode
from api.strategy.macro_engine import MacroRegimeDecision, evaluate_macro_snapshot


MACRO_REGIME_KEYS = ("risk_on_growth", "neutral", "inflation_pressure", "recession_risk", "volatility_stress")
LEGACY_REGIME_MAPPING = {
    "risk_on": "risk_on_growth",
    "neutral": "neutral",
    "cautious": "inflation_pressure",
    "risk_off": "volatility_stress",
}


@dataclass(frozen=True)
class MacroDistributionAdapter:
    parameter_version: str = "legacy_macro_distribution_adapter_v1"
    model_version: str = "score_flow_macro_distribution_adapter_v1"

    def adapt(
        self,
        source: MacroRegimeDecision | MacroSnapshotInput,
        *,
        previous_score: int | None = None,
    ) -> MacroRegimeDistribution:
        decision = _decision_from_source(source)
        if not decision.indicators:
            return self._missing_input_distribution(decision)
        dominant = LEGACY_REGIME_MAPPING.get(decision.regime, "neutral")
        distribution = _legacy_distribution(dominant)
        reason_codes = [
            ReasonCode("MACRO_DISTRIBUTION_LEGACY_ADAPTER", "macro", detail)
            for detail in decision.reasons
        ]
        if previous_score is not None:
            score_change = abs(decision.score - previous_score) / 100.0
            reason_codes.append(
                ReasonCode(
                    "MACRO_SCORE_CHANGE_EVIDENCE",
                    "macro",
                    f"previous_score={previous_score};current_score={decision.score};change={score_change:.4f}",
                )
            )
        return MacroRegimeDistribution(
            as_of_date=decision.as_of_date,
            distribution=distribution,
            dominant_regime=dominant,
            dominant_regime_explanation_only=True,
            confidence=0.7,
            data_quality=0.7,
            reason_codes=reason_codes or [ReasonCode("MACRO_DISTRIBUTION_LEGACY_ADAPTER", "macro")],
            warnings=[],
            parameter_version=self.parameter_version,
            model_version=self.model_version,
        )

    def _missing_input_distribution(self, decision: MacroRegimeDecision) -> MacroRegimeDistribution:
        return MacroRegimeDistribution(
            as_of_date=decision.as_of_date,
            distribution={key: 1.0 if key == "neutral" else 0.0 for key in MACRO_REGIME_KEYS},
            dominant_regime="neutral",
            dominant_regime_explanation_only=True,
            confidence=0.0,
            data_quality=0.0,
            reason_codes=[ReasonCode("MACRO_INPUT_REVIEW_REQUIRED", "macro")],
            warnings=[
                DecisionWarning(
                    "MISSING_MACRO_INPUT_REVIEW_REQUIRED",
                    "WARNING",
                    "macro",
                    "Missing macro indicators; neutral review-required distribution used.",
                )
            ],
            parameter_version=self.parameter_version,
            model_version=self.model_version,
        )


def adapt_macro_distribution(
    source: MacroRegimeDecision | MacroSnapshotInput,
    *,
    previous_score: int | None = None,
) -> MacroRegimeDistribution:
    return MacroDistributionAdapter().adapt(source, previous_score=previous_score)


def _decision_from_source(source: MacroRegimeDecision | MacroSnapshotInput) -> MacroRegimeDecision:
    if isinstance(source, MacroRegimeDecision):
        return source
    if isinstance(source, MacroSnapshotInput):
        return evaluate_macro_snapshot(source)
    raise TypeError("source must be MacroRegimeDecision or MacroSnapshotInput")


def _legacy_distribution(dominant: str) -> dict[str, float]:
    distribution = {key: 0.1 for key in MACRO_REGIME_KEYS}
    distribution[dominant] = 0.6
    total = sum(distribution.values())
    return {key: value / total for key, value in distribution.items()}
