from pathlib import Path

import yaml

from api.strategy.score_layer import load_score_definitions


SCORE_DEFINITION_FILE = Path("config/score_definitions_ai.yaml")
REQUIRED_KEYS = {
    "enabled",
    "score_type",
    "subject_type",
    "subject_id",
    "source_plugin_id",
    "source_feature_key",
    "normalization",
    "smoothing",
    "confidence",
    "data_quality",
    "parameter_version",
    "model_version",
}
EXPECTED_SCORE_KEYS = {
    "feature:ai_capex_cycle",
    "score:bio_capex_bottleneck",
    "score:capex_scenario_distribution",
    "score:valuation_fair_value_ratio",
}
ACTION_TERMS = {"BUY", "SELL", "ORDER", "AUTO_EXECUTE", "TARGET_WEIGHT", "FIXED_WEIGHT"}


def test_ai_score_definitions_yaml_parses():
    data = yaml.safe_load(SCORE_DEFINITION_FILE.read_text(encoding="utf-8"))

    assert set(data["scores"]) == EXPECTED_SCORE_KEYS


def test_ai_score_definitions_load_with_existing_loader():
    definitions = load_score_definitions(SCORE_DEFINITION_FILE)

    assert set(definitions) == EXPECTED_SCORE_KEYS


def test_ai_score_definitions_have_required_keys():
    data = yaml.safe_load(SCORE_DEFINITION_FILE.read_text(encoding="utf-8"))

    for score_key, definition in data["scores"].items():
        assert REQUIRED_KEYS.issubset(definition), score_key
        assert definition["normalization"]["method"]
        assert definition["normalization"]["direction"]
        assert definition["normalization"]["params"]
        assert definition["smoothing"]["method"] == "ema"


def test_ai_score_definitions_have_quality_and_version_metadata():
    data = yaml.safe_load(SCORE_DEFINITION_FILE.read_text(encoding="utf-8"))

    for score_key, definition in data["scores"].items():
        assert definition["data_quality"]["min_required"] is not None, score_key
        assert 0 <= definition["data_quality"]["min_required"] <= 1, score_key
        assert definition["confidence"]["default"] is not None, score_key
        assert definition["parameter_version"].strip(), score_key
        assert definition["model_version"].strip(), score_key


def test_ai_score_definitions_do_not_map_to_actions_or_fixed_weights():
    data = yaml.safe_load(SCORE_DEFINITION_FILE.read_text(encoding="utf-8"))
    payload = yaml.safe_dump(data).upper()

    for term in ACTION_TERMS:
        assert term not in payload
