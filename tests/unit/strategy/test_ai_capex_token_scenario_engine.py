from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenFallbackState
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
TEST_CONFIG = {
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}


@pytest.mark.parametrize(
    "fixture_name,expected",
    [
        ("s1_expanding_accelerating.json", "S1"),
        ("s3_expanding_decelerating_platform.json", "S3"),
        ("s7_contracting_accelerating_overinvestment.json", "S7"),
    ],
)
def test_fixture_features_have_expected_dominant_probability(fixture_name, expected):
    distribution = AICapexTokenScenarioEngine().evaluate(_features(fixture_name), config=TEST_CONFIG)

    assert distribution.dominant_scenario == expected
    assert distribution.probabilities[expected] == max(distribution.probabilities.values())


def test_distribution_contains_all_scenarios_and_sums_to_one():
    distribution = AICapexTokenScenarioEngine().evaluate(_features("s1_expanding_accelerating.json"), config=TEST_CONFIG)

    assert set(distribution.probabilities) == {f"S{i}" for i in range(1, 10)}
    assert sum(distribution.probabilities.values()) == pytest.approx(1.0)
    assert distribution.dominant_scenario_explanation_only is True


def test_missing_parameters_returns_review_required_neutral_distribution():
    distribution = AICapexTokenScenarioEngine().evaluate(_features("s1_expanding_accelerating.json"), config={})

    assert distribution.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED
    assert len(set(distribution.probabilities.values())) == 1
    assert "SCENARIO_PARAMETERS_REVIEW_REQUIRED" in distribution.reason_codes


def test_nan_or_invalid_membership_falls_back():
    distribution = AICapexTokenScenarioEngine().evaluate(
        _features("s1_expanding_accelerating.json"),
        config={"scenario_probability_parameters": {"membership_strength": float("nan")}},
    )

    assert distribution.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED


def test_output_contains_no_allocation_or_order_fields():
    distribution = AICapexTokenScenarioEngine().evaluate(_features("s7_contracting_accelerating_overinvestment.json"), config=TEST_CONFIG)
    payload = set(asdict(distribution))

    assert {"allocation", "target_weight", "order", "orders", "execution"}.isdisjoint(payload)


def _features(name: str):
    data = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    snapshot = AICapexTokenInputAdapter().adapt(data)
    return AICapexTokenFeatureBuilder().build(snapshot, config=TEST_CONFIG)
