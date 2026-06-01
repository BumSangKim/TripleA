from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenFallbackState,
    AICapexTokenSectorComponentScore,
)


STRESS_KEYS = (
    "real_rate_shock_score",
    "credit_spread_stress_score",
    "liquidity_stress_score",
    "fx_stress_score",
    "volatility_stress_score",
)


@dataclass(frozen=True)
class AICapexTokenMacroOverlayResult:
    components: tuple[AICapexTokenSectorComponentScore, ...]
    macro_stress_score: float
    adjustment_intensity: float
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, object]


class AICapexTokenMacroOverlay:
    def apply(
        self,
        components: Sequence[AICapexTokenSectorComponentScore],
        macro_overlay_metrics: Mapping[str, float] | None,
    ) -> AICapexTokenMacroOverlayResult:
        metrics = macro_overlay_metrics or {}
        missing = [key for key in STRESS_KEYS if key not in metrics]
        if missing:
            adjusted = tuple(
                replace(
                    component,
                    confidence=_clamp(component.confidence * 0.5),
                    fallback_state=AICapexTokenFallbackState.REVIEW_REQUIRED,
                    reason_codes=(*component.reason_codes, "missing_macro_overlay_review_required"),
                )
                for component in components
            )
            return AICapexTokenMacroOverlayResult(
                components=adjusted,
                macro_stress_score=0.0,
                adjustment_intensity=0.0,
                reason_codes=("MISSING_MACRO_OVERLAY_REVIEW_REQUIRED",),
                metadata={"missing_macro_keys": tuple(missing), "risk_increase_allowed": False},
            )

        stress = _clamp(sum(_clamp(float(metrics[key])) for key in STRESS_KEYS) / len(STRESS_KEYS))
        intensity = _clamp(stress * 0.5)
        adjusted = tuple(
            replace(
                component,
                confidence=_clamp(component.confidence * (1.0 - intensity)),
                reason_codes=(*component.reason_codes, "macro_overlay_confidence_adjustment"),
            )
            for component in components
        )
        return AICapexTokenMacroOverlayResult(
            components=adjusted,
            macro_stress_score=stress,
            adjustment_intensity=intensity,
            reason_codes=("AI_CAPEX_TOKEN_MACRO_OVERLAY",),
            metadata={"risk_pressure": stress, "scenario_probabilities_unchanged": True},
        )


def apply_ai_capex_token_macro_overlay(
    components: Sequence[AICapexTokenSectorComponentScore],
    macro_overlay_metrics: Mapping[str, float] | None,
) -> AICapexTokenMacroOverlayResult:
    return AICapexTokenMacroOverlay().apply(components, macro_overlay_metrics)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
