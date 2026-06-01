from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenSectorComponentScore
from api.strategy.ai_capex_token_component import AICapexTokenDiagnosticComponent
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter, AICapexTokenInputAdapterError
from api.strategy.ai_capex_token_macro_overlay import AICapexTokenMacroOverlay
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine
from api.strategy.ai_capex_token_sector_components import AICapexTokenSectorComponentBuilder


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
TEST_CONFIG = {
    "enabled": False,
    "diagnostic_only": True,
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}
EXPECTED_SCENARIOS = {
    "s1_expanding_accelerating.json": "S1",
    "s3_expanding_decelerating_platform.json": "S3",
    "s7_contracting_accelerating_overinvestment.json": "S7",
}
STANDARD_SCORE_FIELDS = {
    "score",
    "previous_score",
    "score_change",
    "confidence",
    "data_quality",
    "stability",
    "adjustment_intensity",
    "reason_codes",
    "as_of_date",
    "parameter_version",
    "model_version",
    "components",
}
FORBIDDEN_OUTPUT_KEYS = {"order", "target_weight", "execution", "execute", "live", "broker"}


class PluginStylePayload:
    def __init__(self, data: dict) -> None:
        self.data = data


@pytest.mark.parametrize("fixture_name,expected_scenario", EXPECTED_SCENARIOS.items())
def test_fixture_to_diagnostic_score_flow_has_explainable_standard_outputs(fixture_name: str, expected_scenario: str):
    payload = _load(fixture_name)

    flow = _run_public_flow(PluginStylePayload(payload))
    diagnostic = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)

    assert flow["distribution"].dominant_scenario == expected_scenario
    assert diagnostic.applied_to_sector_engine is False
    assert diagnostic.diagnostic_only is True
    assert "AI_CAPEX_TOKEN_DIAGNOSTIC_ONLY" in diagnostic.reason_codes
    assert len(flow["components"]) == 5
    assert len(diagnostic.components) == 5
    assert _contains_forbidden_key(asdict(diagnostic)) is False

    for component in (*flow["components"], *diagnostic.components):
        assert isinstance(component, AICapexTokenSectorComponentScore)
        assert component.diagnostic_only is True
        assert component.as_of_date.isoformat() == payload["decision_date"]
        assert component.parameter_version
        assert component.model_version
        assert component.reason_codes
        assert set(component.to_score_signal_dict()) == STANDARD_SCORE_FIELDS
        assert component.to_score_signal_dict()["reason_codes"]
        assert _contains_forbidden_key(component.to_score_signal_dict()) is False


def test_invalid_ambiguous_period_fixture_returns_review_required_or_validation_error():
    payload = _load("invalid_ambiguous_period_roles.json")

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "INVALID_EXPLICIT_PERIOD_ROLE_REVIEW_REQUIRED" in result.reason_codes
    with pytest.raises(AICapexTokenInputAdapterError) as exc_info:
        AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)
    assert exc_info.value.fallback_state == "REVIEW_REQUIRED"


def test_future_available_metric_is_excluded_before_scoring():
    payload = _load("future_data_leakage_probe.json")

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert "FUTURE_INPUT_EXCLUDED" in result.reason_codes
    assert "MISSING_TOKEN_CURRENT_REVIEW_REQUIRED" in result.reason_codes
    assert "MISSING_CAPEX_PERIOD_REVIEW_REQUIRED" in result.reason_codes
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert set(result.excluded_metric_keys) >= {"tokens.aggregate.synthetic", "capex.bigtech_ai_total"}


def test_disabled_config_keeps_component_diagnostic_only_and_noop():
    diagnostic = AICapexTokenDiagnosticComponent().build(_load("s1_expanding_accelerating.json"), config=TEST_CONFIG)

    assert diagnostic.enabled is False
    assert diagnostic.diagnostic_only is True
    assert diagnostic.applied_to_sector_engine is False
    assert diagnostic.metadata["safe_sector_extension_point"] is False
    assert diagnostic.metadata["sector_tilt_engine_modified"] is False


def test_poor_data_quality_reduces_confidence_without_risk_increasing_action():
    baseline = AICapexTokenDiagnosticComponent().build(_load("s1_expanding_accelerating.json"), config=TEST_CONFIG)
    low_quality_payload = copy.deepcopy(_load("s1_expanding_accelerating.json"))
    low_quality_payload["token_sources_current"][0]["quality_score"] = 0.4
    low_quality_payload["token_sources_current"][0]["missing_ratio"] = 0.25
    low_quality_payload["token_sources_current"][0]["is_stale"] = True

    low_quality = AICapexTokenDiagnosticComponent().build(low_quality_payload, config=TEST_CONFIG)

    assert max(component.confidence for component in low_quality.components) < max(
        component.confidence for component in baseline.components
    )
    assert all(component.data_quality <= 0.4 for component in low_quality.components)
    assert _contains_forbidden_key(asdict(low_quality)) is False


def _run_public_flow(payload: dict | PluginStylePayload) -> dict:
    snapshot = AICapexTokenInputAdapter().adapt(payload)
    features = AICapexTokenFeatureBuilder().build(snapshot, config=TEST_CONFIG)
    distribution = AICapexTokenScenarioEngine().evaluate(features, config=TEST_CONFIG)
    builder = AICapexTokenSectorComponentBuilder()
    sector_metrics = snapshot.sector_metrics
    components = (
        builder.score_bigtech_platform(distribution, features, sector_metrics.get("bigtech_platform", {})),
        builder.score_power_equipment(distribution, features, sector_metrics.get("power_equipment", {})),
        builder.score_semiconductor_hbm(distribution, features, sector_metrics.get("semiconductor_hbm", {})),
        builder.score_cash_short_duration(distribution, features, macro_stress_score=0.0),
        builder.score_inverse_hedge_diagnostic(distribution, features),
    )
    overlay = AICapexTokenMacroOverlay().apply(components, snapshot.macro_overlay_metrics)
    return {"snapshot": snapshot, "features": features, "distribution": distribution, "components": overlay.components}


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _contains_forbidden_key(value) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_OUTPUT_KEYS or normalized.endswith("_order"):
                return True
            if _contains_forbidden_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False
