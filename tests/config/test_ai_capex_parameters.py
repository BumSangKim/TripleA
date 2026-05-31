from pathlib import Path

import pytest
import yaml


PARAMETER_FILE = Path("config/parameters/ai_capex_cycle.yaml")
REQUIRED_FIELDS = {
    "name",
    "value",
    "version",
    "valid_from",
    "valid_to",
    "source",
    "reason",
    "approved",
    "rollback_condition",
    "affected_modules",
}
CONSERVATIVE_FALLBACKS = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
AGGRESSIVE_TERMS = {"BUY", "INCREASE_RISK", "AUTO_EXECUTE", "EXECUTE_ORDER", "SELL_NOW"}


@pytest.fixture()
def ai_capex_parameters():
    return yaml.safe_load(PARAMETER_FILE.read_text(encoding="utf-8"))


def test_ai_capex_parameter_yaml_parses(ai_capex_parameters):
    assert ai_capex_parameters["fallback_policy"] == "REVIEW_REQUIRED"
    assert isinstance(ai_capex_parameters["parameters"], list)
    assert ai_capex_parameters["parameters"]


def test_ai_capex_parameters_have_required_metadata(ai_capex_parameters):
    for entry in ai_capex_parameters["parameters"]:
        assert REQUIRED_FIELDS.issubset(entry), f"{entry.get('name')} missing metadata"
        assert entry["source"] == str(PARAMETER_FILE)
        assert entry["approved"] is False
        assert entry["rollback_condition"]
        assert entry["affected_modules"]


def test_ai_capex_weights_sum_to_one(ai_capex_parameters):
    weights = _parameter(ai_capex_parameters, "ai_cycle_weights")["value"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_ai_capex_fallback_policy_is_conservative(ai_capex_parameters):
    assert ai_capex_parameters["fallback_policy"] in CONSERVATIVE_FALLBACKS


def test_ai_capex_parameters_do_not_contain_aggressive_fallbacks(ai_capex_parameters):
    payload = yaml.safe_dump(ai_capex_parameters).upper()
    for term in AGGRESSIVE_TERMS:
        assert term not in payload


def test_ai_capex_normalization_bounds_are_ordered(ai_capex_parameters):
    bounds = _parameter(ai_capex_parameters, "normalization_bounds")["value"]
    for metric, metric_bounds in bounds.items():
        assert metric_bounds["lower"] < metric_bounds["upper"], metric


def _parameter(data, name):
    for entry in data["parameters"]:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"missing parameter: {name}")
