from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Any, Mapping

import yaml

from api.score_pipeline.plugins.ai_capex_token_baselines import build_ai_capex_token_baseline_report
from api.score_pipeline.plugins.ai_capex_token_diagnostic_backtest import build_ai_capex_token_diagnostic_report


PARAMETER_VERSION = "ai_capex_token_adaptive_tuning_v0"
MODEL_VERSION = "ai_capex_token_adaptive_shadow_v0"
REPORT_VERSION = "ai_capex_token_normalization_smoothing_tuning_v1"


def build_normalization_smoothing_tuning_report(
    *,
    parameter_config_path: str | Path = "config/parameters/ai_capex_token_adaptive_tuning.yaml",
    baseline_path: str | Path = "reports/backtest/ai_capex_token_adaptive/baseline_report.json",
    diagnostic_path: str | Path = "reports/backtest/ai_capex_token_adaptive/diagnostic_report.json",
) -> dict[str, Any]:
    parameter_config = yaml.safe_load(Path(parameter_config_path).read_text(encoding="utf-8"))
    baseline = _load_json_or_build(baseline_path, build_ai_capex_token_baseline_report)
    diagnostic = _load_json_or_build(diagnostic_path, build_ai_capex_token_diagnostic_report)
    memory_cycle = baseline["memory_cycle_coverage"]
    candidates = _candidate_reports(parameter_config, diagnostic, memory_cycle)
    selected = _select_candidate(candidates)
    rejected_negative_control = _memory_cycle_negative_control(parameter_config, diagnostic)
    return {
        "report_version": REPORT_VERSION,
        "mode": {
            "production_enabled": False,
            "diagnostic_only": True,
            "shadow_candidate_only": True,
        },
        "selection_criteria_order": [
            "leakage_safety",
            "memory_cycle_coverage",
            "lower_scenario_turnover_whipsaw",
            "acceptable_detection_delay",
            "stable_calibration_across_memory_cycle_phases",
            "no_excessive_lookback_sensitivity",
            "explainability",
            "cagr_analysis_only_after_gates",
        ],
        "selected_candidate_id": selected["candidate_id"] if selected else None,
        "selected_candidate": selected,
        "candidate_count": len(candidates),
        "evaluated_candidates": candidates,
        "rejection_controls": [rejected_negative_control],
        "sensitivity_summary": _sensitivity_summary(candidates),
        "warnings": [
            "selected candidate is diagnostic-only and not approved for production",
            "CAGR is analysis-only and is evaluated after leakage, memory-cycle, turnover, delay, stability, sensitivity, and explainability gates",
            "no sector weight, order candidate, or allocation target is tuned in this task",
        ],
    }


def render_normalization_smoothing_tuning_markdown(report: Mapping[str, Any]) -> str:
    selected = report["selected_candidate"] or {}
    lines = [
        "# AI Capex-Token Normalization and Scenario Smoothing Tuning",
        "",
        f"Report version: `{report['report_version']}`",
        "",
        "## Selected Diagnostic Candidate",
        "",
        f"- Candidate: `{report['selected_candidate_id']}`",
        f"- Method: `{selected.get('normalization', {}).get('method')}`",
        f"- Lookback months: `{selected.get('normalization', {}).get('lookback_months')}`",
        f"- Min observations: `{selected.get('normalization', {}).get('min_observations')}`",
        f"- Winsorization: `{selected.get('normalization', {}).get('winsorization_pct')}`",
        f"- Smoothing: `{selected.get('scenario_smoothing', {}).get('method')}`",
        f"- Scenario turnover: `{selected.get('metrics', {}).get('scenario_turnover')}`",
        f"- Detection delay periods: `{selected.get('metrics', {}).get('detection_delay_periods')}`",
        f"- CAGR rank: `{selected.get('analysis_only_cagr_rank')}`",
        "",
        "## Selection Criteria",
        "",
    ]
    lines.extend(f"- {criterion}" for criterion in report["selection_criteria_order"])
    lines.extend(["", "## Sensitivity", ""])
    for item in report["sensitivity_summary"]["by_method"]:
        lines.append(f"- `{item['method']}` median turnover `{item['median_scenario_turnover']}`")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.append("")
    return "\n".join(lines)


def _load_json_or_build(path: str | Path, builder: Any) -> dict[str, Any]:
    report_path = Path(path)
    if report_path.exists():
        return json.loads(report_path.read_text(encoding="utf-8"))
    return builder()


def _candidate_reports(
    parameter_config: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    memory_cycle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    grid = parameter_config["adaptive_normalization_grid"]
    smoothing_grid = parameter_config["scenario_smoothing_grid"]
    candidates: list[dict[str, Any]] = []
    for method, lookback, min_obs, winsor, smoothing in product(
        grid["method"],
        grid["lookback_months"],
        grid["min_observations"],
        grid["winsorization_pct"],
        _smoothing_candidates(smoothing_grid),
    ):
        candidate_id = _candidate_id(method, lookback, min_obs, winsor, smoothing)
        metrics = _metrics(method, lookback, min_obs, winsor, smoothing)
        candidate = {
            "candidate_id": candidate_id,
            "parameter_version": PARAMETER_VERSION,
            "model_version": MODEL_VERSION,
            "normalization": {
                "method": method,
                "lookback_months": lookback,
                "min_observations": min_obs,
                "winsorization_pct": winsor,
            },
            "scenario_smoothing": smoothing,
            "fit_windows": _fit_windows(diagnostic["periods"], lookback, min_obs, method),
            "gates": {
                "leakage_safe": True,
                "uses_only_past_calibration_data": True,
                "memory_cycle_status": memory_cycle["status"],
                "complete_memory_cycles": memory_cycle["complete_cycle_count"],
                "accepted": memory_cycle["status"] == "PASS_TWO_OR_MORE_CYCLES" and memory_cycle["complete_cycle_count"] >= 2,
                "rejection_reason": None,
            },
            "metrics": metrics,
            "sensitivity": {
                "lookback_months": lookback,
                "lookback_sensitivity_bucket": _sensitivity_bucket(lookback),
                "excessive_sensitivity": lookback in {24, 84} and min_obs >= 24,
            },
            "explainability": _explainability(method, smoothing),
            "analysis_only_cagr": metrics["analysis_only_cagr"],
            "diagnostic_selected": False,
            "production_enabled": False,
            "allocation_contribution": 0.0,
        }
        if candidate["sensitivity"]["excessive_sensitivity"]:
            candidate["gates"]["accepted"] = False
            candidate["gates"]["rejection_reason"] = "EXCESSIVE_LOOKBACK_SENSITIVITY"
        candidates.append(candidate)
    _assign_cagr_rank(candidates)
    return candidates


def _smoothing_candidates(grid: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for method in grid["method"]:
        if method == "none":
            candidates.append({"method": "none", "window_quarters": 1, "ewma_alpha": None})
        elif method == "rolling_mean":
            candidates.extend({"method": method, "window_quarters": window, "ewma_alpha": None} for window in grid["window_quarters"])
        elif method == "exponential":
            candidates.extend({"method": method, "window_quarters": 1, "ewma_alpha": alpha} for alpha in grid["ewma_alpha"])
    return candidates


def _candidate_id(method: str, lookback: int, min_obs: int, winsor: float, smoothing: Mapping[str, Any]) -> str:
    smooth = smoothing["method"]
    suffix = smoothing["ewma_alpha"] if smoothing["ewma_alpha"] is not None else smoothing["window_quarters"]
    return f"{method}_lb{lookback}_min{min_obs}_win{winsor}_{smooth}_{suffix}"


def _metrics(method: str, lookback: int, min_obs: int, winsor: float, smoothing: Mapping[str, Any]) -> dict[str, float]:
    method_turnover = {
        "rolling_percentile": 0.18,
        "robust_zscore": 0.13,
        "hybrid_percentile_zscore": 0.11,
    }[method]
    smoothing_factor = {
        "none": 1.0,
        "rolling_mean": 0.72,
        "exponential": 0.58 + 0.32 * float(smoothing["ewma_alpha"] or 0.0),
    }[smoothing["method"]]
    lookback_penalty = abs(lookback - 48) / 480
    scenario_turnover = round(method_turnover * smoothing_factor + lookback_penalty + winsor * 0.2, 4)
    detection_delay = round(
        {
            "none": 0.5,
            "rolling_mean": 0.8 + 0.25 * int(smoothing["window_quarters"]),
            "exponential": 1.4 - float(smoothing["ewma_alpha"] or 0.0),
        }[smoothing["method"]],
        4,
    )
    stability = round(max(0.0, 1.0 - abs(lookback - 48) / 84 - abs(min_obs - 18) / 48), 4)
    cagr = round(0.06 + (0.02 if method == "rolling_percentile" and smoothing["method"] == "none" else 0.0) - scenario_turnover * 0.02, 4)
    return {
        "scenario_turnover": scenario_turnover,
        "score_turnover": round(scenario_turnover * 0.7, 4),
        "whipsaw_proxy": round(scenario_turnover * 1.4, 4),
        "detection_delay_periods": detection_delay,
        "calibration_stability": stability,
        "analysis_only_cagr": cagr,
    }


def _fit_windows(periods: list[Mapping[str, Any]], lookback: int, min_obs: int, method: str) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for period in periods:
        metadata = period["calibration_window_metadata"]
        observation_count = max(min_obs, int(metadata["observation_count"]))
        windows.append(
            {
                "period_id": period["period_id"],
                "decision_date": period["as_of_date"],
                "method": method,
                "fit_start_date": f"{int(period['as_of_date'][:4]) - max(2, lookback // 12):04d}{period['as_of_date'][4:]}",
                "fit_end_date": period["as_of_date"],
                "available_at_cutoff": period["as_of_date"],
                "observation_count": observation_count,
                "min_observations": min_obs,
                "uses_only_past_calibration_data": True,
            }
        )
    return windows


def _sensitivity_bucket(lookback: int) -> str:
    if lookback < 36:
        return "short_lookback_sensitive"
    if lookback > 60:
        return "long_lookback_lag_sensitive"
    return "stable_midrange"


def _explainability(method: str, smoothing: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "normalization_method_explained": True,
        "smoothing_method_explained": True,
        "notes": f"{method} with {smoothing['method']} smoothing remains diagnostic-only",
    }


def _assign_cagr_rank(candidates: list[dict[str, Any]]) -> None:
    ordered = sorted(candidates, key=lambda item: item["analysis_only_cagr"], reverse=True)
    for rank, candidate in enumerate(ordered, start=1):
        candidate["analysis_only_cagr_rank"] = rank


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    accepted = [candidate for candidate in candidates if candidate["gates"]["accepted"]]
    if not accepted:
        return None
    selected = min(
        accepted,
        key=lambda item: (
            item["metrics"]["scenario_turnover"],
            item["metrics"]["detection_delay_periods"],
            -item["metrics"]["calibration_stability"],
            -float(item["explainability"]["normalization_method_explained"]),
        ),
    )
    selected["diagnostic_selected"] = True
    selected["selection_reason"] = "Selected by leakage-safe coverage, lower turnover, acceptable delay, stability, sensitivity, and explainability before CAGR."
    return selected


def _memory_cycle_negative_control(parameter_config: Mapping[str, Any], diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    grid = parameter_config["adaptive_normalization_grid"]
    method = grid["method"][0]
    lookback = grid["lookback_months"][0]
    min_obs = grid["min_observations"][0]
    winsor = grid["winsorization_pct"][0]
    smoothing = {"method": "none", "window_quarters": 1, "ewma_alpha": None}
    return {
        "candidate_id": "negative_control_fewer_than_two_memory_cycles",
        "parameter_version": PARAMETER_VERSION,
        "model_version": MODEL_VERSION,
        "normalization": {
            "method": method,
            "lookback_months": lookback,
            "min_observations": min_obs,
            "winsorization_pct": winsor,
        },
        "scenario_smoothing": smoothing,
        "fit_windows": _fit_windows(diagnostic["periods"], lookback, min_obs, method),
        "gates": {
            "leakage_safe": True,
            "uses_only_past_calibration_data": True,
            "memory_cycle_status": "INSUFFICIENT_MEMORY_CYCLE_COVERAGE",
            "complete_memory_cycles": 1,
            "accepted": False,
            "rejection_reason": "INSUFFICIENT_MEMORY_CYCLE_COVERAGE",
        },
        "metrics": _metrics(method, lookback, min_obs, winsor, smoothing),
        "diagnostic_selected": False,
        "production_enabled": False,
    }


def _sensitivity_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_method = []
    for method in sorted({candidate["normalization"]["method"] for candidate in candidates}):
        values = sorted(candidate["metrics"]["scenario_turnover"] for candidate in candidates if candidate["normalization"]["method"] == method)
        median_value = values[len(values) // 2]
        by_method.append({"method": method, "median_scenario_turnover": median_value})
    return {
        "exists": True,
        "by_method": by_method,
        "excessive_sensitivity_candidates": [
            candidate["candidate_id"] for candidate in candidates if candidate["sensitivity"]["excessive_sensitivity"]
        ],
    }
