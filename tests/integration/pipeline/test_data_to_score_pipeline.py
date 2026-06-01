from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from api.score_pipeline.contracts import ConservativeAction, FeatureOutput, ReasonCode
from api.score_pipeline.data_quality import (
    DataQualityAssessor,
    RawDataPoint,
    SnapshotBuilder,
    conservative_action_for_quality,
)
from api.score_pipeline.features import FeatureRegistry, PriceMomentumFeaturePlugin
from api.score_pipeline.parameters import ParameterRegistry
from api.score_pipeline.scoring import ScoreCalculator, ScoreRegistry


def test_raw_fixture_rows_have_data_quality_metadata(sample_raw_data: dict) -> None:
    decision_date = date.fromisoformat(sample_raw_data["decision_date"])

    for row in sample_raw_data["rows"]:
        available_at = datetime.fromisoformat(row["available_at"])
        metadata = DataQualityAssessor().assess(
            source=row["source"],
            as_of_date=decision_date,
            updated_at=available_at,
            values=[row["value"]],
            stale_after_days=14,
        )

        assert metadata.source == row["source"]
        assert metadata.as_of_date == decision_date
        assert metadata.updated_at == available_at
        assert metadata.quality_score > 0


def test_snapshot_builder_rejects_future_data(sample_raw_data: dict) -> None:
    decision_date = date.fromisoformat(sample_raw_data["decision_date"])
    points = _raw_points_from_fixture(sample_raw_data)
    future_available = datetime.combine(decision_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    points.append(
        RawDataPoint(
            key="future_revision",
            value=999.0,
            source="deterministic_pipeline_fixture_future",
            as_of_date=decision_date,
            available_at=future_available,
            updated_at=future_available,
        )
    )

    snapshot = SnapshotBuilder().build("pipeline-fixture:raw", decision_date, points)

    assert "future_revision" not in snapshot.points
    assert any(warning.code == "FUTURE_DATA_REJECTED" for warning in snapshot.warnings)


def test_raw_fixture_builds_feature_snapshot_with_versions(sample_raw_data: dict) -> None:
    features = _feature_outputs(sample_raw_data)

    assert features
    for feature in features:
        assert feature.as_of_date == date.fromisoformat(sample_raw_data["decision_date"])
        assert feature.parameter_version
        assert feature.model_version
        assert feature.data_quality.quality_score > 0


def test_feature_snapshot_scores_expose_contract_fields(sample_raw_data: dict, expected_contract_fields: dict) -> None:
    registry = ParameterRegistry.from_yaml()
    features = _feature_outputs(sample_raw_data)
    scores = ScoreRegistry().calculate_all(features, registry)

    assert scores
    for score in scores:
        payload = asdict(score)
        for field_name in expected_contract_fields["score_contract_fields"]:
            assert field_name in payload
        assert score.model_version
        assert score.parameter_version


def test_low_quality_variant_uses_conservative_non_risk_increasing_fallback(sample_raw_data: dict) -> None:
    decision_date = date.fromisoformat(sample_raw_data["decision_date"])
    updated_at = datetime.combine(decision_date, datetime.min.time(), tzinfo=UTC)
    low_quality = DataQualityAssessor().assess(
        source="low_quality_fixture_variant",
        as_of_date=decision_date,
        updated_at=updated_at,
        values=[None, None],
        stale_after_days=14,
    )
    feature = FeatureOutput(
        feature_id="low_quality_fixture_feature",
        feature_name="Low Quality Fixture Feature",
        entity_id="SAMPLE_US_EQUITY",
        entity_type="asset",
        raw_value=None,
        normalized_value=0.8,
        confidence=low_quality.quality_score,
        data_quality=low_quality,
        as_of_date=decision_date,
        source="low_quality_fixture_variant",
        parameter_version="fixture_parameter_v1",
        model_version="fixture_feature_v1",
        reason_codes=[ReasonCode("LOW_QUALITY_FIXTURE_VARIANT", "test")],
    )

    score = ScoreCalculator().calculate(feature, ParameterRegistry.from_yaml())

    assert conservative_action_for_quality(low_quality) == ConservativeAction.REVIEW_REQUIRED
    assert score.adjustment_intensity == 0
    assert any(warning.message == ConservativeAction.REVIEW_REQUIRED for warning in score.warnings)


def _feature_outputs(sample_raw_data: dict) -> list[FeatureOutput]:
    decision_date = date.fromisoformat(sample_raw_data["decision_date"])
    snapshot = SnapshotBuilder().build(
        "pipeline-fixture:raw",
        decision_date,
        _raw_points_from_fixture(sample_raw_data),
    )
    registry = FeatureRegistry()
    registry.register(PriceMomentumFeaturePlugin(asset_id="SAMPLE_US_EQUITY"))
    return registry.run_enabled(snapshot, ParameterRegistry.from_yaml())


def _raw_points_from_fixture(sample_raw_data: dict) -> list[RawDataPoint]:
    points: list[RawDataPoint] = []
    price_row: dict | None = None
    for row in sample_raw_data["rows"]:
        available_at = datetime.fromisoformat(row["available_at"])
        as_of_date = date.fromisoformat(row["as_of_date"])
        points.append(
            RawDataPoint(
                key=f"{row['kind']}:{row['metric']}",
                value=float(row["value"]),
                source=row["source"],
                as_of_date=as_of_date,
                available_at=available_at,
                updated_at=available_at,
            )
        )
        if row["kind"] == "price":
            price_row = row

    assert price_row is not None
    price_available_at = datetime.fromisoformat(price_row["available_at"])
    price_as_of_date = date.fromisoformat(price_row["as_of_date"])
    for key in ("price_start", "price_end"):
        points.append(
            RawDataPoint(
                key=key,
                value=float(price_row["value"]),
                source=price_row["source"],
                as_of_date=price_as_of_date,
                available_at=price_available_at,
                updated_at=price_available_at,
            )
        )
    return points
