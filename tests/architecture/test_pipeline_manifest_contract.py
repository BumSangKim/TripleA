from pathlib import Path

from api.score_pipeline.pipeline_manifest import PipelineManifest, load_pipeline_manifest


MANIFEST_PATH = Path("config/pipelines/investment_decision.yaml")


def test_pipeline_manifest_loader_reads_config_file():
    manifest = load_pipeline_manifest(MANIFEST_PATH)

    assert isinstance(manifest, PipelineManifest)
    assert manifest.name == "investment_decision_pipeline"


def test_pipeline_stage_outputs_flow_to_later_inputs_or_audit_capture():
    manifest = load_pipeline_manifest(MANIFEST_PATH)
    stages = list(manifest.stages)
    audit_inputs = set(stages[-1].required_inputs)

    assert "all_intermediate_outputs" in audit_inputs
    for index, stage in enumerate(stages[:-1]):
        later_inputs = set()
        for later_stage in stages[index + 1 :]:
            later_inputs.update(later_stage.required_inputs)

        unconsumed_outputs = set(stage.required_outputs) - later_inputs
        assert not unconsumed_outputs or "all_intermediate_outputs" in audit_inputs


def test_data_quality_metadata_is_used_after_raw_data_stage():
    manifest = load_pipeline_manifest(MANIFEST_PATH)
    stages_after_raw = manifest.stages[1:]

    assert any("data_quality_metadata" in stage.required_inputs for stage in stages_after_raw)


def test_score_stage_requires_confidence_and_data_quality_validations():
    manifest = load_pipeline_manifest(MANIFEST_PATH)
    score_stage = next(stage for stage in manifest.stages if stage.id == "calculate_scores")
    validations = set(score_stage.required_validations)

    assert {"confidence_present", "data_quality_present"} <= validations


def test_sector_scoring_stage_keeps_component_and_confidence_validations():
    manifest = load_pipeline_manifest(MANIFEST_PATH)
    sector_stage = next(stage for stage in manifest.stages if stage.id == "sector_asset_scoring")
    validations = set(sector_stage.required_validations)

    assert {"component_scores_present", "confidence_present"} <= validations


def test_order_candidate_generation_runs_after_hard_constraint_filter():
    manifest = load_pipeline_manifest(MANIFEST_PATH)
    stage_ids = [stage.id for stage in manifest.stages]

    assert stage_ids.index("hard_constraint_filter") < stage_ids.index("order_candidate_generation")


def test_audit_report_requires_all_intermediate_outputs():
    manifest = load_pipeline_manifest(MANIFEST_PATH)
    audit_report = manifest.stages[-1]

    assert audit_report.id == "audit_report"
    assert "all_intermediate_outputs" in audit_report.required_inputs
