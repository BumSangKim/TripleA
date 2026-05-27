from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    value: float
    weight: float
    contribution: float
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreSignal:
    score: float
    previous_score: float | None
    score_change: float | None
    confidence: float
    data_quality: float
    stability: float
    adjustment_intensity: float
    reason_codes: list[str]
    as_of_date: date
    parameter_version: str
    model_version: str
    components: list[ScoreComponent]


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def safe_weighted_average(components: list[ScoreComponent], neutral: float = 0.5) -> float:
    valid = [component for component in components if component.weight > 0]
    total_weight = sum(component.weight for component in valid)
    if total_weight <= 0:
        return clamp_score(neutral)
    return clamp_score(sum(clamp_score(c.value) * c.weight for c in valid) / total_weight)


def confidence_adjusted_score(score: float, confidence: float, data_quality: float, neutral: float = 0.5) -> float:
    intensity = clamp_score(confidence) * clamp_score(data_quality)
    return clamp_score(neutral + (clamp_score(score) - neutral) * intensity)


def combine_reason_codes(*groups: list[str] | tuple[str, ...] | str | None) -> list[str]:
    result: list[str] = []
    for group in groups:
        values = [group] if isinstance(group, str) else list(group or [])
        for value in values:
            if value and value not in result:
                result.append(value)
    return result
