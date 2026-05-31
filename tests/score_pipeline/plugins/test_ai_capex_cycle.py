from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
from api.score_pipeline.parameters import ParameterEntry, ParameterRegistry
from api.score_pipeline.plugins.ai_capex_cycle import AICapexCyclePlugin


DECISION_DATE = date(2026, 5, 31)


def test_ai_capex_cycle_complete_data_produces_bounded_feature_output():
    output = AICapexCyclePlugin().compute(_snapshot(), _registry())

    assert output.feature_id == "feature:ai_capex_cycle"
    assert 0 <= output.normalized_value <= 1
    assert output.raw_value == pytest.approx(output.normalized_value)
    assert output.confidence == pytest.approx(1.0)
    assert any(reason.code == "AI_CAPEX_CYCLE_COMPUTED" for reason in output.reason_codes)
    assert not hasattr(output, "target_weight")
    assert not hasattr(output, "order_candidate")


def test_ai_capex_cycle_missing_required_input_returns_neutral_review():
    points = _points()
    points.pop("token_proxy_index")

    output = AICapexCyclePlugin().compute(HistoricalSnapshot("snap-missing", DECISION_DATE, points), _registry())

    assert output.raw_value is None
    assert output.normalized_value == pytest.approx(0.5)
    assert output.confidence == 0.0
    assert any(reason.code == "AI_CAPEX_DATA_MISSING" for reason in output.reason_codes)
    assert any(warning.code == "MISSING_DATA" for warning in output.warnings)


def test_ai_capex_cycle_stale_data_reduces_confidence_and_records_reason():
    stale_updated_at = datetime(2025, 12, 31, tzinfo=UTC)
    output = AICapexCyclePlugin().compute(_snapshot(updated_at=stale_updated_at), _registry(stale_after_days=10))

    assert output.confidence < 1.0
    assert output.data_quality.is_stale is True
    assert any(reason.code == "AI_CAPEX_DATA_STALE" for reason in output.reason_codes)
    assert any(warning.code == "STALE_DATA" for warning in output.warnings)


def test_ai_capex_cycle_zero_tcr_denominator_stays_bounded():
    points = _points(token_previous=0.0)

    output = AICapexCyclePlugin().compute(HistoricalSnapshot("snap-zero-denom", DECISION_DATE, points), _registry())

    assert 0 <= output.normalized_value <= 1
    assert any(reason.code == "AI_CAPEX_CYCLE_COMPUTED" for reason in output.reason_codes)


def test_ai_capex_cycle_unapproved_or_missing_weights_falls_back_conservatively():
    registry = _registry(approved=False)

    output = AICapexCyclePlugin().compute(_snapshot(), registry)

    assert output.normalized_value == pytest.approx(0.5)
    assert output.confidence == 0.0
    assert output.raw_value is None
    assert any(reason.code == "AI_CAPEX_DATA_MISSING" for reason in output.reason_codes)


def test_ai_capex_cycle_rejects_future_data_via_snapshot_contract():
    points = _points()
    current = points["token_proxy_index"]
    points["token_proxy_index"] = RawDataPoint(
        key=current.key,
        value=current.value,
        source=current.source,
        as_of_date=current.as_of_date,
        available_at=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at=current.updated_at,
    )

    output = AICapexCyclePlugin().compute(HistoricalSnapshot("snap-future", DECISION_DATE, points), _registry())

    assert output.normalized_value == pytest.approx(0.5)
    assert output.confidence == 0.0
    assert any(warning.code == "AI_CAPEX_FUTURE_DATA_REJECTED" for warning in output.warnings)


def test_ai_capex_cycle_has_no_forbidden_imports():
    source = Path("api/score_pipeline/plugins/ai_capex_cycle.py").read_text(encoding="utf-8").lower()

    forbidden = ["fastapi", "sqlite3", "api.brokers", "api.strategy", "api.features.orders", "kis"]
    assert not [item for item in forbidden if item in source]


def _snapshot(updated_at=None):
    return HistoricalSnapshot("snap-ai-capex", DECISION_DATE, _points(updated_at=updated_at))


def _points(token_previous=100.0, updated_at=None):
    updated_at = updated_at or datetime(2026, 5, 30, tzinfo=UTC)
    available_at = datetime(2026, 5, 30, tzinfo=UTC)
    values = {
        "bigtech_ai_capex_yoy": 0.30,
        "bigtech_ai_capex_accel": 0.10,
        "token_proxy_index": 120.0,
        "token_proxy_index_prev": token_previous,
    }
    return {
        key: RawDataPoint(
            key=key,
            value=value,
            source="fixture",
            as_of_date=DECISION_DATE,
            available_at=available_at,
            updated_at=updated_at,
        )
        for key, value in values.items()
    }


def _registry(stale_after_days=120, approved=True):
    return ParameterRegistry(
        [
            ParameterEntry(
                name="ai_cycle_weights",
                value={
                    "capex_growth": 0.30,
                    "demand_momentum": 0.25,
                    "supply_constraint": 0.20,
                    "profitability_quality": 0.15,
                    "data_quality": 0.10,
                },
                version="ai_capex_cycle_test_v1",
                valid_from=DECISION_DATE - timedelta(days=365),
                valid_to=None,
                source="test",
                reason="test approved weights",
                approved=approved,
                affected_modules=["score_pipeline"],
            ),
            ParameterEntry(
                name="stale_after_days",
                value=stale_after_days,
                version="ai_capex_cycle_test_v1",
                valid_from=DECISION_DATE - timedelta(days=365),
                valid_to=None,
                source="test",
                reason="test stale window",
                approved=approved,
                affected_modules=["data_quality"],
            ),
            ParameterEntry(
                name="quality_min_required",
                value=0.70,
                version="ai_capex_cycle_test_v1",
                valid_from=DECISION_DATE - timedelta(days=365),
                valid_to=None,
                source="test",
                reason="test quality minimum",
                approved=approved,
                affected_modules=["data_quality"],
            ),
        ]
    )
