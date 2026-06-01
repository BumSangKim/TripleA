from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from statistics import NormalDist
from typing import Any

import yaml

from api.strategy.data_ports import StrategyScoreStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCORE_DEFINITIONS_PATH = PROJECT_ROOT / "config" / "score_definitions.yaml"
DEFAULT_EVENT_PROFILES_PATH = PROJECT_ROOT / "config" / "score_event_profiles.yaml"
SUPPORTED_NORMALIZATION_METHODS = {
    "min_max",
    "bounded_linear",
    "z_score",
    "percentile",
    "inverse_percentile",
    "neutral_band",
}
SUPPORTED_DIRECTIONS = {
    "higher_is_better",
    "higher_is_worse",
    "lower_is_better",
    "lower_is_worse",
    "neutral_band",
}
SCORE_TYPES = {"atomic", "composite", "penalty", "quality", "confidence"}
SUBJECT_TYPES = {"macro", "sector", "asset", "account", "portfolio"}


class ScoreLayerError(ValueError):
    pass


@dataclass(frozen=True)
class ScoreDefinition:
    score_key: str
    score_type: str
    subject_type: str
    subject_id: str
    source_plugin_id: str
    source_feature_key: str
    normalization_method: str
    normalization_params: dict[str, Any] = field(default_factory=dict)
    direction: str = "higher_is_better"
    smoothing_method: str = "ema"
    base_span: int = 5
    min_span: int = 1
    max_span: int = 20
    confidence_params: dict[str, Any] = field(default_factory=dict)
    data_quality_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    parameter_version: str = "phase5_v1"
    model_version: str = "score_layer_v1"

    def __post_init__(self) -> None:
        for name in ("score_key", "subject_id", "source_plugin_id", "source_feature_key", "parameter_version", "model_version"):
            _require_text(getattr(self, name), name)
        if self.score_type not in SCORE_TYPES:
            raise ScoreLayerError(f"score_type must be one of {sorted(SCORE_TYPES)}")
        if self.subject_type not in SUBJECT_TYPES:
            raise ScoreLayerError(f"subject_type must be one of {sorted(SUBJECT_TYPES)}")
        if self.normalization_method not in SUPPORTED_NORMALIZATION_METHODS:
            raise ScoreLayerError(f"unsupported normalization method: {self.normalization_method}")
        if self.direction not in SUPPORTED_DIRECTIONS:
            raise ScoreLayerError(f"unsupported direction: {self.direction}")
        _validate_spans(self.base_span, self.min_span, self.max_span)


@dataclass(frozen=True)
class ScoreInput:
    score_key: str
    raw_value: float | None
    as_of_date: date
    source_plugin_id: str
    source_feature_key: str
    feature_snapshot_id: str
    data_quality: float = 1.0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("score_key", "source_plugin_id", "source_feature_key", "feature_snapshot_id"):
            _require_text(getattr(self, name), name)
        if self.as_of_date is None:
            raise ScoreLayerError("as_of_date is required")
        _require_ratio(self.data_quality, "data_quality")
        _require_ratio(self.confidence, "confidence")


@dataclass(frozen=True)
class ScoreOutput:
    score_key: str
    score_type: str
    subject_type: str
    subject_id: str
    raw_value: float | None
    normalized_score: float
    smoothed_score: float
    confidence_adjusted_score: float
    decision_score: float
    previous_score: float | None
    score_change: float
    confidence: float
    data_quality: float
    stability: float
    smoothing_method: str
    base_span: int
    effective_span: int
    span_override_applied: bool
    span_override_reason: str | None
    event_profile: str
    override_expires_at: date | None
    reason_codes: list[str]
    warnings: list[str]
    as_of_date: date
    source_plugin_id: str
    source_feature_key: str
    feature_snapshot_id: str
    parameter_version: str
    model_version: str

    def __post_init__(self) -> None:
        for name in ("score_key", "subject_id", "source_plugin_id", "source_feature_key", "feature_snapshot_id"):
            _require_text(getattr(self, name), name)
        for name in ("normalized_score", "smoothed_score", "confidence_adjusted_score", "decision_score", "confidence", "data_quality", "stability"):
            _require_ratio(getattr(self, name), name)
        _validate_spans(self.base_span, min(self.base_span, self.effective_span), max(self.base_span, self.effective_span))


@dataclass(frozen=True)
class SmoothingOverride:
    score_key: str
    event_profile: str
    override_span: int
    reason: str
    valid_from: date | None = None
    valid_to: date | None = None
    approved: bool = False
    min_span: int = 1
    max_span: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.score_key, "score_key")
        _require_text(self.event_profile, "event_profile")
        _require_text(self.reason, "reason")
        _validate_spans(self.override_span, self.min_span, self.max_span)
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ScoreLayerError("valid_from must not be after valid_to")

    def active_on(self, as_of_date: date) -> bool:
        if not self.approved:
            return False
        if self.valid_from and as_of_date < self.valid_from:
            return False
        if self.valid_to and as_of_date > self.valid_to:
            return False
        return True


@dataclass(frozen=True)
class NormalizationResult:
    score: float
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpanResolution:
    effective_span: int
    override_applied: bool
    reason: str | None
    expires_at: date | None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreRunSummary:
    run_id: str
    as_of_date: date
    feature_snapshot_id: str
    event_profile: str
    count_total: int
    count_success: int
    count_warning: int
    count_failed: int
    warnings: list[str]
    status: str


def load_score_definitions(path: str | Path = DEFAULT_SCORE_DEFINITIONS_PATH) -> dict[str, ScoreDefinition]:
    data = _load_yaml(path)
    definitions: dict[str, ScoreDefinition] = {}
    for score_key, raw in (data.get("scores") or {}).items():
        normalization = raw.get("normalization") or {}
        smoothing = raw.get("smoothing") or {}
        definition = ScoreDefinition(
            score_key=raw.get("score_key") or score_key,
            score_type=raw["score_type"],
            subject_type=raw["subject_type"],
            subject_id=raw["subject_id"],
            source_plugin_id=raw["source_plugin_id"],
            source_feature_key=raw["source_feature_key"],
            normalization_method=normalization["method"],
            normalization_params=normalization.get("params") or {},
            direction=normalization.get("direction", raw.get("direction", "higher_is_better")),
            smoothing_method=smoothing.get("method", "ema"),
            base_span=int(smoothing.get("base_span", 5)),
            min_span=int(smoothing.get("min_span", 1)),
            max_span=int(smoothing.get("max_span", 20)),
            confidence_params=raw.get("confidence") or {},
            data_quality_params=raw.get("data_quality") or {},
            enabled=bool(raw.get("enabled", True)),
            parameter_version=raw.get("parameter_version", "phase5_v1"),
            model_version=raw.get("model_version", "score_layer_v1"),
        )
        definitions[definition.score_key] = definition
    if not definitions:
        raise ScoreLayerError("score definitions config must contain at least one score")
    return definitions


def load_event_profiles(path: str | Path = DEFAULT_EVENT_PROFILES_PATH) -> dict[str, dict[str, Any]]:
    data = _load_yaml(path)
    profiles = data.get("event_profiles") or {}
    if "normal" not in profiles:
        raise ScoreLayerError("event profiles must include normal")
    for profile_name, profile in profiles.items():
        adjustments = profile.get("span_adjustments") or {}
        for score_key, span in adjustments.items():
            span = int(span)
            if span <= 0:
                raise ScoreLayerError(f"span adjustment for {profile_name}/{score_key} must be positive")
            if profile_name == "black_swan_watch" and _is_buy_intensity_score(score_key) and span < 5:
                raise ScoreLayerError("black_swan_watch must not make buy-intensity/opportunity scores aggressively responsive")
    return profiles


def normalize_score(definition: ScoreDefinition, raw_value: float | None) -> NormalizationResult:
    if raw_value is None:
        return NormalizationResult(0.5, ["MISSING_FEATURE_DATA", "FALLBACK_TO_NEUTRAL"], ["REVIEW_REQUIRED"])
    try:
        value = float(raw_value)
        params = definition.normalization_params
        method = definition.normalization_method
        if method == "min_max":
            score = _linear(value, float(params["min_value"]), float(params["max_value"]))
        elif method == "bounded_linear":
            score = _linear(value, float(params["lower_bound"]), float(params["upper_bound"]))
        elif method == "z_score":
            std = float(params.get("std", 0))
            if std <= 0:
                raise ScoreLayerError("z_score std must be positive")
            score = NormalDist().cdf((value - float(params.get("mean", 0))) / std)
        elif method in {"percentile", "inverse_percentile"}:
            score = _percentile(value, params)
            if method == "inverse_percentile":
                score = 1.0 - score
        elif method == "neutral_band":
            score = _neutral_band(value, params)
        else:
            raise ScoreLayerError(f"unsupported normalization method: {method}")
    except (KeyError, TypeError, ValueError, ScoreLayerError) as exc:
        return NormalizationResult(0.5, [f"NORMALIZATION_FAILED:{exc}", "FALLBACK_TO_NEUTRAL"], ["REVIEW_REQUIRED"])

    if definition.direction in {"higher_is_worse", "lower_is_better"} and definition.normalization_method not in {"inverse_percentile", "neutral_band"}:
        score = 1.0 - score
    return NormalizationResult(_clamp(score), [], [])


def ema_smooth(current_value: float, previous_ema: float | None, span: int) -> float:
    if span <= 0:
        raise ScoreLayerError("EMA span must be positive")
    current = _clamp(current_value)
    if previous_ema is None:
        return current
    alpha = 2.0 / (span + 1.0)
    return _clamp(alpha * current + (1.0 - alpha) * _clamp(previous_ema))


def resolve_effective_span(
    definition: ScoreDefinition,
    event_profiles: dict[str, dict[str, Any]],
    event_profile: str,
    manual_override: SmoothingOverride | None,
    as_of_date: date,
) -> SpanResolution:
    warnings: list[str] = []
    selected_span = definition.base_span
    reason: str | None = None
    expires_at: date | None = None
    profile = event_profiles.get(event_profile)
    if profile is None:
        warnings.append("UNKNOWN_EVENT_PROFILE_FALLBACK_TO_NORMAL")
        profile = event_profiles.get("normal", {})
        event_profile = "normal"
    profile_adjustments = profile.get("span_adjustments") or {}
    if definition.score_key in profile_adjustments:
        selected_span = int(profile_adjustments[definition.score_key])
        reason = f"event_profile:{event_profile}"
    if manual_override and manual_override.score_key == definition.score_key:
        if manual_override.active_on(as_of_date):
            selected_span = manual_override.override_span
            reason = manual_override.reason
            expires_at = manual_override.valid_to
        else:
            warnings.append("IGNORED_INACTIVE_SPAN_OVERRIDE")
    effective = max(definition.min_span, min(definition.max_span, int(selected_span)))
    return SpanResolution(
        effective_span=effective,
        override_applied=effective != definition.base_span,
        reason=reason if effective != definition.base_span else None,
        expires_at=expires_at,
        warnings=warnings,
    )


def apply_confidence_and_quality(
    smoothed_score: float,
    confidence: float,
    data_quality: float,
    *,
    min_quality: float = 0.0,
    neutral: float = 0.5,
) -> tuple[float, float, list[str]]:
    warnings: list[str] = []
    if confidence < 0.5:
        warnings.append("LOW_CONFIDENCE")
    if data_quality < min_quality:
        warnings.extend(["LOW_DATA_QUALITY", "REVIEW_REQUIRED"])
    confidence_adjusted = _clamp(neutral + (_clamp(smoothed_score) - neutral) * _clamp(confidence))
    decision = _clamp(neutral + (confidence_adjusted - neutral) * _clamp(data_quality))
    return confidence_adjusted, decision, warnings


class ScoreRunner:
    def __init__(
        self,
        definitions: dict[str, ScoreDefinition],
        event_profiles: dict[str, dict[str, Any]],
        store: StrategyScoreStore | None = None,
    ):
        self.definitions = definitions
        self.event_profiles = event_profiles
        self.store = store

    def run(
        self,
        *,
        as_of_date: date,
        feature_snapshot_id: str,
        feature_values: dict[str, ScoreInput | float | None],
        event_profile: str = "normal",
        manual_overrides: list[SmoothingOverride] | None = None,
        parameter_version: str | None = None,
        model_version: str | None = None,
    ) -> tuple[ScoreRunSummary, list[ScoreOutput]]:
        run_id = str(uuid.uuid4())
        outputs: list[ScoreOutput] = []
        run_warnings: list[str] = []
        override_by_score = {override.score_key: override for override in manual_overrides or []}
        enabled_definitions = [definition for definition in self.definitions.values() if definition.enabled]
        for definition in enabled_definitions:
            score_input = _resolve_score_input(definition, feature_values, as_of_date, feature_snapshot_id)
            normalized = normalize_score(definition, score_input.raw_value)
            previous_score = self.store.lookup_previous_score(definition.score_key, definition.subject_type, definition.subject_id, as_of_date) if self.store else None
            span = resolve_effective_span(definition, self.event_profiles, event_profile, override_by_score.get(definition.score_key), as_of_date)
            smoothed = ema_smooth(normalized.score, previous_score, span.effective_span)
            confidence = min(_clamp(score_input.confidence), _clamp(float(definition.confidence_params.get("default", 1.0))))
            data_quality = _clamp(score_input.data_quality)
            confidence_adjusted, decision, adjustment_warnings = apply_confidence_and_quality(
                smoothed,
                confidence,
                data_quality,
                min_quality=float(definition.data_quality_params.get("min_required", 0.0)),
            )
            prev_for_change = decision if previous_score is None else previous_score
            score_change = decision - prev_for_change
            warnings = [*normalized.warnings, *span.warnings, *adjustment_warnings]
            if previous_score is None:
                warnings.append("NO_PREVIOUS_SCORE")
            output = ScoreOutput(
                score_key=definition.score_key,
                score_type=definition.score_type,
                subject_type=definition.subject_type,
                subject_id=definition.subject_id,
                raw_value=score_input.raw_value,
                normalized_score=normalized.score,
                smoothed_score=smoothed,
                confidence_adjusted_score=confidence_adjusted,
                decision_score=decision,
                previous_score=previous_score,
                score_change=score_change,
                confidence=confidence,
                data_quality=data_quality,
                stability=_clamp(1.0 - abs(score_change)),
                smoothing_method=definition.smoothing_method,
                base_span=definition.base_span,
                effective_span=span.effective_span,
                span_override_applied=span.override_applied,
                span_override_reason=span.reason,
                event_profile=event_profile if event_profile in self.event_profiles else "normal",
                override_expires_at=span.expires_at,
                reason_codes=[*normalized.reason_codes],
                warnings=warnings,
                as_of_date=as_of_date,
                source_plugin_id=definition.source_plugin_id,
                source_feature_key=definition.source_feature_key,
                feature_snapshot_id=score_input.feature_snapshot_id,
                parameter_version=parameter_version or definition.parameter_version,
                model_version=model_version or definition.model_version,
            )
            outputs.append(output)
            run_warnings.extend(warnings)
            if self.store:
                self.store.insert_value(run_id, output)
        status = "WARNING" if run_warnings else "SUCCESS"
        summary = ScoreRunSummary(
            run_id=run_id,
            as_of_date=as_of_date,
            feature_snapshot_id=feature_snapshot_id,
            event_profile=event_profile if event_profile in self.event_profiles else "normal",
            count_total=len(enabled_definitions),
            count_success=sum(1 for output in outputs if not output.warnings),
            count_warning=sum(1 for output in outputs if output.warnings),
            count_failed=0,
            warnings=sorted(set(run_warnings)),
            status=status,
        )
        if self.store:
            version_definition = enabled_definitions[0] if enabled_definitions else None
            self.store.create_run(
                run_id,
                feature_snapshot_id,
                as_of_date,
                summary.event_profile,
                parameter_version or (version_definition.parameter_version if version_definition else "phase5_v1"),
                model_version or (version_definition.model_version if version_definition else "score_layer_v1"),
                status,
                summary.warnings,
            )
        return summary, outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the TripleA score layer safely without generating orders.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--feature-snapshot-id", required=True)
    parser.add_argument("--event-profile", default="normal")
    parser.add_argument("--features-json", default="{}")
    args = parser.parse_args(argv)
    definitions = load_score_definitions()
    profiles = load_event_profiles()
    raw_features = json.loads(args.features_json)
    summary, outputs = ScoreRunner(definitions, profiles).run(
        as_of_date=date.fromisoformat(args.as_of_date),
        feature_snapshot_id=args.feature_snapshot_id,
        event_profile=args.event_profile,
        feature_values=raw_features,
    )
    print(json.dumps({"summary": asdict(summary), "scores": [asdict(output) for output in outputs]}, default=str, sort_keys=True))
    return 0


def _resolve_score_input(definition: ScoreDefinition, feature_values: dict[str, ScoreInput | float | None], as_of_date: date, feature_snapshot_id: str) -> ScoreInput:
    value = feature_values.get(definition.score_key, feature_values.get(definition.source_feature_key))
    if isinstance(value, ScoreInput):
        return value
    return ScoreInput(
        score_key=definition.score_key,
        raw_value=None if value is None else float(value),
        as_of_date=as_of_date,
        source_plugin_id=definition.source_plugin_id,
        source_feature_key=definition.source_feature_key,
        feature_snapshot_id=feature_snapshot_id,
        data_quality=1.0 if value is not None else 0.0,
        confidence=1.0 if value is not None else 0.0,
    )


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ScoreLayerError(f"{path} must contain a YAML mapping")
    return data


def _linear(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        raise ScoreLayerError("upper bound must be greater than lower bound")
    return _clamp((value - lower) / (upper - lower))


def _percentile(value: float, params: dict[str, Any]) -> float:
    values = params.get("reference_values") or params.get("history")
    if values:
        ordered = sorted(float(item) for item in values)
        return _clamp(sum(1 for item in ordered if item <= value) / len(ordered))
    return _linear(value, float(params["min_value"]), float(params["max_value"]))


def _neutral_band(value: float, params: dict[str, Any]) -> float:
    lower = float(params["lower_bound"])
    upper = float(params["upper_bound"])
    floor = float(params.get("floor", 0.0))
    ceiling = float(params.get("ceiling", 1.0))
    if lower > upper:
        raise ScoreLayerError("neutral_band lower_bound must be <= upper_bound")
    if lower <= value <= upper:
        return ceiling
    distance = lower - value if value < lower else value - upper
    max_distance = float(params.get("max_distance", max(abs(lower), abs(upper), 1.0)))
    return _clamp(ceiling - (ceiling - floor) * min(distance / max_distance, 1.0))


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ScoreLayerError(f"{name} must be a non-empty string")


def _require_ratio(value: float, name: str) -> None:
    if value is None or not 0.0 <= float(value) <= 1.0:
        raise ScoreLayerError(f"{name} must be between 0 and 1")


def _validate_spans(base_span: int, min_span: int, max_span: int) -> None:
    if int(min_span) <= 0 or int(base_span) <= 0 or int(max_span) <= 0:
        raise ScoreLayerError("base_span, min_span, and max_span must be positive")
    if int(min_span) > int(max_span):
        raise ScoreLayerError("min_span must be <= max_span")
    if not int(min_span) <= int(base_span) <= int(max_span):
        raise ScoreLayerError("base_span must be within min_span/max_span")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _is_buy_intensity_score(score_key: str) -> bool:
    lowered = score_key.lower()
    return "buy_intensity" in lowered or "opportunity" in lowered


if __name__ == "__main__":
    raise SystemExit(main())
