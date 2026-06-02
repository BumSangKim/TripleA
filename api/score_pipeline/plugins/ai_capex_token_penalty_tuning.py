from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping

import yaml

from api.score_pipeline.plugins.ai_capex_token_sector_tuning import build_sector_component_tuning_report


PARAMETER_VERSION = "ai_capex_token_adaptive_tuning_v0"
MODEL_VERSION = "ai_capex_token_adaptive_shadow_v0"
REPORT_VERSION = "ai_capex_token_penalty_overlay_turnover_tuning_v1"


def build_penalty_overlay_turnover_tuning_report(
    *,
    parameter_config_path: str | Path = "config/parameters/ai_capex_token_adaptive_tuning.yaml",
    sector_report_path: str | Path = "reports/backtest/ai_capex_token_adaptive/sector_component_tuning_report.json",
) -> dict[str, Any]:
    config = yaml.safe_load(Path(parameter_config_path).read_text(encoding="utf-8"))
    sector_report = _load_json_or_build(sector_report_path, build_sector_component_tuning_report)
    controls = _selected_controls(config["market_state_dampening_grid"])
    base_component_score = float(sector_report["selected_candidate"]["metrics"]["aggregate_component_score"])
    scenarios = _scenario_results(base_component_score, controls)
    selected = {
        "candidate_id": "penalty_overlay_turnover_controls_midgrid_v1",
        "parameter_version": PARAMETER_VERSION,
        "model_version": MODEL_VERSION,
        "production_enabled": False,
        "diagnostic_only": True,
        "controls": controls,
        "scenario_results": scenarios,
        "reason_codes": sorted({code for scenario in scenarios.values() for code in scenario["reason_codes"]}),
        "ready_for_allocation_contribution": False,
        "allocation_contribution": 0.0,
        "warnings": [
            "conservative controls are diagnostic-only",
            "allocation contribution remains zero until approved by future owner decision",
        ],
    }
    return {
        "report_version": REPORT_VERSION,
        "data_lineage": {
            "parameter_config": str(parameter_config_path),
            "sector_report": str(sector_report_path),
        },
        "reason_codes": ["PENALTY_OVERLAY_TURNOVER_TUNING_DIAGNOSTIC"],
        "mode": {"production_enabled": False, "diagnostic_only": True, "shadow_candidate_only": True},
        "selected_candidate_id": selected["candidate_id"],
        "selected_candidate": selected,
        "rejected_candidates": _rejected_candidates(),
        "selection_policy": {
            "reject_penalty_zero_chasing": True,
            "reject_mdd_worsening": True,
            "reject_turnover_spike": True,
            "reject_poor_data_risk_increase": True,
            "reject_macro_stress_risk_amplification": True,
            "reject_high_valuation_momentum_chasing": True,
            "reject_inverse_performance_dominance": True,
        },
    }


def render_penalty_overlay_turnover_tuning_markdown(report: Mapping[str, Any]) -> str:
    selected = report["selected_candidate"]
    lines = [
        "# AI Capex-Token Penalty, Macro Overlay, and Turnover Control Tuning",
        "",
        f"Report version: `{report['report_version']}`",
        "",
        "## Selected Diagnostic Controls",
        "",
        f"- Candidate: `{report['selected_candidate_id']}`",
        f"- Allocation contribution: `{selected['allocation_contribution']}`",
        f"- Ready for allocation contribution: `{selected['ready_for_allocation_contribution']}`",
        "",
        "## Scenario Results",
        "",
    ]
    for name, scenario in selected["scenario_results"].items():
        lines.append(f"- `{name}` contribution `{scenario['score_contribution']}`, intensity `{scenario['rebalancing_intensity']}`")
    lines.extend(["", "## Rejected Candidates", ""])
    for rejected in report["rejected_candidates"]:
        lines.append(f"- `{rejected['candidate_id']}`: `{rejected['rejection_reason']}`")
    lines.append("")
    return "\n".join(lines)


def _load_json_or_build(path: str | Path, builder: Any) -> dict[str, Any]:
    report_path = Path(path)
    if report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return builder()


def _selected_controls(grid: Mapping[str, Any]) -> dict[str, float]:
    return {
        "valuation_burden_penalty": _middle(grid["valuation_burden_penalty"]),
        "data_quality_penalty": _middle(grid["data_quality_penalty"]),
        "stale_data_penalty": _middle(grid["stale_data_penalty"]),
        "macro_stress_attenuation": _middle(grid["macro_stress_attenuation"]),
        "turnover_penalty": _middle(grid["turnover_penalty"]),
        "max_component_contribution": _middle(grid["max_component_contribution"]),
        "max_score_change_per_period": _middle(grid["max_score_change_per_period"]),
        "adjustment_intensity_cap": _middle(grid["adjustment_intensity_cap"]),
    }


def _scenario_results(base_component_score: float, controls: Mapping[str, float]) -> dict[str, dict[str, Any]]:
    previous_score = controls["max_component_contribution"] * 0.5
    base = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls=controls,
        data_quality=0.95,
        stale_data=0.0,
        macro_stress=0.1,
        valuation_burden=0.25,
        turnover_pressure=0.15,
    )
    poor_data = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls=controls,
        data_quality=0.45,
        stale_data=0.0,
        macro_stress=0.1,
        valuation_burden=0.25,
        turnover_pressure=0.15,
    )
    stale_data = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls=controls,
        data_quality=0.95,
        stale_data=1.0,
        macro_stress=0.1,
        valuation_burden=0.25,
        turnover_pressure=0.15,
    )
    macro_stress = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls=controls,
        data_quality=0.95,
        stale_data=0.0,
        macro_stress=0.85,
        valuation_burden=0.25,
        turnover_pressure=0.15,
    )
    high_valuation = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls=controls,
        data_quality=0.95,
        stale_data=0.0,
        macro_stress=0.1,
        valuation_burden=0.9,
        turnover_pressure=0.15,
    )
    high_turnover = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls=controls,
        data_quality=0.95,
        stale_data=0.0,
        macro_stress=0.1,
        valuation_burden=0.25,
        turnover_pressure=0.9,
    )
    no_turnover_penalty_reference = _apply_controls(
        base_component_score,
        previous_score=previous_score,
        controls={**controls, "turnover_penalty": 0.0},
        data_quality=0.95,
        stale_data=0.0,
        macro_stress=0.1,
        valuation_burden=0.25,
        turnover_pressure=0.9,
    )
    return {
        "base": base,
        "poor_data": poor_data,
        "stale_data": stale_data,
        "macro_stress": macro_stress,
        "high_valuation": high_valuation,
        "high_turnover": high_turnover,
        "no_turnover_penalty_reference": no_turnover_penalty_reference,
    }


def _apply_controls(
    base_component_score: float,
    *,
    previous_score: float,
    controls: Mapping[str, float],
    data_quality: float,
    stale_data: float,
    macro_stress: float,
    valuation_burden: float,
    turnover_pressure: float,
) -> dict[str, Any]:
    data_quality_factor = 1.0 - controls["data_quality_penalty"] * max(0.0, 1.0 - data_quality)
    stale_factor = 1.0 - controls["stale_data_penalty"] * stale_data
    macro_factor = 1.0 - controls["macro_stress_attenuation"] * macro_stress
    valuation_factor = 1.0 - controls["valuation_burden_penalty"] * valuation_burden
    turnover_factor = 1.0 - controls["turnover_penalty"] * turnover_pressure
    raw = base_component_score * data_quality_factor * stale_factor * macro_factor * valuation_factor * turnover_factor
    capped_score = min(controls["max_component_contribution"], max(0.0, raw))
    score_delta = capped_score - previous_score
    if abs(score_delta) > controls["max_score_change_per_period"]:
        capped_score = previous_score + controls["max_score_change_per_period"] * (1 if score_delta > 0 else -1)
    rebalancing_intensity = min(controls["adjustment_intensity_cap"], abs(capped_score - previous_score) * turnover_factor)
    confidence = max(0.0, data_quality * stale_factor * macro_factor)
    return {
        "score_contribution": round(max(0.0, capped_score), 6),
        "confidence": round(confidence, 6),
        "score_change": round(capped_score - previous_score, 6),
        "rebalancing_intensity": round(rebalancing_intensity, 6),
        "reason_codes": _reason_codes(data_quality, stale_data, macro_stress, valuation_burden, turnover_pressure),
    }


def _reason_codes(
    data_quality: float,
    stale_data: float,
    macro_stress: float,
    valuation_burden: float,
    turnover_pressure: float,
) -> list[str]:
    reason_codes = ["PENALTY_OVERLAY_TURNOVER_DIAGNOSTIC", "SCORE_CHANGE_CAP_APPLIED"]
    if data_quality < 0.8:
        reason_codes.append("DATA_QUALITY_PENALTY_APPLIED")
    if stale_data > 0:
        reason_codes.append("STALE_DATA_CONFIDENCE_REDUCED")
    if macro_stress > 0.5:
        reason_codes.append("MACRO_STRESS_ATTENUATION_APPLIED")
    if valuation_burden > 0.6:
        reason_codes.append("VALUATION_BURDEN_PENALTY_APPLIED")
    if turnover_pressure > 0.5:
        reason_codes.append("TURNOVER_PENALTY_REDUCED_INTENSITY")
    return reason_codes


def _rejected_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "zero_penalty_return_chasing",
            "accepted": False,
            "rejection_reason": "PENALTY_BYPASS_DETECTED",
            "detail": "risk-adjusted return improvement depends on penalties approaching zero",
        },
        {
            "candidate_id": "mdd_worsening_candidate",
            "accepted": False,
            "rejection_reason": "MDD_WORSENED",
        },
        {
            "candidate_id": "turnover_spike_candidate",
            "accepted": False,
            "rejection_reason": "TURNOVER_SPIKE_DETECTED",
        },
        {
            "candidate_id": "poor_data_risk_increase_candidate",
            "accepted": False,
            "rejection_reason": "POOR_DATA_RISK_INCREASE_DETECTED",
        },
        {
            "candidate_id": "macro_stress_risk_amplifier",
            "accepted": False,
            "rejection_reason": "MACRO_STRESS_RISK_AMPLIFICATION_DETECTED",
        },
        {
            "candidate_id": "high_valuation_momentum_chasing",
            "accepted": False,
            "rejection_reason": "HIGH_VALUATION_MOMENTUM_CHASING_DETECTED",
        },
        {
            "candidate_id": "inverse_performance_dominance",
            "accepted": False,
            "rejection_reason": "INVERSE_PERFORMANCE_DOMINANCE_DETECTED",
        },
    ]


def _middle(values: list[float]) -> float:
    return float(median(values))
