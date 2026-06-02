from __future__ import annotations

from datetime import date, datetime

import pytest

from api.score_pipeline.adaptive import AdaptiveNormalizationConfig, AdaptiveNormalizationMethod
from api.score_pipeline.adaptive_normalization import (
    AI_CAPEX_TOKEN_ADAPTIVE_FEATURES,
    AdaptiveNormalizationObservation,
    normalize_adaptive_feature,
)
from api.score_pipeline.contracts import ConservativeAction, PipelineContractError


def test_rolling_percentile_known_example():
    value = normalize_adaptive_feature(
        feature_name="token_delta",
        raw_value=3.0,
        observations=_observations("token_delta", [1, 2, 3, 4, 5]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=5),
    )

    assert value.normalized_value == pytest.approx(0.5)
    assert value.calibration_report.observation_count == 5
    assert value.parameter_version == "adaptive-params-v1"
    assert value.model_version == "adaptive-model-v1"


def test_robust_zscore_known_examples():
    center = normalize_adaptive_feature(
        feature_name="capex_growth_rate",
        raw_value=3.0,
        observations=_observations("capex_growth_rate", [1, 2, 3, 4, 5]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROBUST_ZSCORE, min_observations=5),
    )
    high = normalize_adaptive_feature(
        feature_name="capex_growth_rate",
        raw_value=4.4826,
        observations=_observations("capex_growth_rate", [1, 2, 3, 4, 5]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROBUST_ZSCORE, min_observations=5),
    )

    assert center.normalized_value == pytest.approx(0.5)
    assert high.normalized_value == pytest.approx(2 / 3)


def test_hybrid_output_stays_in_unit_interval():
    value = normalize_adaptive_feature(
        feature_name="capex_acceleration",
        raw_value=4.0,
        observations=_observations("capex_acceleration", [1, 2, 3, 4, 5]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.HYBRID_PERCENTILE_ZSCORE, min_observations=5),
    )

    assert 0.0 <= value.normalized_value <= 1.0
    assert value.fallback_state is None


def test_decision_date_leakage_prevention_excludes_future_available_rows():
    observations = [
        *_observations("fcf_margin_change", [10, 20, 30]),
        AdaptiveNormalizationObservation(
            feature_name="fcf_margin_change",
            observed_on=date(2026, 1, 31),
            value=1000.0,
            available_at=datetime(2026, 2, 1, 0, 0, 0),
        ),
    ]

    value = normalize_adaptive_feature(
        feature_name="fcf_margin_change",
        raw_value=30.0,
        observations=observations,
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=3),
    )

    assert value.calibration_report.observation_count == 3
    assert value.normalized_value == pytest.approx((2 + 0.5) / 3)


def test_insufficient_observations_fall_back_conservatively():
    value = normalize_adaptive_feature(
        feature_name="backlog_growth",
        raw_value=1.0,
        observations=_observations("backlog_growth", [1, 2]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=5),
        confidence=0.8,
    )

    assert value.normalized_value == 0.5
    assert value.confidence == 0.0
    assert value.fallback_state == ConservativeAction.REVIEW_REQUIRED
    assert "INSUFFICIENT_ADAPTIVE_CALIBRATION_OBSERVATIONS" in value.reason_codes


def test_winsorization_limits_outlier_influence_without_fixed_market_values():
    value = normalize_adaptive_feature(
        feature_name="asp_change",
        raw_value=4.0,
        observations=_observations("asp_change", [1, 2, 3, 4, 1000]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=5),
        winsorization_pct=0.2,
    )

    assert value.normalized_value == pytest.approx(0.8)
    assert value.fallback_state is None


def test_raw_values_with_different_absolute_scales_are_comparable():
    small_scale = normalize_adaptive_feature(
        feature_name="hbm_asp_change",
        raw_value=30.0,
        observations=_observations("hbm_asp_change", [10, 20, 30, 40, 50]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=5),
    )
    large_scale = normalize_adaptive_feature(
        feature_name="hbm_asp_change",
        raw_value=300.0,
        observations=_observations("hbm_asp_change", [100, 200, 300, 400, 500]),
        decision_date=date(2026, 1, 31),
        config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=5),
    )

    assert small_scale.normalized_value == large_scale.normalized_value == pytest.approx(0.5)


def test_all_declared_ai_capex_feature_names_are_supported():
    for feature_name in AI_CAPEX_TOKEN_ADAPTIVE_FEATURES:
        value = normalize_adaptive_feature(
            feature_name=feature_name,
            raw_value=3.0,
            observations=_observations(feature_name, [1, 2, 3, 4, 5]),
            decision_date=date(2026, 1, 31),
            config=_config(AdaptiveNormalizationMethod.ROLLING_PERCENTILE, min_observations=5),
        )
        assert value.normalized_value == pytest.approx(0.5)


def test_unknown_feature_name_is_rejected():
    with pytest.raises(PipelineContractError):
        AdaptiveNormalizationObservation(
            feature_name="single_indicator_to_buy_signal",
            observed_on=date(2026, 1, 31),
            value=1.0,
            available_at=datetime(2026, 1, 31, 0, 0, 0),
        )


def _config(
    method: AdaptiveNormalizationMethod,
    *,
    min_observations: int,
) -> AdaptiveNormalizationConfig:
    return AdaptiveNormalizationConfig(
        method=method,
        lookback_periods=36,
        lookback_months=36,
        min_observations=min_observations,
        parameter_version="adaptive-params-v1",
        model_version="adaptive-model-v1",
    )


def _observations(feature_name: str, values: list[float]) -> list[AdaptiveNormalizationObservation]:
    points: list[AdaptiveNormalizationObservation] = []
    for index, raw_value in enumerate(values, start=1):
        points.append(
            AdaptiveNormalizationObservation(
                feature_name=feature_name,
                observed_on=date(2025, index, 28),
                value=float(raw_value),
                available_at=datetime(2025, index, 28, 0, 0, 0),
            )
        )
    return points
