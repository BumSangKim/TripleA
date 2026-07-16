from __future__ import annotations

from copy import deepcopy

from api.score_pipeline.plugins.ai_capex_token_diagnostic_backtest import build_ai_capex_token_diagnostic_report
from api.score_pipeline.semiconductor_ai_capex_adapter import SemiconductorAICapexShadowAdapter


def test_adapter_projects_existing_shadow_evidence_without_allocation_activation() -> None:
    report = build_ai_capex_token_diagnostic_report()

    snapshot = SemiconductorAICapexShadowAdapter().adapt(report, period_id="2026-02-s1")

    assert snapshot.diagnostic_only is True
    assert snapshot.allocation_contribution == 0.0
    assert snapshot.fallback_state is None
    assert snapshot.parameter_version == "ai_capex_token_adaptive_tuning_v0"
    assert {feature.feature_id for feature in snapshot.features} == {
        "semiconductor.demand.ai_capex_demand_pressure",
        "semiconductor.demand.ai_capex_capex_momentum",
    }
    assert all(feature.metadata["allocation_contribution"] == 0.0 for feature in snapshot.features)


def test_missing_shadow_field_stays_review_required_instead_of_being_synthesized() -> None:
    report = deepcopy(build_ai_capex_token_diagnostic_report())
    del report["periods"][0]["adaptive_normalized_features"]["token_delta"]

    snapshot = SemiconductorAICapexShadowAdapter().adapt(report, period_id="2026-02-s1")

    assert snapshot.confidence == 0.0
    assert snapshot.data_quality == 0.0
    assert snapshot.fallback_state == "REVIEW_REQUIRED"
    assert next(feature for feature in snapshot.features if feature.feature_id.endswith("demand_pressure")).feature_value is None
