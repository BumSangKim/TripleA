from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenFallbackState
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter
from api.strategy.ai_capex_token_macro_overlay import AICapexTokenMacroOverlay
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine
from api.strategy.ai_capex_token_sector_components import AICapexTokenSectorComponentBuilder


FIXTURE_PATH = Path("tests/fixtures/ai_capex_token_tuning/synthetic_two_memory_cycles.json")
APPROVED_NORMALIZATION = {"normalization_parameters": {"metadata": {"approved": True}}}


def test_membership_strength_changes_dominant_scenario_concentration():
    features, *_ = _context("synthetic-cycle-a-s1", membership_strength=0.55)
    low = AICapexTokenScenarioEngine().evaluate(features, config=_config(0.55))
    high = AICapexTokenScenarioEngine().evaluate(features, config=_config(0.85))

    assert low.dominant_scenario == "S1"
    assert high.dominant_scenario == "S1"
    assert high.probabilities["S1"] > low.probabilities["S1"]
    assert high.probabilities != low.probabilities


def test_macro_stress_changes_component_confidence_without_changing_scenario():
    features, distribution, sector_metrics, _ = _context("synthetic-cycle-a-s1")
    component = AICapexTokenSectorComponentBuilder().score_power_equipment(
        distribution,
        features,
        sector_metrics=sector_metrics["power_equipment"],
    )
    low_stress = {key: 0.0 for key in _macro_keys()}
    high_stress = {key: 0.9 for key in _macro_keys()}

    low = AICapexTokenMacroOverlay().apply([component], low_stress)
    high = AICapexTokenMacroOverlay().apply([component], high_stress)

    assert high.components[0].confidence < low.components[0].confidence
    assert high.macro_stress_score > low.macro_stress_score
    assert high.components[0].scenario_distribution.probabilities == low.components[0].scenario_distribution.probabilities
    assert high.components[0].diagnostic_only is True


def test_high_valuation_burden_lowers_power_and_hbm_scores():
    features, distribution, sector_metrics, _ = _context("synthetic-cycle-a-s1")
    builder = AICapexTokenSectorComponentBuilder()
    low_power = {**sector_metrics["power_equipment"], "valuation_burden_score": 0.1}
    high_power = {**sector_metrics["power_equipment"], "valuation_burden_score": 0.9}
    low_hbm = {**sector_metrics["semiconductor_hbm"], "valuation_burden_score": 0.1}
    high_hbm = {**sector_metrics["semiconductor_hbm"], "valuation_burden_score": 0.9}

    power_low = builder.score_power_equipment(distribution, features, low_power)
    power_high = builder.score_power_equipment(distribution, features, high_power)
    hbm_low = builder.score_semiconductor_hbm(distribution, features, low_hbm)
    hbm_high = builder.score_semiconductor_hbm(distribution, features, high_hbm)

    assert power_high.component_score < power_low.component_score
    assert hbm_high.component_score < hbm_low.component_score
    assert power_high.diagnostic_only is True
    assert hbm_high.diagnostic_only is True


def test_missing_sector_metric_lowers_confidence_and_sets_review_required():
    features, distribution, _, _ = _context("synthetic-cycle-a-s1")

    score = AICapexTokenSectorComponentBuilder().score_power_equipment(distribution, features, {})

    assert score.confidence < distribution.confidence
    assert score.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED
    assert any(reason.startswith("missing_") for reason in score.reason_codes)
    assert score.diagnostic_only is True


def test_future_data_row_is_excluded_before_available_output():
    payload = _snapshot_payload("synthetic-cycle-b-s7")
    without_future = deepcopy(payload)
    without_future["capex_series"] = [
        row for row in without_future["capex_series"] if row["metric_key"] != "future.leakage_probe"
    ]
    adapter = AICapexTokenInputAdapter()

    result_with_future = adapter.adapt_with_metadata(payload)
    result_without_future = adapter.adapt_with_metadata(without_future)

    assert "future.leakage_probe" in result_with_future.excluded_metric_keys
    assert result_with_future.snapshot is not None
    assert result_without_future.snapshot is not None
    assert all(metric.metric_key != "future.leakage_probe" for metric in result_with_future.snapshot.capex_series)

    features_with_future = AICapexTokenFeatureBuilder().build(result_with_future.snapshot, config=APPROVED_NORMALIZATION)
    features_without_future = AICapexTokenFeatureBuilder().build(result_without_future.snapshot, config=APPROVED_NORMALIZATION)
    distribution_with_future = AICapexTokenScenarioEngine().evaluate(features_with_future, config=_config(0.8))
    distribution_without_future = AICapexTokenScenarioEngine().evaluate(features_without_future, config=_config(0.8))

    assert features_with_future == features_without_future
    assert distribution_with_future.probabilities == pytest.approx(distribution_without_future.probabilities)


def _context(snapshot_id: str, *, membership_strength: float = 0.8):
    payload = _snapshot_payload(snapshot_id)
    snapshot = AICapexTokenInputAdapter().adapt(payload)
    features = AICapexTokenFeatureBuilder().build(snapshot, config=APPROVED_NORMALIZATION)
    distribution = AICapexTokenScenarioEngine().evaluate(features, config=_config(membership_strength))
    return features, distribution, payload["sector_metrics"], payload["macro_overlay_metrics"]


def _snapshot_payload(snapshot_id: str) -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for snapshot in fixture["snapshots"]:
        if snapshot["snapshot_id"] == snapshot_id:
            return deepcopy(snapshot)
    raise AssertionError(f"missing snapshot fixture: {snapshot_id}")


def _config(membership_strength: float) -> dict:
    return {
        **APPROVED_NORMALIZATION,
        "scenario_probability_parameters": {"membership_strength": membership_strength},
    }


def _macro_keys() -> tuple[str, ...]:
    return (
        "real_rate_shock_score",
        "credit_spread_stress_score",
        "liquidity_stress_score",
        "fx_stress_score",
        "volatility_stress_score",
    )
