from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenFallbackState
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter
from api.strategy.ai_capex_token_macro_overlay import AICapexTokenMacroOverlay
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine
from api.strategy.ai_capex_token_sector_components import AICapexTokenSectorComponentBuilder


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
TEST_CONFIG = {
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}


def test_macro_stress_reduces_positive_component_confidence():
    context = _context("s1_expanding_accelerating.json")
    component = AICapexTokenSectorComponentBuilder().score_power_equipment(
        context["distribution"], context["features"], context["sector_metrics"]["power_equipment"]
    )
    stressed = {key: 0.9 for key in ("real_rate_shock_score", "credit_spread_stress_score", "liquidity_stress_score", "fx_stress_score", "volatility_stress_score")}

    result = AICapexTokenMacroOverlay().apply([component], stressed)

    assert result.components[0].confidence < component.confidence
    assert result.adjustment_intensity > 0
    assert "macro_overlay_confidence_adjustment" in result.components[0].reason_codes


def test_scenario_probabilities_are_unchanged():
    context = _context("s1_expanding_accelerating.json")
    component = AICapexTokenSectorComponentBuilder().score_power_equipment(
        context["distribution"], context["features"], context["sector_metrics"]["power_equipment"]
    )

    result = AICapexTokenMacroOverlay().apply([component], context["macro_overlay_metrics"])

    assert result.components[0].scenario_distribution.probabilities == component.scenario_distribution.probabilities
    assert result.metadata["scenario_probabilities_unchanged"] is True


def test_missing_macro_input_does_not_increase_risk():
    context = _context("s1_expanding_accelerating.json")
    component = AICapexTokenSectorComponentBuilder().score_power_equipment(
        context["distribution"], context["features"], context["sector_metrics"]["power_equipment"]
    )

    result = AICapexTokenMacroOverlay().apply([component], {})

    assert result.components[0].confidence < component.confidence
    assert result.components[0].fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED
    assert result.metadata["risk_increase_allowed"] is False


def test_overlay_creates_no_order_or_target_fields():
    context = _context("s7_contracting_accelerating_overinvestment.json")
    component = AICapexTokenSectorComponentBuilder().score_inverse_hedge_diagnostic(
        context["distribution"], context["features"]
    )

    result = AICapexTokenMacroOverlay().apply([component], context["macro_overlay_metrics"])
    payload = set(asdict(result))

    assert {"order", "target_weight", "allocation", "execution"}.isdisjoint(payload)


def _context(name: str) -> dict:
    data = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    snapshot = AICapexTokenInputAdapter().adapt(data)
    features = AICapexTokenFeatureBuilder().build(snapshot, config=TEST_CONFIG)
    distribution = AICapexTokenScenarioEngine().evaluate(features, config=TEST_CONFIG)
    return {
        "features": features,
        "distribution": distribution,
        "sector_metrics": data["sector_metrics"],
        "macro_overlay_metrics": data["macro_overlay_metrics"],
    }
