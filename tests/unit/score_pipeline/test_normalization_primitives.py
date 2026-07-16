from __future__ import annotations

from pathlib import Path

import pytest

from api.score_pipeline.contracts import ConservativeAction
from api.score_pipeline.normalization_primitives import (
    compose_level_and_change,
    ewma_smooth,
    load_normalization_parameters,
    normalize_signal,
    robust_z_score,
    rolling_percentile_score,
)


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "parameters" / "semiconductor_normalization.yaml"


def test_normalization_parameters_are_versioned_diagnostic_data() -> None:
    parameters = load_normalization_parameters(CONFIG_PATH)

    assert parameters.parameter_version == "semiconductor_normalization_v1"
    assert parameters.model_version == "semiconductor_normalization_diagnostic_v1"
    assert parameters.ewma_alpha_by_frequency["monthly"] == pytest.approx(0.4)


def test_scores_are_deterministic_bounded_and_outlier_resilient() -> None:
    parameters = load_normalization_parameters(CONFIG_PATH)
    result = normalize_signal(
        raw_value=5.0,
        history=[1.0, 2.0, 3.0, 4.0, 1_000_000.0],
        prior_normalized_scores=[-0.4, -0.2],
        frequency="monthly",
        data_quality=1.0,
        source_confidence=0.8,
        parameters=parameters,
    )

    assert all(-1.0 <= value <= 1.0 for value in (result.percentile_score, result.robust_z_score, result.hybrid_score, result.level_change_score, result.smoothed_score))
    assert result.confidence == pytest.approx(0.8)
    assert result.reason_codes == ("NORMALIZATION_APPLIED",)


def test_constant_history_and_short_or_missing_input_fall_back_conservatively() -> None:
    parameters = load_normalization_parameters(CONFIG_PATH)
    constant = normalize_signal(
        raw_value=2.0,
        history=[2.0] * 5,
        prior_normalized_scores=[],
        frequency="quarterly",
        data_quality=0.8,
        source_confidence=1.0,
        parameters=parameters,
    )
    short = normalize_signal(
        raw_value=2.0,
        history=[1.0, None, 2.0],
        prior_normalized_scores=[],
        frequency="quarterly",
        data_quality=1.0,
        source_confidence=1.0,
        parameters=parameters,
    )
    missing = normalize_signal(
        raw_value=None,
        history=[1.0] * 5,
        prior_normalized_scores=[],
        frequency="quarterly",
        data_quality=0.5,
        source_confidence=1.0,
        parameters=parameters,
    )

    assert constant.robust_z_score == 0.0
    assert "NORMALIZATION_CONSTANT_HISTORY" in constant.reason_codes
    for result in (short, missing):
        assert result.smoothed_score == 0.0
        assert result.confidence == 0.0
        assert result.fallback_state == ConservativeAction.REVIEW_REQUIRED


def test_primitives_bound_values_and_compose_level_and_change() -> None:
    assert rolling_percentile_score(3.0, [1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(0.0)
    assert robust_z_score(1_000_000.0, [1.0, 2.0, 3.0, 4.0, 5.0], clip_at=3.0) == 1.0
    assert ewma_smooth([-1.0, 1.0], alpha=0.25) == pytest.approx(-0.5)
    assert compose_level_and_change(level_score=0.5, prior_scores=[0.1], level_weight=0.7, change_weight=0.3) == pytest.approx(0.47)
