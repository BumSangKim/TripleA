from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenFallbackState,
    CapexAccelerationDirection,
    TokenConsumptionDirection,
)
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")


@pytest.mark.parametrize(
    "fixture_name,token_direction,capex_direction",
    [
        ("s1_expanding_accelerating.json", TokenConsumptionDirection.EXPANDING, CapexAccelerationDirection.ACCELERATING),
        ("s3_expanding_decelerating_platform.json", TokenConsumptionDirection.EXPANDING, CapexAccelerationDirection.DECELERATING),
        ("s7_contracting_accelerating_overinvestment.json", TokenConsumptionDirection.CONTRACTING, CapexAccelerationDirection.ACCELERATING),
    ],
)
def test_fixture_token_and_capex_directions(fixture_name, token_direction, capex_direction):
    features = AICapexTokenFeatureBuilder().build(_snapshot(fixture_name), config=_approved_config())

    assert features.token_direction == token_direction
    assert features.capex_direction == capex_direction
    assert features.fallback_state is None


def test_raw_feature_values_are_calculated_from_explicit_periods():
    features = AICapexTokenFeatureBuilder().build(_snapshot("s1_expanding_accelerating.json"), config=_approved_config())

    assert features.token_consumption_change == pytest.approx(0.2)
    assert features.capex_growth == pytest.approx(145 / 115 - 1)
    assert features.capex_acceleration == pytest.approx((145 / 115 - 1) - (115 / 100 - 1))


def test_previous_token_zero_falls_back_to_review_required():
    snapshot = _snapshot("s1_expanding_accelerating.json")
    previous = snapshot.token_sources_previous[0]
    broken = previous.__class__(**{**previous.__dict__, "value": 0.0})
    snapshot = snapshot.__class__(**{**snapshot.__dict__, "token_sources_previous": (broken,)})

    features = AICapexTokenFeatureBuilder().build(snapshot, config=_approved_config())

    assert features.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED
    assert "TOKEN_PREVIOUS_INVALID_REVIEW_REQUIRED" in features.reason_codes


def test_missing_capex_t_minus_2_falls_back_before_feature_math():
    snapshot = _snapshot("s1_expanding_accelerating.json")
    snapshot = SimpleNamespace(**{**snapshot.__dict__, "capex_series": tuple(snapshot.capex_series[:2])})

    features = AICapexTokenFeatureBuilder().build(snapshot, config=_approved_config())

    assert features.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED
    assert "MISSING_CAPEX_PERIOD_REVIEW_REQUIRED" in features.reason_codes


def test_null_or_missing_config_keeps_normalized_scores_review_required():
    features = AICapexTokenFeatureBuilder().build(_snapshot("s1_expanding_accelerating.json"), config=None)

    assert features.fallback_state == AICapexTokenFallbackState.REVIEW_REQUIRED
    assert "NORMALIZATION_PARAMETERS_REVIEW_REQUIRED" in features.reason_codes
    assert "normalized_directional_scores_not_computed" in features.warnings


def test_poor_data_quality_lowers_data_quality_and_review_reason():
    snapshot = _snapshot("s1_expanding_accelerating.json")
    current = snapshot.token_sources_current[0]
    poor = current.__class__(**{**current.__dict__, "quality_score": 0.2})
    snapshot = snapshot.__class__(**{**snapshot.__dict__, "token_sources_current": (poor,)})

    features = AICapexTokenFeatureBuilder().build(snapshot, config=_approved_config())

    assert features.data_quality == pytest.approx(0.2)


def _snapshot(name: str):
    data = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return AICapexTokenInputAdapter().adapt(data)


def _approved_config() -> dict:
    return {"normalization_parameters": {"metadata": {"approved": True}}}
