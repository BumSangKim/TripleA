from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.strategy.ai_capex_token_input_adapter import (
    AICapexTokenInputAdapter,
    AICapexTokenInputAdapterError,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")


def test_normal_fixture_converts_to_raw_snapshot():
    data = _load("s1_expanding_accelerating.json")

    snapshot = AICapexTokenInputAdapter().adapt(data)

    assert snapshot.snapshot_id == "ai-capex-token-s1-fixture"
    assert snapshot.token_sources_current[0].period_role == "current"
    assert snapshot.token_sources_previous[0].period_role == "previous"
    assert {item.period_role for item in snapshot.capex_series} == {"t", "t_minus_1", "t_minus_2"}


def test_invalid_ambiguous_period_fixture_fails():
    data = _load("invalid_ambiguous_period_roles.json")

    with pytest.raises((AICapexTokenInputAdapterError, KeyError, ValueError)):
        AICapexTokenInputAdapter().adapt(data)


def test_future_data_leakage_probe_excludes_future_metrics():
    data = _load("future_data_leakage_probe.json")

    result = AICapexTokenInputAdapter().adapt_with_metadata(data)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "FUTURE_INPUT_EXCLUDED" in result.reason_codes
    assert set(result.excluded_metric_keys) == {"tokens.aggregate.synthetic", "capex.bigtech_ai_total"}


def test_time_guard_helper_is_called(monkeypatch):
    data = _load("s1_expanding_accelerating.json")
    calls = []

    def fake_is_available(value, decision_time):
        calls.append((value.metric_key, decision_time))
        return True

    monkeypatch.setattr("api.strategy.ai_capex_token_input_adapter.time_guard.is_available_for_decision", fake_is_available)

    snapshot = AICapexTokenInputAdapter().adapt(data)

    assert snapshot.snapshot_id == "ai-capex-token-s1-fixture"
    assert len(calls) == 5


def test_source_name_suffix_is_ignored():
    data = _load("invalid_ambiguous_period_roles.json")

    result = AICapexTokenInputAdapter().adapt_with_metadata(data)

    assert result.snapshot is None
    assert "MISSING_TOKEN_CURRENT_REVIEW_REQUIRED" in result.reason_codes


def test_poor_data_quality_adds_review_reason():
    data = _load("s1_expanding_accelerating.json")
    data["token_sources_current"][0]["quality_score"] = 0.2

    result = AICapexTokenInputAdapter().adapt_with_metadata(data)

    assert result.snapshot is not None
    assert "LOW_DATA_QUALITY_REVIEW_REQUIRED" in result.reason_codes
    assert "LOW_DATA_QUALITY_REVIEW_REQUIRED" in result.snapshot.metadata["reason_codes"]


def test_plugin_boundary_style_object_with_data_mapping_is_supported():
    class PluginLike:
        def __init__(self, data):
            self.data = data

    snapshot = AICapexTokenInputAdapter().adapt(PluginLike(_load("s3_expanding_decelerating_platform.json")))

    assert snapshot.snapshot_id == "ai-capex-token-s3-fixture"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
