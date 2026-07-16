from __future__ import annotations

from api.score_pipeline.plugins.ai_capex_token_diagnostic_backtest import build_ai_capex_token_diagnostic_report
from api.score_pipeline.semiconductor_ai_capex_adapter import SemiconductorAICapexShadowAdapter


def test_shadow_report_reaches_semiconductor_feature_snapshot_without_changing_allocation() -> None:
    report = build_ai_capex_token_diagnostic_report()
    before = report["diagnostic_result"]["allocation_contribution"]

    snapshot = SemiconductorAICapexShadowAdapter().adapt(report, period_id="2026-03-s3")

    assert before == 0.0
    assert snapshot.allocation_contribution == 0.0
    assert snapshot.diagnostic_only is True
    assert report["mode"] == {"production_enabled": False, "diagnostic_only": True, "shadow_candidate_only": True}
    assert all(feature.feature_value is not None for feature in snapshot.features)
