from __future__ import annotations

import json
from pathlib import Path

from api.features.backtests.ai_capex_token_tuning_execution_test import (
    write_ai_capex_token_tuning_execution_validation_report,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token_tuning")


def test_tuning_report_generation_writes_required_json_keys(tmp_path):
    json_path = tmp_path / "tuning_execution_validation_report.json"
    markdown_path = tmp_path / "tuning_execution_validation_report.md"

    report = _write_report(json_path, markdown_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert payload == report
    assert {
        "status",
        "candidate_count",
        "unique_parameter_hash_count",
        "unique_output_signature_count",
        "unique_metric_signature_count",
        "memory_cycle_coverage",
        "selected_candidate_id",
        "rejected_candidates",
        "objective_breakdown",
        "no_op_tuning_detected",
        "leakage_check_passed",
        "diagnostic_only",
        "production_ready",
    }.issubset(payload)
    assert payload["production_ready"] is False
    assert payload["diagnostic_only"] is True


def test_tuning_report_markdown_includes_validation_sections(tmp_path):
    json_path = tmp_path / "tuning_execution_validation_report.json"
    markdown_path = tmp_path / "tuning_execution_validation_report.md"

    _write_report(json_path, markdown_path)
    markdown = markdown_path.read_text(encoding="utf-8")

    assert "AI Capex-Token Tuning Execution Validation Report" in markdown
    assert "Memory Cycle Coverage" in markdown
    assert "Candidate Summary" in markdown
    assert "Rejected Candidates" in markdown
    assert "Objective Breakdown" in markdown
    assert "Leakage / No-Op Checks" in markdown
    assert "production_ready: `False`" in markdown
    assert "leakage_check_passed: `True`" in markdown


def _write_report(json_path: Path, markdown_path: Path) -> dict:
    candidate_grid = json.loads((FIXTURE_DIR / "candidate_grid_smoke.json").read_text(encoding="utf-8"))
    fixture = json.loads((FIXTURE_DIR / "synthetic_two_memory_cycles.json").read_text(encoding="utf-8"))
    return write_ai_capex_token_tuning_execution_validation_report(
        candidate_grid=candidate_grid,
        snapshots=fixture["snapshots"],
        json_path=json_path,
        markdown_path=markdown_path,
    )
