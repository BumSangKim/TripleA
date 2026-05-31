from pathlib import Path

import pytest

from api.score_pipeline.plugins.capex_common import (
    clamp,
    conservative_score_on_missing,
    safe_ratio,
    score_from_z,
    weighted_average,
)


def test_weighted_average_with_complete_values():
    result = weighted_average(
        {"moat": 0.8, "demand": 0.6, "quality": 0.4},
        {"moat": 0.5, "demand": 0.3, "quality": 0.2},
    )

    assert result == pytest.approx(0.66)


def test_weighted_average_missing_values_conservative_neutral():
    result = weighted_average({"moat": 0.8}, {"moat": 0.5, "quality": 0.5})

    assert result == pytest.approx(0.65)


def test_weighted_average_ignore_missing_renormalizes_remaining_values():
    result = weighted_average({"moat": 0.8}, {"moat": 0.5, "quality": 0.5}, missing_policy="ignore")

    assert result == pytest.approx(0.8)


def test_safe_ratio_returns_zero_for_missing_or_zero_denominator():
    assert safe_ratio(10, 0) == 0.0
    assert safe_ratio(None, 10) == 0.0
    assert safe_ratio(3, 2) == pytest.approx(1.5)


def test_clamp_boundaries_and_invalid_bounds():
    assert clamp(1.2) == 1.0
    assert clamp(-0.2) == 0.0
    assert clamp(5, low=1, high=4) == 4.0
    with pytest.raises(ValueError, match="low"):
        clamp(0.5, low=1.0, high=0.0)


def test_score_from_z_is_deterministic_and_bounded():
    assert score_from_z(0) == pytest.approx(0.5)
    assert score_from_z(1.0, center=0.5, scale=0.2) == pytest.approx(0.7)
    assert score_from_z(10.0) == 1.0
    assert score_from_z(None) == pytest.approx(0.5)


def test_conservative_score_on_missing_does_not_increase_risk():
    fallback = conservative_score_on_missing()

    assert fallback == {
        "score": 0.5,
        "confidence": 0.0,
        "fallback_action": "REVIEW_REQUIRED",
    }


def test_capex_common_has_no_forbidden_imports():
    source = Path("api/score_pipeline/plugins/capex_common.py").read_text(encoding="utf-8")

    forbidden = ["fastapi", "sqlite3", "api.brokers", "api.strategy", "api.features.orders", "kis"]
    assert not [item for item in forbidden if item in source.lower()]
