from pathlib import Path

import yaml


MANIFEST_PATH = Path("config/pipelines/investment_decision.yaml")


def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_pipeline_manifest_file_exists_and_parses():
    assert MANIFEST_PATH.exists()
    assert isinstance(load_manifest(), dict)


def test_pipeline_manifest_required_top_level_fields():
    manifest = load_manifest()

    assert manifest["version"] == 1
    assert manifest["name"] == "investment_decision_pipeline"
    assert isinstance(manifest["stages"], list)
    assert isinstance(manifest["fallback_policy"], dict)


def test_pipeline_manifest_stage_contracts_are_complete():
    stages = load_manifest()["stages"]
    required_fields = {"id", "layer", "required_inputs", "required_outputs", "required_validations"}

    for stage in stages:
        assert required_fields <= set(stage)
        assert isinstance(stage["required_inputs"], list)
        assert isinstance(stage["required_outputs"], list)
        assert isinstance(stage["required_validations"], list)


def test_pipeline_manifest_stage_ids_are_unique_and_ordered():
    stages = load_manifest()["stages"]
    stage_ids = [stage["id"] for stage in stages]

    assert len(stage_ids) == len(set(stage_ids))
    assert stage_ids[0] == "collect_raw_data"
    assert stage_ids[-1] == "audit_report"
    assert stage_ids.index("hard_constraint_filter") < stage_ids.index("order_candidate_generation")


def test_pipeline_manifest_disallows_default_live_execution_and_aggressive_fallbacks():
    manifest = load_manifest()
    allowed_actions = set(manifest["fallback_policy"]["allowed_actions"])

    assert manifest["auto_execution_allowed"] is False
    assert not {"BUY", "INCREASE_RISK", "AUTO_EXECUTE"} & allowed_actions
