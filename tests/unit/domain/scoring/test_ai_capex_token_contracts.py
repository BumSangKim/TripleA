from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path

import pytest

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenContractError,
    AICapexTokenFallbackState,
    AICapexTokenFeatureSet,
    AICapexTokenMetric,
    AICapexTokenRawSnapshot,
    AICapexTokenScenarioDistribution,
    AICapexTokenSectorComponentScore,
    CapexAccelerationDirection,
    TokenConsumptionDirection,
    validate_fallback_state,
    validate_scenario_distribution,
    validate_token_period_role,
)


def test_dataclass_creation_normal_case():
    distribution = _distribution()
    score = AICapexTokenSectorComponentScore(
        sector_id="semiconductor_hbm",
        as_of_date=date(2026, 1, 31),
        component_score=0.62,
        confidence=0.7,
        data_quality=0.8,
        diagnostic_only=True,
        scenario_distribution=distribution,
        reason_codes=("AI_CAPEX_TOKEN_DIAGNOSTIC",),
    )

    score_dict = score.to_score_signal_dict()

    assert score_dict["score"] == 0.62
    assert set(score_dict) >= {
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


def test_raw_snapshot_requires_explicit_period_roles():
    snapshot = AICapexTokenRawSnapshot(
        snapshot_id="snapshot-001",
        decision_date=date(2026, 1, 31),
        token_sources_current=(_metric("tokens.google", "current"),),
        token_sources_previous=(_metric("tokens.google", "previous"),),
        capex_series=(
            _metric("capex.total", "t"),
            _metric("capex.total", "t_minus_1"),
            _metric("capex.total", "t_minus_2"),
        ),
        sector_metrics={"semiconductor_hbm": {"valuation_burden_score": 0.4}},
    )

    assert snapshot.snapshot_id == "snapshot-001"


def test_invalid_period_role_fails():
    with pytest.raises(AICapexTokenContractError):
        validate_token_period_role("latest")


def test_source_name_only_current_previous_hint_fails():
    with pytest.raises(AICapexTokenContractError):
        AICapexTokenRawSnapshot(
            snapshot_id="snapshot-001",
            decision_date=date(2026, 1, 31),
            token_sources_current=(_metric("tokens.google", "previous", source="google_current_file"),),
            token_sources_previous=(_metric("tokens.google", "previous"),),
            capex_series=(
                _metric("capex.total", "t"),
                _metric("capex.total", "t_minus_1"),
                _metric("capex.total", "t_minus_2"),
            ),
            sector_metrics={},
        )


def test_scenario_distribution_missing_or_bad_sum_fails():
    probabilities = {f"S{i}": 1 / 9 for i in range(1, 10)}
    probabilities.pop("S9")
    with pytest.raises(AICapexTokenContractError):
        validate_scenario_distribution(probabilities)

    bad_sum = {f"S{i}": 0.1 for i in range(1, 10)}
    with pytest.raises(AICapexTokenContractError):
        validate_scenario_distribution(bad_sum)


def test_fallback_state_contains_no_risk_increasing_values():
    allowed = {item.value for item in AICapexTokenFallbackState}

    assert {"BUY", "INCREASE_RISK", "FORCE_REBALANCE", "AUTO_EXECUTE"}.isdisjoint(allowed)
    with pytest.raises(AICapexTokenContractError):
        validate_fallback_state("INCREASE_RISK")


def test_feature_set_accepts_conservative_fallback_state():
    feature_set = AICapexTokenFeatureSet(
        snapshot_id="snapshot-001",
        as_of_date=date(2026, 1, 31),
        token_consumption_change=None,
        capex_growth=None,
        capex_acceleration=None,
        token_direction=TokenConsumptionDirection.STABLE,
        capex_direction=CapexAccelerationDirection.STABLE,
        data_quality=0.0,
        fallback_state=AICapexTokenFallbackState.REVIEW_REQUIRED,
        reason_codes=("MISSING_INPUT_REVIEW_REQUIRED",),
    )

    assert feature_set.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED


def test_domain_contract_imports_stay_pure():
    path = Path("api/domain/scoring/ai_capex_token_contracts.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features", "api.strategy"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)


def _metric(metric_key: str, period_role: str, *, source: str = "fixture") -> AICapexTokenMetric:
    return AICapexTokenMetric(
        metric_key=metric_key,
        period_role=period_role,
        value=100.0,
        as_of_date=date(2026, 1, 31),
        available_at=datetime(2026, 2, 1),
        source=source,
        quality_score=0.95,
    )


def _distribution() -> AICapexTokenScenarioDistribution:
    return AICapexTokenScenarioDistribution(
        as_of_date=date(2026, 1, 31),
        probabilities={f"S{i}": 1 / 9 for i in range(1, 10)},
        dominant_scenario="S1",
        dominant_scenario_explanation_only=True,
        data_quality=0.8,
        confidence=0.7,
    )
