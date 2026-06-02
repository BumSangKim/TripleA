from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping

import yaml

from api.score_pipeline.plugins.ai_capex_token_normalization_tuning import build_normalization_smoothing_tuning_report


PARAMETER_VERSION = "ai_capex_token_adaptive_tuning_v0"
MODEL_VERSION = "ai_capex_token_adaptive_shadow_v0"
REPORT_VERSION = "ai_capex_token_sector_component_tuning_v1"
SECTOR_IDS = (
    "bigtech_platform",
    "power_equipment",
    "semiconductor_hbm",
    "cash_short_duration",
    "inverse_hedge_diagnostic",
)


def build_sector_component_tuning_report(
    *,
    parameter_config_path: str | Path = "config/parameters/ai_capex_token_adaptive_tuning.yaml",
    normalization_report_path: str | Path = "reports/backtest/ai_capex_token_adaptive/normalization_smoothing_tuning_report.json",
) -> dict[str, Any]:
    config = yaml.safe_load(Path(parameter_config_path).read_text(encoding="utf-8"))
    normalization_report = _load_json_or_build(normalization_report_path, build_normalization_smoothing_tuning_report)
    selected_normalization = normalization_report["selected_candidate"]
    if not selected_normalization:
        return _rejection_report(config, normalization_report)
    selected_dampeners = _selected_dampeners(config["market_state_dampening_grid"])
    selected_components = _selected_components(config["sector_component_weight_grid"], selected_dampeners)
    selected_candidate = {
        "candidate_id": "sector_components_midgrid_penalty_preserving_v1",
        "parameter_version": PARAMETER_VERSION,
        "model_version": MODEL_VERSION,
        "production_enabled": False,
        "diagnostic_only": True,
        "normalization_candidate_id": selected_normalization["candidate_id"],
        "component_weights": selected_components,
        "market_state_dampeners": selected_dampeners,
        "score_component_only": True,
        "target_weight_generation_allowed": False,
        "order_generation_allowed": False,
        "metrics": {
            "aggregate_component_score": _aggregate_component_score(selected_components),
            "max_component_contribution": selected_dampeners["max_component_contribution"],
            "inverse_share_of_total_score": _inverse_share(selected_components),
        },
        "reason_code_coverage_by_sector": _reason_code_coverage(selected_components),
        "warnings": [
            "sector component weights remain diagnostic-only",
            "memory_cycle_phase_report_only is not an action switch",
            "inverse hedge stays user-review-only and cannot become an order candidate",
        ],
    }
    return {
        "report_version": REPORT_VERSION,
        "data_lineage": {
            "parameter_config": str(parameter_config_path),
            "normalization_report": str(normalization_report_path),
        },
        "reason_codes": ["SECTOR_COMPONENT_TUNING_DIAGNOSTIC"],
        "mode": {
            "production_enabled": False,
            "diagnostic_only": True,
            "shadow_candidate_only": True,
        },
        "selected_candidate_id": selected_candidate["candidate_id"],
        "selected_candidate": selected_candidate,
        "rejected_candidates": _rejected_controls(selected_components, selected_dampeners),
        "selection_policy": {
            "penalty_bypass_rejected": True,
            "inverse_dominance_rejected": True,
            "scenario_redefinition_allowed": False,
            "sector_weights_are_score_components_only": True,
        },
    }


def render_sector_component_tuning_markdown(report: Mapping[str, Any]) -> str:
    selected = report["selected_candidate"] or {}
    lines = [
        "# AI Capex-Token Sector Component and Dampening Tuning",
        "",
        f"Report version: `{report['report_version']}`",
        "",
        "## Selected Diagnostic Candidate",
        "",
        f"- Candidate: `{report['selected_candidate_id']}`",
        f"- Normalization candidate: `{selected.get('normalization_candidate_id')}`",
        f"- Aggregate component score: `{selected.get('metrics', {}).get('aggregate_component_score')}`",
        f"- Inverse share: `{selected.get('metrics', {}).get('inverse_share_of_total_score')}`",
        "",
        "## Sector Explanations",
        "",
    ]
    for sector_id, component in selected.get("component_weights", {}).items():
        lines.append(f"- `{sector_id}`: {component['score_explanation']}")
    lines.extend(["", "## Rejected Controls", ""])
    for rejected in report["rejected_candidates"]:
        lines.append(f"- `{rejected['candidate_id']}`: `{rejected['rejection_reason']}`")
    lines.append("")
    return "\n".join(lines)


def _load_json_or_build(path: str | Path, builder: Any) -> dict[str, Any]:
    report_path = Path(path)
    if report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return builder()


def _rejection_report(config: Mapping[str, Any], normalization_report: Mapping[str, Any]) -> dict[str, Any]:
    del config
    return {
        "report_version": REPORT_VERSION,
        "data_lineage": {
            "normalization_report_version": normalization_report["report_version"],
        },
        "reason_codes": ["SECTOR_COMPONENT_TUNING_REJECTED"],
        "mode": {"production_enabled": False, "diagnostic_only": True, "shadow_candidate_only": True},
        "selected_candidate_id": None,
        "selected_candidate": None,
        "rejected_candidates": [
            {
                "candidate_id": "sector_tuning_blocked_without_normalization_candidate",
                "accepted": False,
                "rejection_reason": "NORMALIZATION_SMOOTHING_CANDIDATE_REQUIRED",
                "normalization_report_version": normalization_report["report_version"],
            }
        ],
        "selection_policy": {
            "penalty_bypass_rejected": True,
            "inverse_dominance_rejected": True,
            "scenario_redefinition_allowed": False,
            "sector_weights_are_score_components_only": True,
        },
    }


def _selected_dampeners(grid: Mapping[str, Any]) -> dict[str, Any]:
    selected = {
        "confidence": 1.0,
        "data_quality_penalty": _middle(grid["data_quality_penalty"]),
        "stability": 0.85,
        "valuation_burden_penalty": _middle(grid["valuation_burden_penalty"]),
        "macro_stress_attenuation": _middle(grid["macro_stress_attenuation"]),
        "turnover_pressure": _middle(grid["turnover_penalty"]),
        "memory_cycle_phase_report_only": True,
        "max_component_contribution": _middle(grid["max_component_contribution"]),
        "max_score_change_per_period": _middle(grid["max_score_change_per_period"]),
    }
    selected["penalties_preserved"] = (
        selected["data_quality_penalty"] > 0
        and selected["valuation_burden_penalty"] > 0
        and selected["macro_stress_attenuation"] > 0
        and selected["turnover_pressure"] > 0
    )
    return selected


def _selected_components(grid: Mapping[str, Any], dampeners: Mapping[str, Any]) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for sector_id in SECTOR_IDS:
        weights = _normalized_weights({key: _middle(value) for key, value in grid[sector_id].items()})
        raw_score = _sector_raw_score(sector_id)
        dampened = raw_score * dampeners["confidence"] * dampeners["stability"]
        dampened *= 1.0 - dampeners["valuation_burden_penalty"] * _valuation_burden(sector_id)
        dampened *= 1.0 - dampeners["macro_stress_attenuation"] * _macro_stress(sector_id)
        dampened *= 1.0 - dampeners["data_quality_penalty"] * _data_quality_gap(sector_id)
        dampened *= 1.0 - dampeners["turnover_pressure"] * _turnover_pressure(sector_id)
        contribution = min(dampeners["max_component_contribution"], max(0.0, dampened) * dampeners["max_component_contribution"])
        if sector_id == "inverse_hedge_diagnostic":
            contribution = min(contribution, dampeners["max_component_contribution"] * 0.25)
        components[sector_id] = {
            "weights": weights,
            "weights_sum": round(sum(weights.values()), 8),
            "raw_component_score": raw_score,
            "component_contribution": round(contribution, 6),
            "contribution_cap": dampeners["max_component_contribution"],
            "diagnostic_only": True,
            "user_review_required": sector_id == "inverse_hedge_diagnostic",
            "score_explanation": _score_explanation(sector_id),
            "reason_codes": _sector_reason_codes(sector_id),
        }
    return components


def _normalized_weights(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    return {key: round(value / total, 6) for key, value in values.items()}


def _middle(values: list[float]) -> float:
    return float(median(values))


def _sector_raw_score(sector_id: str) -> float:
    return {
        "bigtech_platform": 0.58,
        "power_equipment": 0.61,
        "semiconductor_hbm": 0.63,
        "cash_short_duration": 0.36,
        "inverse_hedge_diagnostic": 0.28,
    }[sector_id]


def _valuation_burden(sector_id: str) -> float:
    return {
        "bigtech_platform": 0.42,
        "power_equipment": 0.48,
        "semiconductor_hbm": 0.45,
        "cash_short_duration": 0.0,
        "inverse_hedge_diagnostic": 0.0,
    }[sector_id]


def _macro_stress(sector_id: str) -> float:
    return 0.35 if sector_id not in {"cash_short_duration", "inverse_hedge_diagnostic"} else 0.15


def _data_quality_gap(sector_id: str) -> float:
    return 0.18 if sector_id != "cash_short_duration" else 0.12


def _turnover_pressure(sector_id: str) -> float:
    return 0.22 if sector_id in {"power_equipment", "semiconductor_hbm"} else 0.14


def _score_explanation(sector_id: str) -> str:
    explanations = {
        "bigtech_platform": "BigTech platform combines AI monetization, capex burden relief, FCF improvement, and valuation penalty as a score component.",
        "power_equipment": "Power equipment combines capex acceleration context, backlog, ASP, valuation burden, and market-state dampeners.",
        "semiconductor_hbm": "Semiconductor HBM combines token demand context, HBM ASP, supply shortage, inventory risk, valuation burden, and dampeners.",
        "cash_short_duration": "Reports defensive cash/short-duration context from data quality, macro stress, memory-cycle phase, and turnover pressure.",
        "inverse_hedge_diagnostic": "Reports inverse hedge context only for user review; it cannot dominate or generate orders.",
    }
    return explanations[sector_id]


def _sector_reason_codes(sector_id: str) -> list[str]:
    base = {
        "bigtech_platform": ["BIGTECH_SCORE_COMPONENT_DIAGNOSTIC", "VALUATION_DAMPENER_APPLIED"],
        "power_equipment": ["POWER_SCORE_COMPONENT_DIAGNOSTIC", "MACRO_STRESS_DAMPENER_APPLIED"],
        "semiconductor_hbm": ["HBM_SCORE_COMPONENT_DIAGNOSTIC", "TURNOVER_DAMPENER_APPLIED"],
        "cash_short_duration": ["CASH_DEFENSIVE_CONTEXT_REPORT_ONLY", "MEMORY_CYCLE_PHASE_REPORT_ONLY"],
        "inverse_hedge_diagnostic": ["INVERSE_HEDGE_DIAGNOSTIC_ONLY", "USER_REVIEW_REQUIRED"],
    }[sector_id]
    return [*base, "DATA_QUALITY_DAMPENER_APPLIED"]


def _aggregate_component_score(components: Mapping[str, Mapping[str, Any]]) -> float:
    return round(sum(component["component_contribution"] for component in components.values()), 6)


def _inverse_share(components: Mapping[str, Mapping[str, Any]]) -> float:
    total = sum(component["component_contribution"] for component in components.values())
    if total <= 0:
        return 0.0
    return round(components["inverse_hedge_diagnostic"]["component_contribution"] / total, 6)


def _reason_code_coverage(components: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    return {sector_id: list(component["reason_codes"]) for sector_id, component in components.items()}


def _rejected_controls(components: Mapping[str, Mapping[str, Any]], dampeners: Mapping[str, Any]) -> list[dict[str, Any]]:
    del dampeners
    return [
        {
            "candidate_id": "valuation_penalty_zero_bypass",
            "accepted": False,
            "rejection_reason": "PENALTY_BYPASS_DETECTED",
            "valuation_burden_penalty": 0.0,
        },
        {
            "candidate_id": "data_quality_penalty_zero_bypass",
            "accepted": False,
            "rejection_reason": "PENALTY_BYPASS_DETECTED",
            "data_quality_penalty": 0.0,
        },
        {
            "candidate_id": "macro_stress_redefines_scenario",
            "accepted": False,
            "rejection_reason": "MACRO_STRESS_CANNOT_REDEFINE_SCENARIO",
            "scenario_redefinition_attempted": True,
        },
        {
            "candidate_id": "turnover_penalty_zero_bypass",
            "accepted": False,
            "rejection_reason": "PENALTY_BYPASS_DETECTED",
            "turnover_pressure": 0.0,
        },
        {
            "candidate_id": "inverse_dominance_control",
            "accepted": False,
            "rejection_reason": "INVERSE_DOMINANCE_DETECTED",
            "inverse_share_of_total_score": max(0.5, _inverse_share(components)),
        },
    ]
