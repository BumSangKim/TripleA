from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from api.data.capex_feature_materializer import CapexFeatureMaterializer
from api.data.capex_snapshot_builder import CapexRawSnapshot, CapexSnapshotPointMetadata
from api.score_pipeline.contracts import DataQualityMetadata
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
from api.score_pipeline.plugins.ai_capex_cycle import REQUIRED_INPUTS as AI_REQUIRED_INPUTS
from api.score_pipeline.plugins.bio_capex_bottleneck import (
    DEMAND_MOMENTUM_COMPONENTS,
    FINANCIAL_QUALITY_COMPONENTS,
    RISK_PENALTY_COMPONENTS,
    STRUCTURAL_MOAT_COMPONENTS,
)


DECISION_DATE = date(2024, 5, 31)
AVAILABLE = datetime(2024, 5, 30, tzinfo=UTC)


def raw_point(key: str, value: float, *, available_at: datetime = AVAILABLE) -> RawDataPoint:
    return RawDataPoint(
        key=key,
        value=value,
        source="fixture",
        as_of_date=DECISION_DATE,
        available_at=available_at,
        updated_at=available_at,
    )


def metadata(key: str, unit: str) -> CapexSnapshotPointMetadata:
    quality = DataQualityMetadata(
        source="fixture",
        as_of_date=DECISION_DATE,
        updated_at=AVAILABLE,
        quality_score=1.0,
        missing_ratio=0.0,
    )
    return CapexSnapshotPointMetadata(
        key=key,
        metric_id=key,
        source="fixture",
        source_id="fixture",
        unit=unit,
        available_at=AVAILABLE,
        updated_at=AVAILABLE,
        revision_id=None,
        quality=quality,
    )


def capex_raw_snapshot(points: dict[str, RawDataPoint], units: dict[str, str] | None = None) -> CapexRawSnapshot:
    unit_map = units or {}
    return CapexRawSnapshot(
        snapshot=HistoricalSnapshot("raw-snap", DECISION_DATE, points),
        point_metadata={key: metadata(key, unit) for key, unit in unit_map.items()},
    )


def test_complete_snapshot_materializes_ai_and_bio_inputs() -> None:
    points = {
        "ai.capex.yoy": raw_point("ai.capex.yoy", 0.18),
        "ai.capex.acceleration": raw_point("ai.capex.acceleration", 0.04),
        "ai.token_proxy.index": raw_point("ai.token_proxy.index", 1.34),
        "token_proxy_index_prev": raw_point("token_proxy_index_prev", 1.0),
    }
    for key in (
        *STRUCTURAL_MOAT_COMPONENTS,
        *DEMAND_MOMENTUM_COMPONENTS,
        *FINANCIAL_QUALITY_COMPONENTS,
        *RISK_PENALTY_COMPONENTS,
    ):
        points[key] = raw_point(key, 0.5)
    units = {
        "ai.capex.yoy": "year_over_year_change",
        "ai.capex.acceleration": "quarter_over_quarter_delta",
        "ai.token_proxy.index": "index_level",
    }

    materializer = CapexFeatureMaterializer()
    ai = materializer.materialize_ai(capex_raw_snapshot(points, units))
    bio = materializer.materialize_bio(capex_raw_snapshot(points, units))

    assert set(ai.points) == set(AI_REQUIRED_INPUTS)
    assert ai.points["bigtech_ai_capex_yoy"].value == 0.18
    assert ai.points["token_proxy_index"].value == 1.34
    assert ai.confidence == 1.0
    assert set(bio.points) == set((
        *STRUCTURAL_MOAT_COMPONENTS,
        *DEMAND_MOMENTUM_COMPONENTS,
        *FINANCIAL_QUALITY_COMPONENTS,
        *RISK_PENALTY_COMPONENTS,
    ))
    assert bio.confidence == 1.0


def test_missing_metric_lowers_confidence_and_warns() -> None:
    points = {
        "ai.capex.yoy": raw_point("ai.capex.yoy", 0.18),
        "ai.token_proxy.index": raw_point("ai.token_proxy.index", 1.34),
        "token_proxy_index_prev": raw_point("token_proxy_index_prev", 1.0),
    }

    result = CapexFeatureMaterializer().materialize_ai(
        capex_raw_snapshot(
            points,
            {
                "ai.capex.yoy": "year_over_year_change",
                "ai.token_proxy.index": "index_level",
            },
        )
    )

    assert "bigtech_ai_capex_accel" in result.missing_inputs
    assert result.confidence < 1.0
    assert any(warning.code == "CAPEX_MATERIALIZER_MISSING_INPUT" for warning in result.warnings)


def test_unit_mismatch_without_mapping_triggers_review_required_warning() -> None:
    points = {
        "ai.capex.yoy": raw_point("ai.capex.yoy", 18.0),
        "ai.capex.acceleration": raw_point("ai.capex.acceleration", 0.04),
        "ai.token_proxy.index": raw_point("ai.token_proxy.index", 1.34),
        "token_proxy_index_prev": raw_point("token_proxy_index_prev", 1.0),
    }
    units = {
        "ai.capex.yoy": "percent",
        "ai.capex.acceleration": "quarter_over_quarter_delta",
        "ai.token_proxy.index": "index_level",
    }

    result = CapexFeatureMaterializer().materialize_ai(capex_raw_snapshot(points, units))

    assert "bigtech_ai_capex_yoy" in result.review_required
    assert "bigtech_ai_capex_yoy" in result.missing_inputs
    assert any(warning.code == "CAPEX_MATERIALIZER_UNIT_REVIEW_REQUIRED" for warning in result.warnings)


def test_future_data_is_not_accepted() -> None:
    future = AVAILABLE + timedelta(days=5)
    points = {
        "ai.capex.yoy": raw_point("ai.capex.yoy", 0.18),
        "ai.capex.acceleration": raw_point("ai.capex.acceleration", 0.04),
        "ai.token_proxy.index": raw_point("ai.token_proxy.index", 9.99, available_at=future),
        "token_proxy_index_prev": raw_point("token_proxy_index_prev", 1.0),
    }
    units = {
        "ai.capex.yoy": "year_over_year_change",
        "ai.capex.acceleration": "quarter_over_quarter_delta",
        "ai.token_proxy.index": "index_level",
    }

    result = CapexFeatureMaterializer().materialize_ai(capex_raw_snapshot(points, units))

    assert "token_proxy_index" not in result.points
    assert "token_proxy_index" in result.missing_inputs
    assert any(warning.code == "CAPEX_MATERIALIZER_FUTURE_DATA_REJECTED" for warning in result.warnings)


def test_materializer_has_no_execution_or_rebalance_surface() -> None:
    source = __import__("pathlib").Path("api/data/capex_feature_materializer.py").read_text()
    forbidden_terms = (
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "order_candidate",
        "target_weight",
        "rebalance",
        "submit_order",
        "place_order",
    )

    assert not any(term in source for term in forbidden_terms)
