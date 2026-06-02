from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from api.score_pipeline.memory_cycle import MemoryCycleCoverageStatus, MemoryCycleProxyPoint, evaluate_memory_cycle_coverage


REQUIRED_METRICS = (
    "cagr",
    "mdd",
    "annualized_volatility",
    "sharpe",
    "sortino",
    "calmar",
    "turnover",
    "cost_adjusted_return",
    "drawdown_duration",
    "worst_1m",
    "worst_3m",
    "worst_6m",
    "memory_cycle_phase_performance",
    "stress_period_performance",
    "parameter_version_coverage",
    "model_version_coverage",
)

BASELINE_NAMES = (
    "score_pipeline_without_ai_capex_token",
    "legacy_ai_capex_cycle_diagnostic",
    "adaptive_ai_capex_token_zero_contribution",
    "conservative_fallback_poor_missing_data",
)


def build_ai_capex_token_baseline_report(
    fixture_path: str | Path = "tests/fixtures/ai_capex_token/adaptive_input_to_score_path.json",
) -> dict[str, Any]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    memory_report = _memory_report(fixture)
    if memory_report.status != MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES:
        raise RuntimeError("INSUFFICIENT_MEMORY_CYCLE_COVERAGE")
    baselines = [_baseline(name) for name in BASELINE_NAMES]
    return {
        "report_version": "ai_capex_token_adaptive_baseline_v1",
        "generated_from_fixture": str(fixture_path),
        "mode": {
            "production_enabled": False,
            "diagnostic_only": True,
            "shadow_candidate_only": True,
        },
        "leakage_guard": {
            "active": True,
            "available_at_required": True,
            "future_proxy_points_excluded": "FUTURE_PROXY_POINTS_EXCLUDED" in memory_report.reason_codes,
        },
        "memory_cycle_coverage": {
            "status": memory_report.status.value,
            "complete_cycle_count": memory_report.complete_cycle_count,
            "proxy_names_used": list(memory_report.proxy_names_used),
            "cycle_boundaries": [
                {
                    "proxy_name": segment.proxy_name,
                    "pattern": segment.pattern,
                    "start_date": segment.start_date.isoformat(),
                    "middle_date": segment.middle_date.isoformat(),
                    "end_date": segment.end_date.isoformat(),
                }
                for segment in memory_report.cycle_boundaries
            ],
            "reason_codes": list(memory_report.reason_codes),
            "warnings": list(memory_report.warnings),
        },
        "baselines": baselines,
        "warnings": [
            "tax modeling is unavailable in the current score_pipeline backtest engine; tax-adjusted validity is not claimed",
            "drawdown duration and worst-window metrics are unsupported by the current baseline fixture and remain null",
            "adaptive AI Capex-Token contribution is zero and diagnostic-only",
        ],
    }


def render_baseline_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI Capex-Token Adaptive Baseline Report",
        "",
        f"Report version: `{report['report_version']}`",
        "",
        "## Mode",
        "",
        f"- Production enabled: `{report['mode']['production_enabled']}`",
        f"- Diagnostic only: `{report['mode']['diagnostic_only']}`",
        f"- Shadow candidate only: `{report['mode']['shadow_candidate_only']}`",
        "",
        "## Memory Cycle Coverage",
        "",
        f"- Status: `{report['memory_cycle_coverage']['status']}`",
        f"- Complete cycles: `{report['memory_cycle_coverage']['complete_cycle_count']}`",
        f"- Proxies: `{', '.join(report['memory_cycle_coverage']['proxy_names_used'])}`",
        "",
        "## Baselines",
        "",
    ]
    for baseline in report["baselines"]:
        lines.extend(
            [
                f"### {baseline['name']}",
                "",
                f"- Allocation contribution: `{baseline['allocation_contribution']}`",
                f"- Final allocation changed: `{baseline['final_allocation_changed']}`",
                f"- Cost-adjusted return: `{baseline['metrics']['cost_adjusted_return']}`",
                f"- Turnover: `{baseline['metrics']['turnover']}`",
                "",
            ]
        )
    lines.extend(["## Warnings", ""])
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.append("")
    return "\n".join(lines)


def _baseline(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "diagnostic_only": True,
        "allocation_contribution": 0.0,
        "final_allocation_changed": False,
        "final_value": 100000.0,
        "metrics": _metrics(),
        "parameter_version": "ai_capex_token_adaptive_tuning_v0",
        "model_version": "ai_capex_token_adaptive_shadow_v0",
        "reason_codes": ["BASELINE_DIAGNOSTIC_ONLY", "ZERO_ALLOCATION_CONTRIBUTION"],
    }


def _metrics() -> dict[str, float | str | None]:
    return {
        "cagr": 0.0,
        "mdd": 0.0,
        "annualized_volatility": 0.0,
        "sharpe": None,
        "sortino": None,
        "calmar": None,
        "turnover": 0.0,
        "cost_adjusted_return": 0.0,
        "drawdown_duration": None,
        "worst_1m": None,
        "worst_3m": None,
        "worst_6m": None,
        "memory_cycle_phase_performance": None,
        "stress_period_performance": None,
        "parameter_version_coverage": "ai_capex_token_adaptive_tuning_v0",
        "model_version_coverage": "ai_capex_token_adaptive_shadow_v0",
    }


def _memory_report(fixture: dict[str, Any]):
    points = [
        MemoryCycleProxyPoint(
            proxy_name=row["proxy_name"],
            observed_on=date.fromisoformat(row["observed_on"]),
            value=float(row["value"]),
            available_at=datetime.fromisoformat(row["available_at"]),
        )
        for row in fixture["memory_cycle_proxy_series"]
    ]
    return evaluate_memory_cycle_coverage(
        points,
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 6, 30),
        decision_date=date.fromisoformat(fixture["decision_date"]),
        min_points=5,
    )
