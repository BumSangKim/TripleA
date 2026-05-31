from pathlib import Path

import yaml


UNIVERSE_FILE = Path("config/capex_bottleneck_universe.yaml")
REQUIRED_LAYER_FIELDS = {
    "enabled",
    "role",
    "risk_class",
    "example_tickers",
    "exclusion_tags",
    "notes",
}
EXPECTED_LAYERS = {
    "tools_consumables",
    "bioprocessing",
    "clinical_data_cro",
    "cdmo_manufacturing",
    "bio_data_platform",
    "high_risk_ai_biotech",
}
TARGET_WEIGHT_KEYS = {"target_weight", "target_weights", "fixed_weight", "allocation_weight"}


def test_capex_bottleneck_universe_yaml_parses():
    data = yaml.safe_load(UNIVERSE_FILE.read_text(encoding="utf-8"))

    assert data["source"] == "research_spec"
    assert data["advisory_only"] is True
    assert set(data["layers"]) == EXPECTED_LAYERS


def test_capex_bottleneck_layers_have_required_metadata():
    data = yaml.safe_load(UNIVERSE_FILE.read_text(encoding="utf-8"))

    for layer_name, layer in data["layers"].items():
        assert REQUIRED_LAYER_FIELDS.issubset(layer), layer_name
        assert isinstance(layer["enabled"], bool), layer_name
        assert layer["role"], layer_name
        assert layer["risk_class"], layer_name
        assert isinstance(layer["example_tickers"], list), layer_name
        assert layer["example_tickers"], layer_name
        assert isinstance(layer["exclusion_tags"], list), layer_name
        assert layer["notes"], layer_name


def test_capex_bottleneck_universe_has_no_fixed_target_weights():
    data = yaml.safe_load(UNIVERSE_FILE.read_text(encoding="utf-8"))
    found = _find_forbidden_keys(data, TARGET_WEIGHT_KEYS)

    assert found == []


def test_capex_bottleneck_exclusion_tags_cover_clinical_event_risks():
    data = yaml.safe_load(UNIVERSE_FILE.read_text(encoding="utf-8"))
    all_tags = {
        tag
        for layer in data["layers"].values()
        for tag in layer["exclusion_tags"]
    }

    assert "clinical_event_risk" in all_tags
    assert "single_pipeline_risk" in all_tags
    assert "binary_event_risk" in data["layers"]["high_risk_ai_biotech"]["exclusion_tags"]


def test_high_risk_groups_are_not_core_anchor_by_default():
    data = yaml.safe_load(UNIVERSE_FILE.read_text(encoding="utf-8"))

    for layer_name, layer in data["layers"].items():
        if "high" in layer["risk_class"]:
            assert layer["role"] != "core_anchor", layer_name
    assert data["layers"]["high_risk_ai_biotech"]["enabled"] is False
    assert data["layers"]["high_risk_ai_biotech"]["role"] == "observation_only"


def _find_forbidden_keys(value, forbidden_keys):
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden_keys:
                found.append(key)
            found.extend(_find_forbidden_keys(child, forbidden_keys))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_forbidden_keys(child, forbidden_keys))
    return found
