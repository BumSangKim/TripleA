from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.score_pipeline.plugins.ai_capex_token_baselines import build_ai_capex_token_baseline_report


PERIODS = (
    {
        "period_id": "2026-02-s1",
        "as_of_date": "2026-02-10",
        "token_delta_normalized": 0.86,
        "capex_acceleration_normalized": 0.82,
        "dominant_scenario": "S1",
        "memory_cycle_phase": "recovery",
        "data_quality": 0.95,
        "future_sector_return": 0.03,
        "future_drawdown": -0.01,
    },
    {
        "period_id": "2026-03-s3",
        "as_of_date": "2026-03-10",
        "token_delta_normalized": 0.84,
        "capex_acceleration_normalized": 0.18,
        "dominant_scenario": "S3",
        "memory_cycle_phase": "normalization",
        "data_quality": 0.9,
        "future_sector_return": 0.01,
        "future_drawdown": -0.02,
    },
    {
        "period_id": "2026-04-s7",
        "as_of_date": "2026-04-10",
        "token_delta_normalized": 0.14,
        "capex_acceleration_normalized": 0.83,
        "dominant_scenario": "S7",
        "memory_cycle_phase": "stress",
        "data_quality": 0.72,
        "future_sector_return": -0.02,
        "future_drawdown": -0.05,
    },
)


def build_ai_capex_token_diagnostic_report(
    baseline_path: str | Path = "reports/backtest/ai_capex_token_adaptive/baseline_report.json",
) -> dict[str, Any]:
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8")) if Path(baseline_path).exists() else build_ai_capex_token_baseline_report()
    periods = [_diagnostic_period(item) for item in PERIODS]
    return {
        "report_version": "ai_capex_token_adaptive_diagnostic_v1",
        "data_lineage": {
            "baseline_report": str(baseline_path),
            "diagnostic_period_source": "api.score_pipeline.plugins.ai_capex_token_diagnostic_backtest.PERIODS",
        },
        "reason_codes": ["AI_CAPEX_TOKEN_ADAPTIVE_DIAGNOSTIC_REPORT"],
        "mode": {
            "production_enabled": False,
            "diagnostic_only": True,
            "shadow_candidate_only": True,
        },
        "baseline_reference": {
            "final_value": baseline["baselines"][0]["final_value"],
            "cost_adjusted_return": baseline["baselines"][0]["metrics"]["cost_adjusted_return"],
        },
        "diagnostic_result": {
            "allocation_contribution": 0.0,
            "final_value": baseline["baselines"][0]["final_value"],
            "cost_adjusted_return": baseline["baselines"][0]["metrics"]["cost_adjusted_return"],
            "final_allocation_changed": False,
        },
        "periods": periods,
        "reason_code_frequency": _reason_code_frequency(periods),
        "future_outcome_comparison": {
            "analysis_only": True,
            "not_used_for_signal_calculation": True,
            "fields": ["future_sector_return", "future_drawdown"],
        },
        "warnings": [
            "dominant_scenario is explanation-only and is not used for allocation",
            "future outcome comparison is analysis-only",
            "adaptive AI Capex-Token contribution remains zero",
        ],
    }


def render_diagnostic_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI Capex-Token Adaptive Diagnostic Report",
        "",
        f"Report version: `{report['report_version']}`",
        "",
        "## Result",
        "",
        f"- Allocation contribution: `{report['diagnostic_result']['allocation_contribution']}`",
        f"- Final allocation changed: `{report['diagnostic_result']['final_allocation_changed']}`",
        f"- Cost-adjusted return: `{report['diagnostic_result']['cost_adjusted_return']}`",
        "",
        "## Periods",
        "",
    ]
    for period in report["periods"]:
        lines.extend(
            [
                f"### {period['period_id']}",
                "",
                f"- Dominant scenario: `{period['dominant_scenario']}`",
                f"- Scenario turnover: `{period['scenario_turnover']}`",
                f"- Score turnover: `{period['score_turnover']}`",
                f"- Data quality: `{period['data_quality_by_period']}`",
                "",
            ]
        )
    lines.extend(["## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.append("")
    return "\n".join(lines)


def _diagnostic_period(row: dict[str, Any]) -> dict[str, Any]:
    probabilities = _scenario_distribution(row["dominant_scenario"])
    dampener = 0.82 if row["data_quality"] >= 0.9 else 0.62
    reason_codes = ["ADAPTIVE_DIAGNOSTIC_ONLY", f"{row['dominant_scenario']}_EXPLANATION_ONLY"]
    warnings = [] if row["data_quality"] >= 0.8 else ["LOW_DATA_QUALITY_REVIEW_REQUIRED"]
    return {
        "period_id": row["period_id"],
        "as_of_date": row["as_of_date"],
        "parameter_version": "ai_capex_token_adaptive_tuning_v0",
        "model_version": "ai_capex_token_adaptive_shadow_v0",
        "adaptive_normalized_features": {
            "token_delta": row["token_delta_normalized"],
            "capex_acceleration": row["capex_acceleration_normalized"],
        },
        "scenario_distribution": probabilities,
        "dominant_scenario": row["dominant_scenario"],
        "dominant_scenario_explanation_only": True,
        "sector_component_diagnostics": {
            "bigtech_platform": {"component_contribution": 0.0, "diagnostic_only": True},
            "power_equipment": {"component_contribution": 0.0, "diagnostic_only": True},
            "semiconductor_hbm": {"component_contribution": 0.0, "diagnostic_only": True},
            "cash_short_duration": {"component_contribution": 0.0, "diagnostic_only": True},
            "inverse_hedge_diagnostic": {"component_contribution": 0.0, "diagnostic_only": True, "user_review_required": True},
        },
        "market_state_dampeners": {
            "confidence": dampener,
            "data_quality": row["data_quality"],
            "valuation_dampener": dampener,
            "macro_stress_dampener": dampener,
            "turnover_dampener": 1.0,
        },
        "score_turnover": 0.0,
        "scenario_turnover": 0.0,
        "reason_codes": reason_codes,
        "warnings": warnings,
        "data_quality_by_period": row["data_quality"],
        "memory_cycle_phase": row["memory_cycle_phase"],
        "calibration_window_metadata": {
            "method": "rolling_percentile",
            "min_observations": 24,
            "observation_count": 24,
            "available_at_cutoff": row["as_of_date"],
        },
        "future_outcome_comparison": {
            "analysis_only": True,
            "not_used_for_signal_calculation": True,
            "future_sector_return": row["future_sector_return"],
            "future_drawdown": row["future_drawdown"],
        },
    }


def _scenario_distribution(dominant: str) -> dict[str, float]:
    remaining = 0.2 / 8.0
    probabilities = {f"S{i}": remaining for i in range(1, 10)}
    probabilities[dominant] = 0.8
    return probabilities


def _reason_code_frequency(periods: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for period in periods:
        for code in period["reason_codes"]:
            counts[code] = counts.get(code, 0) + 1
    return counts
