from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
from api.score_pipeline.parameters import ParameterEntry, ParameterRegistry
from api.score_pipeline.plugins.bio_capex_bottleneck import (
    DEMAND_MOMENTUM_COMPONENTS,
    FINANCIAL_QUALITY_COMPONENTS,
    RISK_PENALTY_COMPONENTS,
    STRUCTURAL_MOAT_COMPONENTS,
    BioCapexBottleneckPlugin,
    is_core_anchor_allowed,
)


DECISION_DATE = date(2026, 5, 31)


def test_bio_capex_bottleneck_high_moat_demand_low_risk_scores_well():
    breakdown = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(), _registry())

    assert breakdown.structural_moat == pytest.approx(0.8)
    assert breakdown.demand_momentum == pytest.approx(0.7)
    assert breakdown.financial_quality == pytest.approx(0.75)
    assert breakdown.risk_penalty == pytest.approx(0.1)
    assert breakdown.final_score == pytest.approx(0.7175)
    assert any(reason.code == "BIO_CAPEX_BOTTLENECK_COMPUTED" for reason in breakdown.reason_codes)


def test_bio_capex_bottleneck_high_risk_penalty_reduces_score():
    low_risk = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(risk=0.1), _registry())
    high_risk = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(risk=0.9), _registry())

    assert high_risk.final_score < low_risk.final_score
    assert low_risk.final_score - high_risk.final_score == pytest.approx(0.28)


def test_bio_capex_bottleneck_missing_inputs_lower_confidence():
    points = _points()
    points.pop("gross_margin")

    output = BioCapexBottleneckPlugin().compute(HistoricalSnapshot("snap-missing", DECISION_DATE, points), _registry())

    assert 0 <= output.normalized_value <= 1
    assert output.confidence < 1.0
    assert any(reason.code == "BIO_CAPEX_DATA_MISSING" for reason in output.reason_codes)
    assert any(warning.code == "BIO_CAPEX_MISSING_COMPONENT" for warning in output.warnings)


def test_bio_capex_bottleneck_clinical_event_tag_blocks_core_anchor():
    tags = {"clinical_event_biotech", "single_pipeline_biotech"}

    breakdown = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(), _registry(), asset_tags=tags)

    assert is_core_anchor_allowed(tags) is False
    assert any(reason.code == "BIO_CAPEX_CORE_ANCHOR_BLOCKED" for reason in breakdown.reason_codes)
    assert any(warning.code == "BIO_CAPEX_CLINICAL_EVENT_OBSERVATION_ONLY" for warning in breakdown.warnings)


def test_bio_capex_bottleneck_score_is_clamped_to_range():
    max_score = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(moat=1.5, demand=1.5, quality=1.5, risk=-1.0), _registry())
    min_score = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(moat=-1.0, demand=-1.0, quality=-1.0, risk=2.0), _registry())

    assert max_score.final_score == 1.0
    assert min_score.final_score == 0.0


def test_bio_capex_bottleneck_component_weights_are_deterministic():
    registry = _registry(structural_weights={key: (1.0 if key == "switching_cost" else 0.0) for key in STRUCTURAL_MOAT_COMPONENTS})
    points = _points(moat=0.4)
    points["switching_cost"] = _point("switching_cost", 0.9)

    breakdown = BioCapexBottleneckPlugin().compute_breakdown(HistoricalSnapshot("snap-weighted", DECISION_DATE, points), registry)

    assert breakdown.structural_moat == pytest.approx(0.9)


def test_bio_capex_bottleneck_unapproved_weights_fallback_is_neutral_review():
    breakdown = BioCapexBottleneckPlugin().compute_breakdown(_snapshot(), _registry(approved=False))

    assert breakdown.final_score == pytest.approx(0.5)
    assert breakdown.confidence == 0.0
    assert any(reason.code == "BIO_CAPEX_DATA_MISSING" for reason in breakdown.reason_codes)


def test_bio_capex_bottleneck_future_data_is_not_accepted():
    points = _points()
    current = points["switching_cost"]
    points["switching_cost"] = RawDataPoint(
        key=current.key,
        value=current.value,
        source=current.source,
        as_of_date=current.as_of_date,
        available_at=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at=current.updated_at,
    )

    breakdown = BioCapexBottleneckPlugin().compute_breakdown(HistoricalSnapshot("snap-future", DECISION_DATE, points), _registry())

    assert breakdown.confidence < 1.0
    assert any(warning.code == "BIO_CAPEX_FUTURE_DATA_REJECTED" for warning in breakdown.warnings)


def test_bio_capex_bottleneck_has_no_forbidden_imports():
    source = Path("api/score_pipeline/plugins/bio_capex_bottleneck.py").read_text(encoding="utf-8").lower()

    forbidden = ["fastapi", "sqlite3", "api.brokers", "api.strategy", "api.features.orders", "kis"]
    assert not [item for item in forbidden if item in source]


def _snapshot(moat=0.8, demand=0.7, quality=0.75, risk=0.1):
    return HistoricalSnapshot("snap-bio-capex", DECISION_DATE, _points(moat=moat, demand=demand, quality=quality, risk=risk))


def _points(moat=0.8, demand=0.7, quality=0.75, risk=0.1):
    points = {}
    for key in STRUCTURAL_MOAT_COMPONENTS:
        points[key] = _point(key, moat)
    for key in DEMAND_MOMENTUM_COMPONENTS:
        points[key] = _point(key, demand)
    for key in FINANCIAL_QUALITY_COMPONENTS:
        points[key] = _point(key, quality)
    for key in RISK_PENALTY_COMPONENTS:
        points[key] = _point(key, risk)
    return points


def _point(key, value):
    return RawDataPoint(
        key=key,
        value=value,
        source="fixture",
        as_of_date=DECISION_DATE,
        available_at=datetime(2026, 5, 30, tzinfo=UTC),
        updated_at=datetime(2026, 5, 30, tzinfo=UTC),
    )


def _registry(approved=True, structural_weights=None):
    structural_weights = structural_weights or {
        "switching_cost": 0.20,
        "regulatory_lock_in": 0.15,
        "recurring_revenue": 0.20,
        "installed_base": 0.15,
        "customer_diversification": 0.15,
        "workflow_penetration": 0.15,
    }
    entries = [
        _entry(
            "final_score_weights",
            {
                "structural_moat": 0.40,
                "demand_momentum": 0.35,
                "financial_quality": 0.25,
                "risk_penalty_multiplier": 0.35,
            },
            approved,
        ),
        _entry("structural_moat_weights", structural_weights, approved),
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
            approved,
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
            approved,
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
            approved,
        ),
    ]
    return ParameterRegistry(entries)


def _entry(name, value, approved):
    return ParameterEntry(
        name=name,
        value=value,
        version="bio_capex_bottleneck_test_v1",
        valid_from=DECISION_DATE - timedelta(days=365),
        valid_to=None,
        source="test",
        reason="test parameter",
        approved=approved,
        affected_modules=["score_pipeline"],
    )
