from datetime import date
from pathlib import Path

import pytest

from api.score_pipeline.plugins.valuation_engine import PERBounds, ValuationEngine, clamp_target_per


AS_OF_DATE = date(2026, 5, 31)


def test_valuation_engine_normal_fair_value_calculation():
    result = _evaluate(forward_eps=2.0, midcycle_eps=1.5, base_per=20.0, last_price=30.0)

    assert result.eps_persistence == 1.0
    assert result.target_per == pytest.approx(25.0)
    assert result.fair_value == pytest.approx(37.5)
    assert result.fair_value_ratio == pytest.approx(1.25)
    assert any(reason.code == "VALUATION_COMPUTED" for reason in result.reason_codes)


def test_valuation_engine_missing_eps_returns_unavailable_not_zero():
    result = _evaluate(forward_eps=None, midcycle_eps=1.5, base_per=20.0, last_price=30.0)

    assert result.fair_value is None
    assert result.fair_value_ratio is None
    assert result.target_per is None
    assert result.confidence == 0.0
    assert any(reason.code == "VALUATION_MISSING_EPS" for reason in result.reason_codes)
    assert any(warning.code == "VALUATION_UNAVAILABLE" for warning in result.warnings)


def test_valuation_engine_negative_eps_is_conservative():
    result = _evaluate(forward_eps=-1.0, midcycle_eps=1.5, base_per=20.0, last_price=30.0)

    assert result.fair_value is None
    assert result.fair_value_ratio is None
    assert result.forward_eps == -1.0
    assert any(reason.code == "VALUATION_UNAVAILABLE" for reason in result.reason_codes)


def test_valuation_engine_macro_multiplier_affects_fair_value_without_action():
    neutral = _evaluate(macro_multiplier=1.0)
    penalized = _evaluate(macro_multiplier=0.8)

    assert penalized.fair_value < neutral.fair_value
    assert any(reason.code == "VALUATION_MACRO_PENALTY" for reason in penalized.reason_codes)
    for field_name in ("action", "buy", "sell", "order_candidate"):
        assert not hasattr(penalized, field_name)


def test_valuation_engine_per_bounds_clamp_correctly():
    bounds = PERBounds(min_per=10.0, max_per=30.0)

    assert clamp_target_per(125.0, bounds) == 30.0
    assert clamp_target_per(5.0, bounds) == 10.0
    assert _evaluate(base_per=100.0, per_bounds=bounds).target_per == 30.0


def test_valuation_engine_core_missing_price_does_not_create_false_cheap_signal():
    result = _evaluate(last_price=None)

    assert result.fair_value is None
    assert result.fair_value_ratio is None
    assert result.confidence == 0.0
    assert any(warning.code == "VALUATION_UNAVAILABLE" for warning in result.warnings)


def test_valuation_engine_has_no_forbidden_imports():
    source = Path("api/score_pipeline/plugins/valuation_engine.py").read_text(encoding="utf-8").lower()

    forbidden = ["fastapi", "sqlite3", "api.brokers", "api.strategy", "api.features.orders", "kis"]
    assert not [item for item in forbidden if item in source]


def _evaluate(**overrides):
    params = {
        "asset_id": "BIO_INFRA",
        "as_of_date": AS_OF_DATE,
        "forward_eps": 2.0,
        "midcycle_eps": 1.5,
        "base_per": 20.0,
        "last_price": 30.0,
        "macro_multiplier": 1.0,
        "per_bounds": PERBounds(min_per=10.0, max_per=30.0),
        "confidence": 0.9,
        "data_quality": 0.85,
    }
    params.update(overrides)
    return ValuationEngine().evaluate(**params)
