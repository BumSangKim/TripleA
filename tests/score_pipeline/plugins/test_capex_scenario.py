from datetime import date
from pathlib import Path

import pytest

from api.score_pipeline.plugins.capex_scenario import CapexScenarioEngine, SCENARIOS


def test_capex_scenario_distribution_sums_to_one():
    result = _evaluate()

    assert set(result.distribution) == set(SCENARIOS)
    assert sum(result.distribution.values()) == pytest.approx(1.0)


def test_capex_scenario_dominant_is_distribution_max():
    result = _evaluate(ai_capex_cycle_score=0.9, tcr=1.0, capex_acceleration=1.0, macro_multiplier=1.0)

    assert result.dominant_scenario == max(result.distribution, key=result.distribution.get)
    assert result.dominant_scenario in SCENARIOS


def test_capex_scenario_low_data_quality_lowers_confidence():
    high_quality = _evaluate(data_quality=0.95)
    low_quality = _evaluate(data_quality=0.25)

    assert low_quality.confidence < high_quality.confidence
    assert any(reason.code == "CAPEX_SCENARIO_LOW_DATA_QUALITY" for reason in low_quality.reason_codes)
    assert any(warning.code == "CAPEX_SCENARIO_LOW_DATA_QUALITY" for warning in low_quality.warnings)


def test_capex_scenario_edge_inputs_do_not_produce_negative_or_nan_probabilities():
    result = _evaluate(
        ai_capex_cycle_score=-10.0,
        tcr=float("nan"),
        tce=100.0,
        capex_acceleration=-100.0,
        macro_multiplier=100.0,
    )

    assert sum(result.distribution.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in result.distribution.values())
    assert result.confidence == 0.0
    assert any(reason.code == "CAPEX_SCENARIO_INPUT_MISSING" for reason in result.reason_codes)


def test_capex_scenario_output_has_no_fixed_allocation_fields():
    result = _evaluate()

    for field_name in ("target_weight", "target_weights", "allocation", "order_candidate"):
        assert not hasattr(result, field_name)


def test_capex_scenario_engine_has_no_forbidden_imports():
    source = Path("api/score_pipeline/plugins/capex_scenario.py").read_text(encoding="utf-8").lower()

    forbidden = ["fastapi", "sqlite3", "api.brokers", "api.strategy", "api.features.orders", "kis"]
    assert not [item for item in forbidden if item in source]


def _evaluate(**overrides):
    params = {
        "as_of_date": date(2026, 5, 31),
        "ai_capex_cycle_score": 0.7,
        "tcr": 0.2,
        "tce": 0.3,
        "capex_acceleration": 0.1,
        "macro_multiplier": 0.8,
        "data_quality": 0.9,
    }
    params.update(overrides)
    return CapexScenarioEngine().evaluate(**params)
