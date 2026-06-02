from __future__ import annotations

import json
from pathlib import Path

from api.score_pipeline.plugins.ai_capex_token_baselines import (
    BASELINE_NAMES,
    REQUIRED_METRICS,
    build_ai_capex_token_baseline_report,
    render_baseline_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
JSON_REPORT = REPORT_DIR / "baseline_report.json"
MD_REPORT = REPORT_DIR / "baseline_report.md"


def test_baseline_reports_are_generated_and_match_builder():
    assert JSON_REPORT.exists()
    assert MD_REPORT.exists()

    file_report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    built_report = build_ai_capex_token_baseline_report()

    assert file_report == built_report
    assert MD_REPORT.read_text(encoding="utf-8") == render_baseline_markdown(built_report)


def test_baseline_report_schema_and_metrics_are_complete():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["report_version"] == "ai_capex_token_adaptive_baseline_v1"
    assert [baseline["name"] for baseline in report["baselines"]] == list(BASELINE_NAMES)
    for baseline in report["baselines"]:
        assert set(REQUIRED_METRICS) <= set(baseline["metrics"])
        assert baseline["parameter_version"] == "ai_capex_token_adaptive_tuning_v0"
        assert baseline["model_version"] == "ai_capex_token_adaptive_shadow_v0"


def test_diagnostic_only_baseline_does_not_alter_allocation_or_returns():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    returns = {baseline["metrics"]["cost_adjusted_return"] for baseline in report["baselines"]}
    final_values = {baseline["final_value"] for baseline in report["baselines"]}
    for baseline in report["baselines"]:
        assert baseline["allocation_contribution"] == 0.0
        assert baseline["final_allocation_changed"] is False
        assert baseline["metrics"]["turnover"] == 0.0
    assert returns == {0.0}
    assert final_values == {100000.0}


def test_memory_cycle_coverage_and_leakage_guard_are_included():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["memory_cycle_coverage"]["status"] == "PASS_TWO_OR_MORE_CYCLES"
    assert report["memory_cycle_coverage"]["complete_cycle_count"] >= 2
    assert report["memory_cycle_coverage"]["proxy_names_used"] == ["dram_asp_index"]
    assert report["leakage_guard"]["active"] is True
    assert report["leakage_guard"]["available_at_required"] is True
    assert report["leakage_guard"]["future_proxy_points_excluded"] is True


def test_report_keeps_production_disabled_and_documents_unsupported_metrics():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["mode"]["production_enabled"] is False
    assert report["mode"]["diagnostic_only"] is True
    assert report["mode"]["shadow_candidate_only"] is True
    assert any("tax modeling is unavailable" in warning for warning in report["warnings"])
    assert any("remain null" in warning for warning in report["warnings"])
