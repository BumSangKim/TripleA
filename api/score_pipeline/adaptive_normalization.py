from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from statistics import median
from typing import Iterable

from api.score_pipeline.adaptive import (
    AdaptiveCalibrationReport,
    AdaptiveCalibrationWindow,
    AdaptiveNormalizationConfig,
    AdaptiveNormalizationMethod,
    AdaptiveNormalizedValue,
)
from api.score_pipeline.contracts import ConservativeAction, PipelineContractError, clamp_ratio


AI_CAPEX_TOKEN_ADAPTIVE_FEATURES = frozenset(
    {
        "token_delta",
        "capex_growth_rate",
        "capex_acceleration",
        "fcf_margin_change",
        "backlog_growth",
        "asp_change",
        "hbm_asp_change",
        "supply_growth",
        "inventory_change",
        "valuation_burden",
        "macro_stress",
    }
)


@dataclass(frozen=True)
class AdaptiveNormalizationObservation:
    feature_name: str
    observed_on: date
    value: float
    available_at: datetime

    def __post_init__(self) -> None:
        if self.feature_name not in AI_CAPEX_TOKEN_ADAPTIVE_FEATURES:
            raise PipelineContractError("feature_name is not allowed for AI Capex-Token adaptive normalization")
        if self.observed_on is None:
            raise PipelineContractError("observed_on is required")
        if self.available_at is None:
            raise PipelineContractError("available_at is required")
        float(self.value)


def normalize_adaptive_feature(
    *,
    feature_name: str,
    raw_value: float | None,
    observations: Iterable[AdaptiveNormalizationObservation],
    decision_date: date,
    config: AdaptiveNormalizationConfig,
    confidence: float = 1.0,
    data_quality: float = 1.0,
    winsorization_pct: float = 0.0,
) -> AdaptiveNormalizedValue:
    if feature_name not in AI_CAPEX_TOKEN_ADAPTIVE_FEATURES:
        raise PipelineContractError("feature_name is not allowed for AI Capex-Token adaptive normalization")
    if decision_date is None:
        raise PipelineContractError("decision_date is required")
    if not 0.0 <= winsorization_pct < 0.5:
        raise PipelineContractError("winsorization_pct must be between 0 and 0.5")
    safe = _available_fit_observations(
        observations,
        feature_name=feature_name,
        decision_date=decision_date,
        lookback_months=config.lookback_months,
    )
    window = _calibration_window(safe, decision_date, config)
    report = AdaptiveCalibrationReport.from_window(config, window)
    if raw_value is None or not report.is_usable:
        return AdaptiveNormalizedValue(
            raw_value=raw_value,
            normalized_value=0.5,
            method=config.method,
            calibration_report=report,
            confidence=0.0,
            data_quality=clamp_ratio(data_quality),
            parameter_version=config.parameter_version,
            model_version=config.model_version,
            fallback_state=ConservativeAction.REVIEW_REQUIRED,
            reason_codes=(*report.reason_codes, "ADAPTIVE_NORMALIZATION_REVIEW_REQUIRED"),
            warnings=report.warnings,
        )

    values = _winsorized([point.value for point in safe], winsorization_pct=winsorization_pct)
    normalized = _normalize(float(raw_value), values, config.method)
    return AdaptiveNormalizedValue(
        raw_value=float(raw_value),
        normalized_value=normalized,
        method=config.method,
        calibration_report=report,
        confidence=clamp_ratio(confidence),
        data_quality=clamp_ratio(data_quality),
        parameter_version=config.parameter_version,
        model_version=config.model_version,
        reason_codes=("ADAPTIVE_NORMALIZATION_APPLIED",),
        warnings=report.warnings,
    )


def _available_fit_observations(
    observations: Iterable[AdaptiveNormalizationObservation],
    *,
    feature_name: str,
    decision_date: date,
    lookback_months: int,
) -> list[AdaptiveNormalizationObservation]:
    fit_start = decision_date - timedelta(days=lookback_months * 31)
    return sorted(
        (
            point
            for point in observations
            if point.feature_name == feature_name
            and fit_start <= point.observed_on <= decision_date
            and point.available_at.date() <= decision_date
        ),
        key=lambda point: point.observed_on,
    )


def _calibration_window(
    observations: list[AdaptiveNormalizationObservation],
    decision_date: date,
    config: AdaptiveNormalizationConfig,
) -> AdaptiveCalibrationWindow:
    if observations:
        fit_start = observations[0].observed_on
        fit_end = observations[-1].observed_on
    else:
        fit_start = decision_date
        fit_end = decision_date
    return AdaptiveCalibrationWindow(
        fit_start_date=fit_start,
        fit_end_date=fit_end,
        decision_date=decision_date,
        observation_count=len(observations),
        available_at_cutoff=datetime.combine(decision_date, time.max),
        parameter_version=config.parameter_version,
        model_version=config.model_version,
    )


def _normalize(raw_value: float, values: list[float], method: AdaptiveNormalizationMethod) -> float:
    if method == AdaptiveNormalizationMethod.ROLLING_PERCENTILE:
        return _percentile_score(raw_value, values)
    if method in {AdaptiveNormalizationMethod.ROBUST_ZSCORE, AdaptiveNormalizationMethod.ROLLING_Z_SCORE}:
        return _robust_zscore_score(raw_value, values)
    if method == AdaptiveNormalizationMethod.HYBRID_PERCENTILE_ZSCORE:
        return clamp_ratio((_percentile_score(raw_value, values) + _robust_zscore_score(raw_value, values)) / 2.0)
    if method == AdaptiveNormalizationMethod.ROBUST_PERCENTILE:
        return _percentile_score(raw_value, values)
    raise PipelineContractError("unsupported adaptive normalization method")


def _percentile_score(raw_value: float, values: list[float]) -> float:
    less = sum(1 for value in values if value < raw_value)
    equal = sum(1 for value in values if value == raw_value)
    return clamp_ratio((less + 0.5 * equal) / len(values))


def _robust_zscore_score(raw_value: float, values: list[float]) -> float:
    center = median(values)
    deviations = [abs(value - center) for value in values]
    mad = median(deviations)
    if mad <= 0:
        return 0.5
    robust_z = (raw_value - center) / (1.4826 * mad)
    return clamp_ratio(0.5 + robust_z / 6.0)


def _winsorized(values: list[float], *, winsorization_pct: float) -> list[float]:
    if not values or winsorization_pct <= 0:
        return list(values)
    ordered = sorted(values)
    lower_index = min(len(ordered) - 1, int(len(ordered) * winsorization_pct))
    upper_index = max(0, len(ordered) - 1 - lower_index)
    lower = ordered[lower_index]
    upper = ordered[upper_index]
    return [min(max(value, lower), upper) for value in values]
