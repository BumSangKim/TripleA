from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from api.strategy.ai_capex_token_component import AICapexTokenDiagnosticComponent
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
TEST_CONFIG = {
    "enabled": False,
    "diagnostic_only": True,
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}
RISK_INCREASING_TERMS = {
    "BUY",
    "INCREASE_RISK",
    "INCREASE_SATELLITE_WEIGHT",
    "FORCE_REBALANCE",
    "AUTO_EXECUTE",
    "LIVE_EXECUTE",
}


def test_future_fixture_metric_is_excluded_at_backtest_decision_date():
    payload = _load("future_data_leakage_probe.json")

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "FUTURE_INPUT_EXCLUDED" in result.reason_codes
    assert set(result.excluded_metric_keys) >= {"tokens.aggregate.synthetic", "capex.bigtech_ai_total"}


def test_future_only_positive_signal_cannot_create_risk_increasing_output():
    payload = _future_only_positive_payload(decision_date="2026-02-10")

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "FUTURE_INPUT_EXCLUDED" in result.reason_codes
    assert RISK_INCREASING_TERMS.isdisjoint(set(result.reason_codes))
    assert RISK_INCREASING_TERMS.isdisjoint(set(result.excluded_metric_keys))


def test_later_decision_date_can_include_newly_available_signal():
    early_payload = _future_only_positive_payload(decision_date="2026-02-10")
    later_payload = _future_only_positive_payload(decision_date="2026-02-21")

    early = AICapexTokenInputAdapter().adapt_with_metadata(early_payload)
    later_diagnostic = AICapexTokenDiagnosticComponent().build(later_payload, config=TEST_CONFIG)

    assert early.snapshot is None
    assert later_diagnostic.components
    assert later_diagnostic.components[0].scenario_distribution.dominant_scenario == "S1"
    assert all(component.diagnostic_only for component in later_diagnostic.components)
    assert _contains_risk_increasing_output(asdict(later_diagnostic)) is False


def test_future_revised_data_does_not_change_same_decision_date_output():
    baseline_payload = _load("s1_expanding_accelerating.json")
    revised_payload = copy.deepcopy(baseline_payload)
    revised_payload["token_sources_current"].append(
        {
            "metric_key": "tokens.aggregate.synthetic.revised",
            "period_role": "current",
            "value": 999.0,
            "as_of_date": "2026-01-31",
            "available_at": "2026-02-20T00:00:00",
            "source": "synthetic_future_revision",
            "quality_score": 0.95,
            "missing_ratio": 0.0,
            "is_stale": False,
        }
    )
    revised_payload["capex_series"].append(
        {
            "metric_key": "capex.bigtech_ai_total.revised",
            "period_role": "t",
            "value": 999.0,
            "as_of_date": "2026-01-31",
            "available_at": "2026-02-20T00:00:00",
            "source": "synthetic_future_revision",
            "quality_score": 0.95,
            "missing_ratio": 0.0,
            "is_stale": False,
        }
    )

    baseline = AICapexTokenDiagnosticComponent().build(baseline_payload, config=TEST_CONFIG)
    revised = AICapexTokenDiagnosticComponent().build(revised_payload, config=TEST_CONFIG)

    assert [component.component_score for component in revised.components] == pytest.approx(
        [component.component_score for component in baseline.components]
    )
    assert [component.scenario_distribution.probabilities for component in revised.components] == [
        component.scenario_distribution.probabilities for component in baseline.components
    ]


def test_same_input_and_parameter_version_are_reproducible():
    payload = _load("s1_expanding_accelerating.json")

    first = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)
    second = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)

    assert asdict(first) == asdict(second)


def test_missing_available_at_metadata_triggers_review_required_failure():
    payload = _load("s1_expanding_accelerating.json")
    payload["token_sources_current"][0].pop("available_at")

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "INVALID_EXPLICIT_PERIOD_ROLE_REVIEW_REQUIRED" in result.reason_codes
    assert "MISSING_TOKEN_CURRENT_REVIEW_REQUIRED" in result.reason_codes


def _future_only_positive_payload(*, decision_date: str) -> dict:
    payload = _load("s1_expanding_accelerating.json")
    payload["decision_date"] = decision_date
    payload["snapshot_id"] = f"ai-capex-token-future-positive-{decision_date}"
    for row in [*payload["token_sources_current"], *payload["capex_series"]]:
        if row["period_role"] in {"current", "t"}:
            row["available_at"] = "2026-02-20T00:00:00"
            row["source"] = "synthetic_future_positive_probe"
    return payload


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _contains_risk_increasing_output(value) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).upper() in RISK_INCREASING_TERMS:
                return True
            if _contains_risk_increasing_output(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_contains_risk_increasing_output(item) for item in value)
    elif isinstance(value, str):
        return value.upper() in RISK_INCREASING_TERMS
    return False
