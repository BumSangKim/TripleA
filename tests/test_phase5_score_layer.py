import sqlite3
from dataclasses import fields
from datetime import date

import pytest

from api.score_pipeline.score_store import SQLiteScoreStore
from api.strategy.score_layer import (
    ScoreDefinition,
    ScoreInput,
    ScoreLayerError,
    ScoreOutput,
    ScoreRunner,
    SmoothingOverride,
    apply_confidence_and_quality,
    ema_smooth,
    load_event_profiles,
    load_score_definitions,
    normalize_score,
    resolve_effective_span,
)


def _definition(**overrides):
    data = {
        "score_key": "momentum_score",
        "score_type": "atomic",
        "subject_type": "asset",
        "subject_id": "SMH",
        "source_plugin_id": "mock_plugin",
        "source_feature_key": "momentum_3m",
        "normalization_method": "bounded_linear",
        "normalization_params": {"lower_bound": -1, "upper_bound": 1},
        "direction": "higher_is_better",
        "base_span": 5,
        "min_span": 1,
        "max_span": 20,
        "confidence_params": {"default": 1.0},
        "data_quality_params": {"min_required": 0.7},
    }
    data.update(overrides)
    return ScoreDefinition(**data)


def test_score_contract_accepts_valid_definition():
    definition = _definition()
    assert definition.score_key == "momentum_score"


def test_score_contract_rejects_invalid_span():
    with pytest.raises(ScoreLayerError, match="base_span"):
        _definition(base_span=0)


def test_score_output_contains_smoothing_metadata():
    output = ScoreOutput(
        score_key="momentum_score",
        score_type="atomic",
        subject_type="asset",
        subject_id="SMH",
        raw_value=0.2,
        normalized_score=0.6,
        smoothed_score=0.55,
        confidence_adjusted_score=0.55,
        decision_score=0.55,
        previous_score=None,
        score_change=0,
        confidence=1,
        data_quality=1,
        stability=1,
        smoothing_method="ema",
        base_span=5,
        effective_span=2,
        span_override_applied=True,
        span_override_reason="event_profile:geopolitical_risk",
        event_profile="geopolitical_risk",
        override_expires_at=None,
        reason_codes=[],
        warnings=[],
        as_of_date=date(2026, 5, 27),
        source_plugin_id="mock_plugin",
        source_feature_key="momentum_3m",
        feature_snapshot_id="snap-1",
        parameter_version="p",
        model_version="m",
    )
    assert output.effective_span == 2


def test_score_output_bounds_scores():
    with pytest.raises(ScoreLayerError, match="decision_score"):
        ScoreOutput(
            score_key="momentum_score",
            score_type="atomic",
            subject_type="asset",
            subject_id="SMH",
            raw_value=0.2,
            normalized_score=0.6,
            smoothed_score=0.55,
            confidence_adjusted_score=0.55,
            decision_score=1.1,
            previous_score=None,
            score_change=0,
            confidence=1,
            data_quality=1,
            stability=1,
            smoothing_method="ema",
            base_span=5,
            effective_span=5,
            span_override_applied=False,
            span_override_reason=None,
            event_profile="normal",
            override_expires_at=None,
            reason_codes=[],
            warnings=[],
            as_of_date=date(2026, 5, 27),
            source_plugin_id="mock_plugin",
            source_feature_key="momentum_3m",
            feature_snapshot_id="snap-1",
            parameter_version="p",
            model_version="m",
        )


def test_load_score_definitions_and_event_profiles():
    definitions = load_score_definitions()
    profiles = load_event_profiles()
    assert "volatility_stress_score" in definitions
    assert "black_swan_watch" in profiles
    assert profiles["black_swan_watch"]["span_adjustments"]["buy_intensity_score"] >= definitions["buy_intensity_score"].base_span


def test_score_definition_requires_score_key():
    with pytest.raises(ScoreLayerError, match="score_key"):
        _definition(score_key="")


def test_min_max_normalization_and_directionality():
    result = normalize_score(_definition(normalization_method="min_max", normalization_params={"min_value": 0, "max_value": 10}), 7)
    inverse = normalize_score(_definition(normalization_method="min_max", normalization_params={"min_value": 0, "max_value": 10}, direction="higher_is_worse"), 7)
    assert result.score == 0.7
    assert inverse.score == pytest.approx(0.3)


def test_bounded_linear_normalization_clamps_values():
    result = normalize_score(_definition(), 10)
    assert result.score == 1.0


def test_percentile_and_inverse_percentile_normalization():
    percentile = normalize_score(_definition(normalization_method="percentile", normalization_params={"reference_values": [1, 2, 3, 4]}), 3)
    inverse = normalize_score(_definition(normalization_method="inverse_percentile", normalization_params={"reference_values": [1, 2, 3, 4]}), 3)
    assert percentile.score == 0.75
    assert inverse.score == 0.25


def test_neutral_band_normalization():
    result = normalize_score(_definition(normalization_method="neutral_band", normalization_params={"lower_bound": -0.1, "upper_bound": 0.1}), 0)
    assert result.score == 1.0


def test_invalid_normalization_method_fails_safely():
    with pytest.raises(ScoreLayerError):
        _definition(normalization_method="not_supported")


def test_ema_smoothing_basic():
    assert ema_smooth(1.0, 0.0, 3) == 0.5


def test_event_and_manual_span_override_resolution():
    definition = _definition()
    profiles = {"normal": {"span_adjustments": {}}, "stress": {"span_adjustments": {"momentum_score": 2}}}
    event_span = resolve_effective_span(definition, profiles, "stress", None, date(2026, 5, 27))
    manual = SmoothingOverride("momentum_score", "stress", 1, "approved manual", date(2026, 5, 1), date(2026, 5, 31), True, 1, 20)
    manual_span = resolve_effective_span(definition, profiles, "stress", manual, date(2026, 5, 27))
    expired_span = resolve_effective_span(definition, profiles, "stress", manual, date(2026, 6, 27))
    assert event_span.effective_span == 2
    assert manual_span.effective_span == 1
    assert expired_span.effective_span == 2
    assert "IGNORED_INACTIVE_SPAN_OVERRIDE" in expired_span.warnings


def test_confidence_and_data_quality_adjustment():
    confidence_adjusted, decision, warnings = apply_confidence_and_quality(1.0, 0.5, 0.5, min_quality=0.7)
    assert confidence_adjusted == 0.75
    assert decision == 0.625
    assert "LOW_DATA_QUALITY" in warnings


def test_score_persistence_roundtrip_and_previous_lookup():
    conn = sqlite3.connect(":memory:")
    store = SQLiteScoreStore(conn)
    output = ScoreOutput(
        score_key="momentum_score",
        score_type="atomic",
        subject_type="asset",
        subject_id="SMH",
        raw_value=0.2,
        normalized_score=0.6,
        smoothed_score=0.6,
        confidence_adjusted_score=0.6,
        decision_score=0.6,
        previous_score=None,
        score_change=0,
        confidence=1,
        data_quality=1,
        stability=1,
        smoothing_method="ema",
        base_span=5,
        effective_span=5,
        span_override_applied=False,
        span_override_reason=None,
        event_profile="normal",
        override_expires_at=None,
        reason_codes=["OK"],
        warnings=[],
        as_of_date=date(2026, 5, 26),
        source_plugin_id="mock_plugin",
        source_feature_key="momentum_3m",
        feature_snapshot_id="snap-1",
        parameter_version="p",
        model_version="m",
    )
    store.create_run("run-1", "snap-1", date(2026, 5, 26), "normal", "p", "m", "SUCCESS", [])
    store.insert_value("run-1", output)
    assert store.lookup_previous_score("momentum_score", "asset", "SMH", date(2026, 5, 27)) == 0.6
    assert store.values_for_run("run-1")[0]["effective_span"] == 5


def test_score_runner_processes_snapshot_and_persists_outputs():
    conn = sqlite3.connect(":memory:")
    store = SQLiteScoreStore(conn)
    definition = _definition()
    runner = ScoreRunner({"momentum_score": definition}, {"normal": {"span_adjustments": {}}, "stress": {"span_adjustments": {"momentum_score": 2}}}, store)
    summary, outputs = runner.run(
        as_of_date=date(2026, 5, 27),
        feature_snapshot_id="snap-2",
        event_profile="stress",
        feature_values={"momentum_3m": ScoreInput("momentum_score", 0.5, date(2026, 5, 27), "mock_plugin", "momentum_3m", "snap-2", 0.8, 0.9)},
    )
    assert summary.count_total == 1
    assert outputs[0].effective_span == 2
    assert outputs[0].parameter_version == "phase5_v1"
    assert store.values_for_run(summary.run_id)[0]["source_feature_key"] == "momentum_3m"


def test_phase5_missing_data_conservative_fallback_and_no_order_generation():
    runner = ScoreRunner({"momentum_score": _definition()}, {"normal": {"span_adjustments": {}}})
    _, outputs = runner.run(as_of_date=date(2026, 5, 27), feature_snapshot_id="snap-3", feature_values={})
    assert outputs[0].decision_score == 0.5
    assert "REVIEW_REQUIRED" in outputs[0].reason_codes
    blocked = {"order", "target_weight", "allocation", "broker"}
    assert not blocked.intersection({field.name for field in fields(type(outputs[0]))})
