from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenFallbackState, AICapexTokenSectorComponentScore
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter
from api.strategy.ai_capex_token_macro_overlay import AICapexTokenMacroOverlay
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine
from api.strategy.ai_capex_token_sector_components import AICapexTokenSectorComponentBuilder


@dataclass(frozen=True)
class AICapexTokenDiagnosticOutput:
    enabled: bool
    diagnostic_only: bool
    applied_to_sector_engine: bool
    components: tuple[AICapexTokenSectorComponentScore, ...]
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, object]


class AICapexTokenDiagnosticComponent:
    def build(
        self,
        payload: Mapping[str, object] | object,
        *,
        config: Mapping[str, object] | None = None,
    ) -> AICapexTokenDiagnosticOutput:
        config = config or {}
        enabled = bool(config.get("enabled", False))
        diagnostic_only = bool(config.get("diagnostic_only", True))
        snapshot = AICapexTokenInputAdapter().adapt(payload)
        features = AICapexTokenFeatureBuilder().build(snapshot, config=config)
        distribution = AICapexTokenScenarioEngine().evaluate(features, config=config)
        builder = AICapexTokenSectorComponentBuilder()
        sector_metrics = snapshot.sector_metrics
        components = [
            builder.score_bigtech_platform(distribution, features, sector_metrics.get("bigtech_platform", {})),
            builder.score_power_equipment(distribution, features, sector_metrics.get("power_equipment", {})),
            builder.score_semiconductor_hbm(distribution, features, sector_metrics.get("semiconductor_hbm", {})),
            builder.score_cash_short_duration(
                distribution,
                features,
                macro_stress_score=_macro_stress(snapshot.macro_overlay_metrics),
            ),
            builder.score_inverse_hedge_diagnostic(distribution, features),
        ]
        if features.fallback_state is not None:
            components = [
                replace(
                    component,
                    fallback_state=AICapexTokenFallbackState.REVIEW_REQUIRED,
                    reason_codes=(*component.reason_codes, "feature_fallback_review_required"),
                )
                for component in components
            ]
        overlay = AICapexTokenMacroOverlay().apply(components, snapshot.macro_overlay_metrics)
        return AICapexTokenDiagnosticOutput(
            enabled=enabled,
            diagnostic_only=diagnostic_only,
            applied_to_sector_engine=False,
            components=overlay.components,
            reason_codes=("AI_CAPEX_TOKEN_DIAGNOSTIC_ONLY", *overlay.reason_codes),
            metadata={
                "safe_sector_extension_point": False,
                "sector_tilt_engine_modified": False,
                "macro_overlay": overlay.metadata,
            },
        )


def build_ai_capex_token_diagnostic_component(
    payload: Mapping[str, object] | object,
    *,
    config: Mapping[str, object] | None = None,
) -> AICapexTokenDiagnosticOutput:
    return AICapexTokenDiagnosticComponent().build(payload, config=config)


def _macro_stress(metrics: Mapping[str, float]) -> float:
    if not metrics:
        return 0.0
    return max(0.0, min(1.0, sum(float(value) for value in metrics.values()) / len(metrics)))
