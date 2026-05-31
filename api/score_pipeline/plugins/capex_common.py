from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from api.score_pipeline.contracts import ConservativeAction


def clamp(value: float | int | None, low: float = 0.0, high: float = 1.0) -> float:
    if low > high:
        raise ValueError("low must not be greater than high")
    if value is None:
        return float(low)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(low)
    return max(float(low), min(float(high), numeric))


def safe_ratio(numerator: float | int | None, denominator: float | int | None, epsilon: float = 1e-9) -> float:
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if numerator is None or denominator is None:
        return 0.0
    denominator_value = float(denominator)
    if abs(denominator_value) <= epsilon:
        return 0.0
    return float(numerator) / denominator_value


def weighted_average(
    values: Mapping[str, float | int | None],
    weights: Mapping[str, float | int],
    missing_policy: str = "conservative",
) -> float:
    if missing_policy not in {"conservative", "ignore"}:
        raise ValueError("missing_policy must be conservative or ignore")
    total_weight = 0.0
    weighted_sum = 0.0
    for key, raw_weight in weights.items():
        weight = max(0.0, float(raw_weight))
        if weight == 0.0:
            continue
        value = values.get(key)
        if value is None:
            if missing_policy == "ignore":
                continue
            value = 0.5
        total_weight += weight
        weighted_sum += clamp(value) * weight
    if total_weight <= 0.0:
        return 0.5
    return clamp(weighted_sum / total_weight)


def score_from_z(z: float | int | None, center: float = 0.5, scale: float = 0.2) -> float:
    if scale < 0:
        raise ValueError("scale must be non-negative")
    if z is None:
        return clamp(center)
    return clamp(float(center) + float(z) * float(scale))


def conservative_score_on_missing(default: float = 0.5, confidence: float = 0.0) -> dict[str, Any]:
    return {
        "score": clamp(default),
        "confidence": clamp(confidence),
        "fallback_action": ConservativeAction.REVIEW_REQUIRED,
    }
