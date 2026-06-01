from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine
from api.strategy.ai_capex_token_sector_components import AICapexTokenSectorComponentBuilder


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
TEST_CONFIG = {
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}


def test_s1_improves_power_and_hbm_without_order_fields():
    context = _context("s1_expanding_accelerating.json")
    builder = AICapexTokenSectorComponentBuilder()

    power = builder.score_power_equipment(context["distribution"], context["features"], context["sector_metrics"]["power_equipment"])
    hbm = builder.score_semiconductor_hbm(context["distribution"], context["features"], context["sector_metrics"]["semiconductor_hbm"])

    assert power.component_score > 0.5
    assert hbm.component_score > 0.45
    assert {"order", "target_weight", "allocation", "execution"}.isdisjoint(set(asdict(power)))


def test_s3_bigtech_improves_and_power_valuation_penalty_is_continuous():
    context = _context("s3_expanding_decelerating_platform.json")
    builder = AICapexTokenSectorComponentBuilder()
    base_metrics = dict(context["sector_metrics"]["power_equipment"])
    high_valuation = {**base_metrics, "valuation_burden_score": 0.9}

    bigtech = builder.score_bigtech_platform(context["distribution"], context["features"], context["sector_metrics"]["bigtech_platform"])
    base_power = builder.score_power_equipment(context["distribution"], context["features"], base_metrics)
    penalized_power = builder.score_power_equipment(context["distribution"], context["features"], high_valuation)

    assert bigtech.component_score > 0.5
    assert penalized_power.component_score < base_power.component_score


def test_s7_cash_defensive_and_inverse_diagnostic_rise():
    context = _context("s7_contracting_accelerating_overinvestment.json")
    builder = AICapexTokenSectorComponentBuilder()

    cash = builder.score_cash_short_duration(context["distribution"], context["features"], macro_stress_score=0.7)
    inverse = builder.score_inverse_hedge_diagnostic(context["distribution"], context["features"])

    assert cash.component_score > 0.4
    assert inverse.component_score == context["distribution"].probabilities["S7"]
    assert "inverse_hedge_diagnostic_only" in inverse.reason_codes


def test_missing_sector_metric_lowers_confidence_and_review_reason():
    context = _context("s1_expanding_accelerating.json")
    builder = AICapexTokenSectorComponentBuilder()

    score = builder.score_power_equipment(context["distribution"], context["features"], {})

    assert score.confidence < context["distribution"].confidence
    assert any(reason.startswith("missing_") for reason in score.reason_codes)


def test_inverse_component_has_no_order_target_or_allocation_field():
    context = _context("s7_contracting_accelerating_overinvestment.json")

    inverse = AICapexTokenSectorComponentBuilder().score_inverse_hedge_diagnostic(context["distribution"], context["features"])

    assert {"order", "target_weight", "allocation", "execution"}.isdisjoint(set(asdict(inverse)))
    assert inverse.diagnostic_only is True


def _context(name: str) -> dict:
    data = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    snapshot = AICapexTokenInputAdapter().adapt(data)
    features = AICapexTokenFeatureBuilder().build(snapshot, config=TEST_CONFIG)
    distribution = AICapexTokenScenarioEngine().evaluate(features, config=TEST_CONFIG)
    return {
        "snapshot": snapshot,
        "features": features,
        "distribution": distribution,
        "sector_metrics": data["sector_metrics"],
    }
