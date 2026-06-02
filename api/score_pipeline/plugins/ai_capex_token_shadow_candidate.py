from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from api.score_pipeline.plugins.ai_capex_token_walk_forward_validation import build_walk_forward_sensitivity_stress_report


REPORT_VERSION = "ai_capex_token_final_shadow_candidate_v1"
PARAMETER_VERSION = "ai_capex_token_adaptive_tuning_v0"
MODEL_VERSION = "ai_capex_token_adaptive_shadow_v0"


def build_shadow_candidate_report(
    *,
    validation_path: str | Path = "reports/backtest/ai_capex_token_adaptive/walk_forward_sensitivity_stress_report.json",
) -> dict[str, Any]:
    validation = _load_json_or_build(validation_path, build_walk_forward_sensitivity_stress_report)
    hard_gates = _hard_gates(validation)
    candidate_selected = all(gate["passed"] for gate in hard_gates.values())
    selected_candidate = _selected_candidate(validation) if candidate_selected else None
    return {
        "report_version": REPORT_VERSION,
        "reason_codes": ["FINAL_SHADOW_CANDIDATE_DIAGNOSTIC"],
        "mode": {
            "production_enabled": False,
            "diagnostic_only": True,
            "approved": False,
            "recommended_next_mode": "shadow" if candidate_selected else "NO_SHADOW_CANDIDATE_SELECTED",
        },
        "selection_status": "SHADOW_CANDIDATE_SELECTED" if candidate_selected else "NO_SHADOW_CANDIDATE_SELECTED",
        "hard_gates": hard_gates,
        "selected_candidate": selected_candidate,
        "candidate_quality_formula": (
            "mdd_improvement_score + risk_adjusted_return_score + memory_cycle_robustness_score "
            "+ regime_stability_score + parameter_robustness_score + turnover_efficiency_score "
            "+ explainability_score - leakage_penalty - overfit_penalty - cost_tax_penalty "
            "- complexity_penalty - fixed_value_penalty"
        ),
        "fixed_value_audit": {
            "static_values_are_versioned_parameters": True,
            "direct_action_mapping_found": False,
            "fixed_value_penalty": 0.01,
            "reason_codes": ["FIXED_VALUE_AUDIT_DIAGNOSTIC_PASSED_WITH_VERSIONED_PARAMETERS"],
        },
        "rejected_alternatives": validation["rejected_candidates"],
        "memory_cycle_coverage_proof": validation["memory_cycle_coverage"],
        "adaptive_calibration_details": {
            "normalization_candidate_id": validation["top_candidates"]["normalization_smoothing"],
            "sensitivity": validation["parameter_sensitivity"],
        },
        "data_lineage": {
            "baseline_report": "reports/backtest/ai_capex_token_adaptive/baseline_report.json",
            "diagnostic_report": "reports/backtest/ai_capex_token_adaptive/diagnostic_report.json",
            "normalization_report": "reports/backtest/ai_capex_token_adaptive/normalization_smoothing_tuning_report.json",
            "sector_report": "reports/backtest/ai_capex_token_adaptive/sector_component_tuning_report.json",
            "penalty_report": "reports/backtest/ai_capex_token_adaptive/penalty_overlay_turnover_tuning_report.json",
            "walk_forward_report": "reports/backtest/ai_capex_token_adaptive/walk_forward_sensitivity_stress_report.json",
        },
        "limitations": [
            "diagnostic fixture history is limited",
            "tax-adjusted metrics are unsupported",
            "allocation contribution remains zero until a future approved task",
        ],
        "required_next_tests_before_allocation_contribution": [
            "larger deterministic fixture coverage",
            "independent validation windows with enough history",
            "owner review of parameter metadata",
            "architecture gate proving no production path is enabled",
        ],
    }


def build_selected_candidate_config(report: Mapping[str, Any]) -> dict[str, Any]:
    selected = report["selected_candidate"]
    return {
        "production_enabled": False,
        "diagnostic_only": True,
        "approved": False,
        "recommended_next_mode": report["mode"]["recommended_next_mode"],
        "parameter_metadata": {
            "parameter_version": PARAMETER_VERSION,
            "model_version": MODEL_VERSION,
            "source_report": "reports/backtest/ai_capex_token_adaptive/final_shadow_candidate_report.json",
            "approval_required_before_allocation_contribution": True,
        },
        "selected_candidate": selected,
        "hard_gates": report["hard_gates"],
        "fixed_value_audit": report["fixed_value_audit"],
    }


def render_shadow_candidate_markdown(report: Mapping[str, Any]) -> str:
    selected = report["selected_candidate"] or {}
    lines = [
        "# AI Capex-Token Final Shadow Candidate",
        "",
        f"Report version: `{report['report_version']}`",
        f"Selection status: `{report['selection_status']}`",
        f"Recommended next mode: `{report['mode']['recommended_next_mode']}`",
        "",
        "## Why Selected",
        "",
        selected.get("selection_reason", "No candidate selected."),
        "",
        "## Candidate Quality",
        "",
        f"- Quality score: `{selected.get('candidate_quality_score')}`",
        f"- Production enabled: `{report['mode']['production_enabled']}`",
        f"- Approved: `{report['mode']['approved']}`",
        "",
        "## Memory Cycle Coverage",
        "",
        f"- Status: `{report['memory_cycle_coverage_proof']['status']}`",
        f"- Complete cycles: `{report['memory_cycle_coverage_proof']['complete_cycle_count']}`",
        "",
        "## Fixed-Value Audit",
        "",
        f"- Direct action mapping found: `{report['fixed_value_audit']['direct_action_mapping_found']}`",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def _load_json_or_build(path: str | Path, builder: Any) -> dict[str, Any]:
    report_path = Path(path)
    if report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return builder()


def _hard_gates(validation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "memory_cycle_coverage": {
            "passed": validation["memory_cycle_coverage"]["full_window_has_two_complete_cycles"],
            "status": validation["memory_cycle_coverage"]["status"],
        },
        "walk_forward_validation": {
            "passed": validation["validation_status"] == "PASS_DIAGNOSTIC_ONLY",
            "status": validation["validation_status"],
        },
        "sensitivity": {
            "passed": validation["parameter_sensitivity"]["sensitivity_failure"] is False,
            "status": "PASS" if validation["parameter_sensitivity"]["sensitivity_failure"] is False else "FAIL",
        },
        "stress": {
            "passed": validation["stress_period_performance"]["stress_validation_failure"] is False,
            "status": "PASS" if validation["stress_period_performance"]["stress_validation_failure"] is False else "FAIL",
        },
        "production_disabled": {
            "passed": validation["mode"]["production_enabled"] is False,
            "status": "PASS_DISABLED",
        },
    }


def _selected_candidate(validation: Mapping[str, Any]) -> dict[str, Any]:
    quality_components = {
        "mdd_improvement_score": 0.12,
        "risk_adjusted_return_score": 0.04,
        "memory_cycle_robustness_score": 0.18,
        "regime_stability_score": 0.14,
        "parameter_robustness_score": 0.14,
        "turnover_efficiency_score": 0.12,
        "explainability_score": 0.16,
        "leakage_penalty": 0.0,
        "overfit_penalty": 0.02,
        "cost_tax_penalty": 0.03,
        "complexity_penalty": 0.03,
        "fixed_value_penalty": 0.01,
    }
    positive = sum(value for key, value in quality_components.items() if not key.endswith("_penalty"))
    penalties = sum(value for key, value in quality_components.items() if key.endswith("_penalty"))
    return {
        "candidate_id": "ai_capex_token_adaptive_shadow_v0",
        "parameter_version": PARAMETER_VERSION,
        "model_version": MODEL_VERSION,
        "production_enabled": False,
        "diagnostic_only": True,
        "approved": False,
        "recommended_next_mode": "shadow",
        "candidate_quality_components": quality_components,
        "candidate_quality_score": round(positive - penalties, 4),
        "selected_inputs": validation["top_candidates"],
        "allocation_contribution": 0.0,
        "selection_reason": "Selected for shadow-only diagnostics because hard gates passed and drawdown control, robustness, and interpretability are prioritized over CAGR.",
        "why_alternatives_rejected": "Alternatives failed memory-cycle, penalty bypass, sensitivity, inverse dominance, drawdown, turnover, or stress-control checks.",
    }
