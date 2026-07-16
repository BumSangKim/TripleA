from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Iterable, Mapping

import yaml

from api.score_pipeline.contracts import ConservativeAction, PipelineContractError, clamp_ratio


VALID_FREQUENCIES = frozenset({"daily", "weekly", "monthly", "quarterly", "annual"})


@dataclass(frozen=True)
class NormalizationParameters:
    parameter_version: str
    model_version: str
    min_observations: int
    robust_z_clip: float
    hybrid_percentile_weight: float
    ewma_alpha_by_frequency: Mapping[str, float]
    level_weight: float
    change_weight: float

    def __post_init__(self) -> None:
        if not self.parameter_version or not self.model_version:
            raise PipelineContractError("parameter_version and model_version are required")
        if self.min_observations < 1:
            raise PipelineContractError("min_observations must be positive")
        if self.robust_z_clip <= 0:
            raise PipelineContractError("robust_z_clip must be positive")
        for value, name in (
            (self.hybrid_percentile_weight, "hybrid_percentile_weight"),
            (self.level_weight, "level_weight"),
            (self.change_weight, "change_weight"),
        ):
            if not 0.0 <= value <= 1.0:
                raise PipelineContractError(f"{name} must be in [0, 1]")
        if abs((self.level_weight + self.change_weight) - 1.0) > 1e-9:
            raise PipelineContractError("level_weight and change_weight must sum to 1")
        if not self.ewma_alpha_by_frequency:
            raise PipelineContractError("ewma_alpha_by_frequency is required")
        for frequency, alpha in self.ewma_alpha_by_frequency.items():
            if frequency not in VALID_FREQUENCIES:
                raise PipelineContractError("unsupported frequency")
            if not 0.0 < alpha <= 1.0:
                raise PipelineContractError("EWMA alpha must be in (0, 1]")


@dataclass(frozen=True)
class NormalizedSignal:
    raw_value: float | None
    percentile_score: float
    robust_z_score: float
    hybrid_score: float
    level_change_score: float
    smoothed_score: float
    confidence: float
    data_quality: float
    parameter_version: str
    model_version: str
    fallback_state: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "percentile_score",
            "robust_z_score",
            "hybrid_score",
            "level_change_score",
            "smoothed_score",
        ):
            value = getattr(self, field_name)
            if not -1.0 <= value <= 1.0:
                raise PipelineContractError(f"{field_name} must be in [-1, 1]")
        clamp_ratio(self.confidence)
        clamp_ratio(self.data_quality)
        if self.fallback_state is not None and self.fallback_state not in ConservativeAction.values():
            raise PipelineContractError("fallback_state must be conservative")


def load_normalization_parameters(path: str | Path) -> NormalizationParameters:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    metadata = raw.get("parameter_metadata") or {}
    normalization = raw.get("normalization") or {}
    smoothing = raw.get("smoothing") or {}
    composition = raw.get("level_change_composition") or {}
    try:
        return NormalizationParameters(
            parameter_version=str(metadata["parameter_version"]),
            model_version=str(metadata["model_version"]),
            min_observations=int(normalization["min_observations"]),
            robust_z_clip=float(normalization["robust_z_clip"]),
            hybrid_percentile_weight=float(normalization["hybrid_percentile_weight"]),
            ewma_alpha_by_frequency={key: float(value) for key, value in smoothing["ewma_alpha_by_frequency"].items()},
            level_weight=float(composition["level_weight"]),
            change_weight=float(composition["change_weight"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineContractError("invalid normalization parameter configuration") from exc


def normalize_signal(
    *,
    raw_value: float | None,
    history: Iterable[float | None],
    prior_normalized_scores: Iterable[float],
    frequency: str,
    data_quality: float,
    source_confidence: float,
    parameters: NormalizationParameters,
) -> NormalizedSignal:
    if frequency not in parameters.ewma_alpha_by_frequency:
        raise PipelineContractError("frequency has no configured EWMA alpha")
    usable_history = [float(value) for value in history if value is not None]
    safe_quality = clamp_ratio(data_quality)
    safe_confidence = clamp_ratio(source_confidence)
    if raw_value is None:
        return _fallback(raw_value, safe_quality, parameters, "NORMALIZATION_MISSING_OBSERVATION")
    if len(usable_history) < parameters.min_observations:
        return _fallback(raw_value, safe_quality, parameters, "NORMALIZATION_INSUFFICIENT_HISTORY")

    raw = float(raw_value)
    percentile = rolling_percentile_score(raw, usable_history)
    robust = robust_z_score(raw, usable_history, clip_at=parameters.robust_z_clip)
    hybrid = _bound(
        parameters.hybrid_percentile_weight * percentile
        + (1.0 - parameters.hybrid_percentile_weight) * robust
    )
    prior = [float(value) for value in prior_normalized_scores]
    level_change = compose_level_and_change(
        level_score=hybrid,
        prior_scores=prior,
        level_weight=parameters.level_weight,
        change_weight=parameters.change_weight,
    )
    smoothed = ewma_smooth(
        [*prior, level_change],
        alpha=parameters.ewma_alpha_by_frequency[frequency],
    )
    reasons = ["NORMALIZATION_APPLIED"]
    if len(set(usable_history)) == 1:
        reasons.append("NORMALIZATION_CONSTANT_HISTORY")
    if safe_quality < 1.0:
        reasons.append("NORMALIZATION_DEGRADED_DATA_QUALITY")
    return NormalizedSignal(
        raw_value=raw,
        percentile_score=percentile,
        robust_z_score=robust,
        hybrid_score=hybrid,
        level_change_score=level_change,
        smoothed_score=smoothed,
        confidence=clamp_ratio(safe_quality * safe_confidence),
        data_quality=safe_quality,
        parameter_version=parameters.parameter_version,
        model_version=parameters.model_version,
        reason_codes=tuple(reasons),
    )


def rolling_percentile_score(raw_value: float, history: Iterable[float]) -> float:
    values = [float(value) for value in history]
    if not values:
        raise PipelineContractError("history is required")
    less = sum(value < raw_value for value in values)
    equal = sum(value == raw_value for value in values)
    return _bound(2.0 * ((less + 0.5 * equal) / len(values)) - 1.0)


def robust_z_score(raw_value: float, history: Iterable[float], *, clip_at: float) -> float:
    values = [float(value) for value in history]
    if not values:
        raise PipelineContractError("history is required")
    if clip_at <= 0:
        raise PipelineContractError("clip_at must be positive")
    center = median(values)
    mad = median([abs(value - center) for value in values])
    if mad == 0:
        return 0.0
    z_score = (float(raw_value) - center) / (1.4826 * mad)
    return _bound(z_score / clip_at)


def ewma_smooth(values: Iterable[float], *, alpha: float) -> float:
    if not 0.0 < alpha <= 1.0:
        raise PipelineContractError("alpha must be in (0, 1]")
    series = [_bound(float(value)) for value in values]
    if not series:
        return 0.0
    smoothed = series[0]
    for value in series[1:]:
        smoothed = alpha * value + (1.0 - alpha) * smoothed
    return _bound(smoothed)


def compose_level_and_change(
    *,
    level_score: float,
    prior_scores: Iterable[float],
    level_weight: float,
    change_weight: float,
) -> float:
    if not 0.0 <= level_weight <= 1.0 or not 0.0 <= change_weight <= 1.0:
        raise PipelineContractError("composition weights must be in [0, 1]")
    if abs((level_weight + change_weight) - 1.0) > 1e-9:
        raise PipelineContractError("composition weights must sum to 1")
    prior = [_bound(float(value)) for value in prior_scores]
    change_score = 0.0 if not prior else _bound(level_score - prior[-1])
    return _bound(level_weight * _bound(level_score) + change_weight * change_score)


def _fallback(
    raw_value: float | None,
    data_quality: float,
    parameters: NormalizationParameters,
    reason_code: str,
) -> NormalizedSignal:
    return NormalizedSignal(
        raw_value=raw_value,
        percentile_score=0.0,
        robust_z_score=0.0,
        hybrid_score=0.0,
        level_change_score=0.0,
        smoothed_score=0.0,
        confidence=0.0,
        data_quality=data_quality,
        parameter_version=parameters.parameter_version,
        model_version=parameters.model_version,
        fallback_state=ConservativeAction.REVIEW_REQUIRED,
        reason_codes=(reason_code, "NORMALIZATION_REVIEW_REQUIRED"),
    )


def _bound(value: float) -> float:
    return max(-1.0, min(1.0, value))
