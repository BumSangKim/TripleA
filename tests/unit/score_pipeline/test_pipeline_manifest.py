from pathlib import Path

import pytest
import yaml

from api.score_pipeline.pipeline_manifest import PipelineManifestError, load_pipeline_manifest


MANIFEST_PATH = Path("config/pipelines/investment_decision.yaml")


def test_load_pipeline_manifest_success():
    manifest = load_pipeline_manifest(MANIFEST_PATH)

    assert manifest.name == "investment_decision_pipeline"
    assert manifest.auto_execution_allowed is False
    assert manifest.stages[0].id == "collect_raw_data"
    assert manifest.stages[-1].id == "audit_report"


def test_duplicate_stage_id_fails(tmp_path: Path):
    raw = _manifest_raw()
    raw["stages"][1]["id"] = raw["stages"][0]["id"]

    with pytest.raises(PipelineManifestError, match="duplicate stage ids"):
        load_pipeline_manifest(_write_manifest(tmp_path, raw))


def test_collect_raw_data_must_be_first(tmp_path: Path):
    raw = _manifest_raw()
    raw["stages"][0], raw["stages"][1] = raw["stages"][1], raw["stages"][0]

    with pytest.raises(PipelineManifestError, match="collect_raw_data must be the first stage"):
        load_pipeline_manifest(_write_manifest(tmp_path, raw))


def test_audit_report_must_be_last(tmp_path: Path):
    raw = _manifest_raw()
    raw["stages"][-1], raw["stages"][-2] = raw["stages"][-2], raw["stages"][-1]

    with pytest.raises(PipelineManifestError, match="audit_report must be the last stage"):
        load_pipeline_manifest(_write_manifest(tmp_path, raw))


def test_hard_constraint_filter_must_precede_simulation_output(tmp_path: Path):
    raw = _manifest_raw()
    stage_ids = [stage["id"] for stage in raw["stages"]]
    hard_constraint_index = stage_ids.index("hard_constraint_filter")
    simulation_output_index = stage_ids.index("simulation_output_generation")
    raw["stages"][hard_constraint_index], raw["stages"][simulation_output_index] = (
        raw["stages"][simulation_output_index],
        raw["stages"][hard_constraint_index],
    )

    with pytest.raises(PipelineManifestError, match="hard_constraint_filter must run before simulation_output_generation"):
        load_pipeline_manifest(_write_manifest(tmp_path, raw))


def test_auto_execution_allowed_true_fails(tmp_path: Path):
    raw = _manifest_raw()
    raw["auto_execution_allowed"] = True

    with pytest.raises(PipelineManifestError, match="auto_execution_allowed must be false"):
        load_pipeline_manifest(_write_manifest(tmp_path, raw))


def test_fallback_allowed_buy_fails(tmp_path: Path):
    raw = _manifest_raw()
    raw["fallback_policy"]["allowed_actions"].append("BUY")

    with pytest.raises(PipelineManifestError, match="fallback actions cannot be both allowed and forbidden"):
        load_pipeline_manifest(_write_manifest(tmp_path, raw))


def _manifest_raw() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def _write_manifest(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "investment_decision.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path
