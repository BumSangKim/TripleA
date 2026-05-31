from pathlib import Path

import pytest
import yaml


PARAMETER_FILE = Path("config/parameters/bio_capex_bottleneck.yaml")
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
CLINICAL_EVENT_TERMS = {"TRIAL", "PDUFA", "APPROVAL_EVENT", "CLINICAL_SUCCESS", "FDA_APPROVAL"}
ACTION_TERMS = {"BUY", "SELL", "AUTO_EXECUTE", "ORDER_SUBMIT", "INCREASE_RISK"}


@pytest.fixture()
def bio_capex_parameters():
    return yaml.safe_load(PARAMETER_FILE.read_text(encoding="utf-8"))


def test_bio_capex_parameter_yaml_parses(bio_capex_parameters):
    assert bio_capex_parameters["fallback_policy"] == "REVIEW_REQUIRED"
    assert isinstance(bio_capex_parameters["parameters"], list)
    assert bio_capex_parameters["parameters"]


def test_bio_capex_parameters_have_required_metadata(bio_capex_parameters):
    for entry in bio_capex_parameters["parameters"]:
        assert REQUIRED_FIELDS.issubset(entry), f"{entry.get('name')} missing metadata"
        assert entry["source"] == str(PARAMETER_FILE)
        assert entry["approved"] is False
        assert entry["rollback_condition"]
        assert entry["affected_modules"]


def test_bio_capex_final_score_formula_matches_spec(bio_capex_parameters):
    weights = _parameter(bio_capex_parameters, "final_score_weights")["value"]

    assert weights["structural_moat"] == pytest.approx(0.40)
    assert weights["demand_momentum"] == pytest.approx(0.35)
    assert weights["financial_quality"] == pytest.approx(0.25)
    assert weights["risk_penalty_multiplier"] == pytest.approx(0.35)
    assert (
        weights["structural_moat"]
        + weights["demand_momentum"]
        + weights["financial_quality"]
    ) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "parameter_name",
    [
        "structural_moat_weights",
        "demand_momentum_weights",
        "financial_quality_weights",
        "risk_penalty_weights",
    ],
)
def test_bio_capex_component_weight_groups_sum_to_one(bio_capex_parameters, parameter_name):
    weights = _parameter(bio_capex_parameters, parameter_name)["value"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_bio_capex_formula_references_score_components_not_actions(bio_capex_parameters):
    final_weights = _parameter(bio_capex_parameters, "final_score_weights")["value"]
    payload = " ".join(final_weights).upper()
    for term in ACTION_TERMS:
        assert term not in payload


def test_bio_capex_clinical_event_terms_are_not_score_inputs(bio_capex_parameters):
    parameter_names_and_keys = []
    for entry in bio_capex_parameters["parameters"]:
        parameter_names_and_keys.append(entry["name"])
        if isinstance(entry["value"], dict):
            parameter_names_and_keys.extend(entry["value"].keys())
    payload = " ".join(parameter_names_and_keys).upper()
    for term in CLINICAL_EVENT_TERMS:
        assert term not in payload


def test_bio_capex_fallback_states_are_conservative(bio_capex_parameters):
    assert bio_capex_parameters["fallback_policy"] in CONSERVATIVE_FALLBACKS
    missing_data = _parameter(bio_capex_parameters, "missing_data_behavior")["value"]
    assert missing_data["fallback_action"] in CONSERVATIVE_FALLBACKS
    assert missing_data["publish_score_when_required_group_missing"] is False


def _parameter(data, name):
    for entry in data["parameters"]:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"missing parameter: {name}")
