from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from api.strategy.ai_capex_token_component import AICapexTokenDiagnosticComponent
from api.strategy.sector_tilt_engine import SectorTiltEngine


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
TEST_CONFIG = {
    "enabled": False,
    "diagnostic_only": True,
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}


def test_config_disabled_keeps_sector_tilt_engine_output_unchanged():
    engine = SectorTiltEngine()
    asset_weights = {"A": 0.5, "B": 0.5}
    before = engine.apply(asset_weights, [], {}, {"A": "GROWTH", "B": "GROWTH"})

    diagnostic = AICapexTokenDiagnosticComponent().build(_load("s1_expanding_accelerating.json"), config=TEST_CONFIG)
    after = engine.apply(asset_weights, [], {}, {"A": "GROWTH", "B": "GROWTH"})

    assert before == after
    assert diagnostic.applied_to_sector_engine is False


def test_diagnostic_only_mode_creates_separate_output():
    diagnostic = AICapexTokenDiagnosticComponent().build(_load("s3_expanding_decelerating_platform.json"), config=TEST_CONFIG)

    assert diagnostic.diagnostic_only is True
    assert len(diagnostic.components) == 5
    assert "AI_CAPEX_TOKEN_DIAGNOSTIC_ONLY" in diagnostic.reason_codes


def test_missing_parameter_does_not_apply_total_score_to_sector_engine():
    config = {"enabled": True, "diagnostic_only": True}

    diagnostic = AICapexTokenDiagnosticComponent().build(_load("s1_expanding_accelerating.json"), config=config)

    assert diagnostic.applied_to_sector_engine is False
    assert diagnostic.metadata["safe_sector_extension_point"] is False
    assert any(component.fallback_state is not None for component in diagnostic.components)


def test_output_has_no_order_target_rebalancing_or_execution_fields():
    diagnostic = AICapexTokenDiagnosticComponent().build(_load("s7_contracting_accelerating_overinvestment.json"), config=TEST_CONFIG)
    payload = asdict(diagnostic)

    assert _contains_forbidden_key(payload) is False


def test_strategy_import_boundary_avoids_features_brokers_and_providers():
    import ast

    path = Path("api/strategy/ai_capex_token_component.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"api.features", "api.brokers", "api.providers", "api.db"}
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _contains_forbidden_key(value) -> bool:
    forbidden = {"order", "target", "allocation", "rebalance", "execution"}
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(term in str(key).lower() for term in forbidden):
                return True
            if _contains_forbidden_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False
