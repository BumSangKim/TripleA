from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from api.features.capex_cycle.schemas import CapexCycleScoreResponse
from api.features.capex_cycle.service import CapexCycleService
from api.score_pipeline.parameters import ParameterEntry, ParameterRegistry


DECISION_DATE = date(2026, 8, 1)


def test_service_returns_normal_score_response_from_fixture_data():
    service = CapexCycleService(registry=_registry(), macro_multiplier=1.0)

    scores = service.get_scores(as_of_date=DECISION_DATE)

    ai_score = next(score for score in scores if isinstance(score, CapexCycleScoreResponse))
    assert 0.0 <= ai_score.score <= 1.0
    assert ai_score.confidence > 0.0
    assert ai_score.data_quality > 0.0
    assert ai_score.parameter_version == "capex_service_test_v1"
    assert any(reason.code == "AI_CAPEX_CYCLE_COMPUTED" for reason in ai_score.reason_codes)
    assert not hasattr(ai_score, "target_weight")
    assert not hasattr(ai_score, "execution_id")


def test_service_missing_data_returns_conservative_warning():
    service = CapexCycleService(
        registry=_registry(),
        capex_adapter=EmptyCapexAdapter(),
        company_metric_adapter=EmptyCompanyMetricAdapter(),
    )

    scores = service.get_scores(as_of_date=DECISION_DATE)
    ai_score = next(score for score in scores if isinstance(score, CapexCycleScoreResponse))

    assert ai_score.score == 0.5
    assert ai_score.confidence == 0.0
    assert any(reason.code == "AI_CAPEX_DATA_MISSING" for reason in ai_score.reason_codes)
    assert any(warning.code == "MISSING_DATA" for warning in ai_score.warnings)


def test_service_valuation_unavailable_stays_none():
    service = CapexCycleService(registry=_registry(), valuation_inputs={"sample_ai": {"last_price": 100.0}})

    valuation = service.get_valuation(asset_id="sample_ai", as_of_date=DECISION_DATE)

    assert valuation.fair_value is None
    assert valuation.fair_value_ratio is None
    assert valuation.target_per is None
    assert valuation.confidence == 0.0
    assert any(reason.code == "VALUATION_UNAVAILABLE" for reason in valuation.reason_codes)


def test_service_reason_codes_propagate_to_scenario_response():
    service = CapexCycleService(registry=_registry(), macro_multiplier=None)

    scenario = service.get_scenario(as_of_date=DECISION_DATE)

    assert scenario.dominant_scenario
    assert any(reason.code == "CAPEX_SCENARIO_INPUT_MISSING" for reason in scenario.reason_codes)
    assert any(warning.code == "CAPEX_SCENARIO_REVIEW_REQUIRED" for warning in scenario.warnings)


def test_service_has_no_forbidden_layer_imports():
    source = Path("api/features/capex_cycle/service.py").read_text(encoding="utf-8").lower()

    forbidden = ["api.brokers", "api.strategy", "api.features.orders", "kis", "execute_draft", "submit_order"]
    assert not [item for item in forbidden if item in source]


class EmptyCapexAdapter:
    adapter_name = "empty"

    def list_series(self):
        return ()

    def fetch_series(self, series_id, *, start=None, end=None, as_of=None):
        return ()


class EmptyCompanyMetricAdapter:
    adapter_name = "empty"

    def list_metrics(self, company_id=None):
        return ()

    def fetch_metric(self, company_id, metric_id, *, start=None, end=None, as_of=None):
        return ()


def _registry():
    return ParameterRegistry(
        [
            _entry(
                "ai_cycle_weights",
                {
                    "capex_growth": 0.30,
                    "demand_momentum": 0.25,
                    "supply_constraint": 0.20,
                    "profitability_quality": 0.15,
                    "data_quality": 0.10,
                },
            ),
            _entry("stale_after_days", 180),
            _entry("quality_min_required", 0.70),
            _entry(
                "final_score_weights",
                {
                    "structural_moat": 0.40,
                    "demand_momentum": 0.35,
                    "financial_quality": 0.25,
                    "risk_penalty_multiplier": 0.35,
                },
            ),
            _entry(
                "structural_moat_weights",
                {
                    "switching_cost": 0.20,
                    "regulatory_lock_in": 0.15,
                    "recurring_revenue": 0.20,
                    "installed_base": 0.15,
                    "customer_diversification": 0.15,
                    "workflow_penetration": 0.15,
                },
            ),
            _entry(
                "demand_momentum_weights",
                {
                    "segment_growth": 0.20,
                    "order_growth": 0.20,
                    "backlog_growth": 0.20,
                    "book_to_bill": 0.15,
                    "consumables_growth": 0.15,
                    "inventory_normalization": 0.10,
                },
            ),
            _entry(
                "financial_quality_weights",
                {
                    "gross_margin": 0.18,
                    "ebitda_margin": 0.18,
                    "fcf_margin": 0.18,
                    "roic": 0.18,
                    "balance_sheet": 0.14,
                    "margin_stability": 0.14,
                },
            ),
            _entry(
                "risk_penalty_weights",
                {
                    "one_off_demand": 0.12,
                    "customer_inventory_risk": 0.12,
                    "order_deceleration": 0.14,
                    "valuation_overheat": 0.14,
                    "overcapacity": 0.12,
                    "funding_risk": 0.12,
                    "guidance_cut": 0.12,
                    "geopolitical_risk": 0.12,
                },
            ),
        ]
    )


def _entry(name, value):
    return ParameterEntry(
        name=name,
        value=value,
        version="capex_service_test_v1",
        valid_from=DECISION_DATE - timedelta(days=365),
        valid_to=None,
        source="test",
        reason="test parameter",
        approved=True,
        affected_modules=["score_pipeline"],
    )
