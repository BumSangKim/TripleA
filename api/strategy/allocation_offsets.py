from __future__ import annotations


def apply_speed_and_friction_offsets(
    target_weights: dict[str, float],
    previous_weights: dict[str, float] | None,
    *,
    max_change_per_rebalance: float | None = None,
    target_adjustment_speed_multiplier: float = 1.0,
    rebalance_band: float = 0.0,
    high_urgency: bool = False,
) -> dict[str, float]:
    if not previous_weights:
        return _normalize(target_weights)
    adjusted = dict(previous_weights)
    cap = None if max_change_per_rebalance is None else max_change_per_rebalance * max(target_adjustment_speed_multiplier, 0.0)
    if high_urgency and cap is not None:
        cap *= 2.0
    for asset in set(target_weights) | set(previous_weights):
        previous = previous_weights.get(asset, 0.0)
        target = target_weights.get(asset, 0.0)
        delta = target - previous
        if abs(delta) < rebalance_band:
            adjusted[asset] = previous
            continue
        if cap is not None:
            delta = max(-cap, min(cap, delta))
        adjusted[asset] = max(previous + delta, 0.0)
    return _normalize(adjusted)


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(value, 0.0) for value in weights.values())
    if total <= 0:
        return weights
    return {key: max(value, 0.0) / total for key, value in weights.items() if max(value, 0.0) > 0}
