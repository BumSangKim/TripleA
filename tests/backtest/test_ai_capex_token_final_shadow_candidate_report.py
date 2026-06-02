from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from api.score_pipeline.plugins.ai_capex_token_shadow_candidate import (
    build_selected_candidate_config,
    build_shadow_candidate_report,
    render_shadow_candidate_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
JSON_REPORT = REPORT_DIR / "final_shadow_candidate_report.json"
MD_REPORT = REPORT_DIR / "final_shadow_candidate_report.md"
SELECTED_CONFIG = Path("config/parameters/ai_capex_token_adaptive_selected_candidate.yaml")
FORBIDDEN_KEYS = {"order", "orders", "execution", "broker", "target_weight", "place_order", "submit_order"}


def test_final_shadow_candidate_report_and_config_match_builders():
    assert JSON_REPORT.exists()
    assert MD_REPORT.exists()
    assert SELECTED_CONFIG.exists()

    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    built = build_shadow_candidate_report()
    config = yaml.safe_load(SELECTED_CONFIG.read_text(encoding="utf-8"))

    assert report == built
    assert MD_REPORT.read_text(encoding="utf-8") == render_shadow_candidate_markdown(built)
    assert config == build_selected_candidate_config(built)


def test_candidate_selected_only_when_all_hard_gates_pass():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["selection_status"] == "SHADOW_CANDIDATE_SELECTED"
    assert all(gate["passed"] is True for gate in report["hard_gates"].values())
    assert report["selected_candidate"] is not None
    assert report["selected_candidate"]["candidate_quality_score"] > 0


def test_production_disabled_approved_false_and_next_mode_shadow():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    config = yaml.safe_load(SELECTED_CONFIG.read_text(encoding="utf-8"))

    for payload in (report["mode"], config):
        assert payload["production_enabled"] is False
        assert payload["diagnostic_only"] is True
        assert payload["approved"] is False
        assert payload["recommended_next_mode"] == "shadow"
    assert config["parameter_metadata"]["approval_required_before_allocation_contribution"] is True


def test_no_forbidden_order_execution_fields_are_present():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    config = yaml.safe_load(SELECTED_CONFIG.read_text(encoding="utf-8"))

    assert not _forbidden_keys(report)
    assert not _forbidden_keys(config)


def test_fixed_value_audit_and_rejected_reasons_are_present():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["fixed_value_audit"]["static_values_are_versioned_parameters"] is True
    assert report["fixed_value_audit"]["direct_action_mapping_found"] is False
    assert "FIXED_VALUE_AUDIT_DIAGNOSTIC_PASSED_WITH_VERSIONED_PARAMETERS" in report["fixed_value_audit"]["reason_codes"]
    reasons = {item.get("rejection_reason") or item.get("gates", {}).get("rejection_reason") for item in report["rejected_alternatives"]}
    assert "INSUFFICIENT_MEMORY_CYCLE_COVERAGE" in reasons
    assert "PENALTY_BYPASS_DETECTED" in reasons
    assert "INVERSE_DOMINANCE_DETECTED" in reasons


def test_report_contains_required_context_sections():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["memory_cycle_coverage_proof"]["complete_cycle_count"] >= 2
    assert report["adaptive_calibration_details"]["normalization_candidate_id"]
    assert report["data_lineage"]
    assert report["limitations"]
    assert report["required_next_tests_before_allocation_contribution"]


def _forbidden_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in FORBIDDEN_KEYS:
                found.append(str(key))
            found.extend(_forbidden_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_forbidden_keys(item))
    return found
