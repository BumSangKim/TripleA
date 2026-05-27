from __future__ import annotations

from dataclasses import dataclass

from api.score_pipeline.contracts import DecisionWarning, FeatureOutput, ReasonCode, ScoreOutput, clamp_ratio
from api.score_pipeline.parameters import ParameterRegistry


def ema_smooth(current_score: float, previous_score: float | None, span: int) -> float:
    if span <= 0:
        raise ValueError("span must be positive")
    current = clamp_ratio(current_score)
    if previous_score is None:
        return current
    alpha = 2 / (span + 1)
    return clamp_ratio(alpha * current + (1 - alpha) * clamp_ratio(previous_score))


def confidence_adjust(score: float, confidence: float, neutral: float = 0.5) -> float:
    return clamp_ratio(neutral + (clamp_ratio(score) - neutral) * clamp_ratio(confidence))


def data_quality_adjust(score: float, data_quality: float, neutral: float = 0.5) -> float:
    return clamp_ratio(neutral + (clamp_ratio(score) - neutral) * clamp_ratio(data_quality))


@dataclass(frozen=True)
class ScoreCalculator:
    score_id: str = "score:price_momentum"

    def calculate(
        self,
        feature: FeatureOutput,
        registry: ParameterRegistry,
        *,
        previous_score: float | None = None,
    ) -> ScoreOutput:
        span_lookup = registry.get("ema_span", as_of_date=feature.as_of_date, expected_type=int)
        span = int(span_lookup.value) if span_lookup.value is not None else 10
        normalized = clamp_ratio(feature.normalized_value)
        smoothed = ema_smooth(normalized, previous_score, span)
        confidence_score = confidence_adjust(smoothed, feature.confidence)
        data_quality_score = data_quality_adjust(confidence_score, feature.data_quality.quality_score)
        prev = data_quality_score if previous_score is None else previous_score
        score_change = data_quality_score - prev
        warnings = [*feature.warnings, *span_lookup.warnings]
        if feature.data_quality.conservative_action:
            warnings.append(
                DecisionWarning(
                    "DATA_QUALITY_CONSERVATIVE_FALLBACK",
                    "WARNING",
                    "score",
                    feature.data_quality.conservative_action,
                )
            )
        return ScoreOutput(
            score_id=self.score_id,
            subject_id=feature.entity_id,
            subject_type=feature.entity_type,
            score=data_quality_score,
            previous_score=previous_score,
            score_change=score_change,
            confidence=feature.confidence,
            data_quality=feature.data_quality.quality_score,
            stability=clamp_ratio(1.0 - abs(score_change)),
            adjustment_intensity=clamp_ratio(abs(data_quality_score - 0.5) * feature.confidence * feature.data_quality.quality_score),
            as_of_date=feature.as_of_date,
            parameter_version=feature.parameter_version,
            model_version="score_pipeline_score_v1",
            reason_codes=[*feature.reason_codes, ReasonCode("SCORE_FLOW_APPLIED", "score")],
            warnings=warnings,
            normalized_score=normalized,
            smoothed_score=smoothed,
            confidence_adjusted_score=confidence_score,
            data_quality_adjusted_score=data_quality_score,
        )


class ScoreRegistry:
    def __init__(self):
        self._calculators: dict[str, ScoreCalculator] = {}

    def register(self, calculator: ScoreCalculator) -> None:
        self._calculators[calculator.score_id] = calculator

    def calculate_all(
        self,
        features: list[FeatureOutput],
        registry: ParameterRegistry,
        previous_scores: dict[str, float] | None = None,
    ) -> list[ScoreOutput]:
        if not self._calculators:
            self.register(ScoreCalculator())
        previous_scores = previous_scores or {}
        calculator = next(iter(self._calculators.values()))
        return [
            calculator.calculate(feature, registry, previous_score=previous_scores.get(feature.entity_id))
            for feature in features
        ]
