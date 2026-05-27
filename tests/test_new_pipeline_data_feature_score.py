from datetime import UTC, date, datetime, timedelta

import pytest

from api.new_pipeline.contracts import ConservativeAction
from api.new_pipeline.data_quality import (
    DataQualityAssessor,
    RawDataPoint,
    SnapshotBuilder,
    conservative_action_for_quality,
)
from api.new_pipeline.features import FeatureRegistry, PriceMomentumFeaturePlugin
from api.new_pipeline.parameters import ParameterRegistry
from api.new_pipeline.scoring import ScoreCalculator, confidence_adjust, data_quality_adjust, ema_smooth


NOW = datetime(2026, 5, 27, tzinfo=UTC)


def _point(key, value, *, available_at=NOW, updated_at=NOW):
    return RawDataPoint(key, value, "fixture", date(2026, 5, 27), available_at, updated_at)


def test_data_quality_detects_missing_stale_and_anomalous_data():
    metadata = DataQualityAssessor().assess(
        source="fixture",
        as_of_date=date(2026, 5, 27),
        updated_at=NOW - timedelta(days=30),
        values=[1.0, None, 1.1, 100.0, 1.2],
        stale_after_days=7,
    )
    assert metadata.missing_ratio == 0.2
    assert metadata.is_stale is True
    assert {warning.code for warning in metadata.warnings} >= {"MISSING_DATA", "STALE_DATA"}
    assert conservative_action_for_quality(metadata) in {ConservativeAction.HOLD, ConservativeAction.REVIEW_REQUIRED}


def test_snapshot_builder_filters_future_data_and_get_available_rejects_leakage():
    future = _point("future_price", 100, available_at=NOW + timedelta(days=1))
    snapshot = SnapshotBuilder().build("snap-1", date(2026, 5, 27), [future])
    assert "future_price" not in snapshot.points
    assert snapshot.warnings[0].code == "FUTURE_DATA_REJECTED"


def test_feature_plugin_registration_execution_and_normalized_output():
    snapshot = SnapshotBuilder().build(
        "snap-1",
        date(2026, 5, 27),
        [_point("price_start", 100), _point("price_end", 110)],
    )
    registry = FeatureRegistry()
    registry.register(PriceMomentumFeaturePlugin(asset_id="SPY"))
    outputs = registry.run_enabled(snapshot, ParameterRegistry.from_yaml())
    assert registry.plugin_ids() == {"price_momentum_feature"}
    assert outputs[0].raw_value == pytest.approx(0.1)
    assert 0 <= outputs[0].normalized_value <= 1
    assert outputs[0].parameter_version == "new_pipeline_v1"
    assert outputs[0].data_quality.quality_score == 1.0


def test_feature_plugin_missing_input_fallback_and_independence():
    snapshot = SnapshotBuilder().build("snap-1", date(2026, 5, 27), [_point("price_start", 100)])
    registry = FeatureRegistry()
    registry.register(PriceMomentumFeaturePlugin(asset_id="SPY"))
    output = registry.run_enabled(snapshot, ParameterRegistry.from_yaml())[0]
    assert output.normalized_value == 0.5
    assert any(warning.code == "FEATURE_FALLBACK_NEUTRAL" for warning in output.warnings)
    assert not hasattr(output, "target_weight")
    assert not hasattr(output, "order_candidate")


def test_score_layer_flow_and_previous_score_change():
    snapshot = SnapshotBuilder().build(
        "snap-1",
        date(2026, 5, 27),
        [_point("price_start", 100), _point("price_end", 120)],
    )
    feature = FeatureRegistry()
    feature.register(PriceMomentumFeaturePlugin(asset_id="SPY"))
    output = feature.run_enabled(snapshot, ParameterRegistry.from_yaml())[0]
    score = ScoreCalculator().calculate(output, ParameterRegistry.from_yaml(), previous_score=0.55)
    assert score.normalized_score == pytest.approx(0.7)
    assert score.smoothed_score is not None
    assert score.confidence_adjusted_score is not None
    assert score.data_quality_adjusted_score is not None
    assert score.score_change == pytest.approx(score.score - 0.55)
    assert any(reason.code == "SCORE_FLOW_APPLIED" for reason in score.reason_codes)


def test_smoothing_and_adjustment_helpers_are_bounded():
    assert ema_smooth(1.0, 0.0, 3) == 0.5
    assert confidence_adjust(1.0, 0.5) == 0.75
    assert data_quality_adjust(1.0, 0.5) == 0.75
