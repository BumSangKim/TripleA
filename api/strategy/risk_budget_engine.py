from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskBucketRule:
    target: float
    min: float
    max: float


@dataclass(frozen=True)
class RiskBudgetPolicy:
    buckets: dict[str, RiskBucketRule]


@dataclass(frozen=True)
class RiskBudgetResult:
    adjusted_weights: dict[str, float]
    bucket_weights: dict[str, float]
    violations: list[str]
    reasons: list[str]


class RiskBudgetEngine:
    def apply(
        self,
        asset_weights: dict[str, float],
        asset_to_bucket: dict[str, str],
        policy: RiskBudgetPolicy,
    ) -> RiskBudgetResult:
        weights = _normalize_with_zero_assets(asset_weights, asset_to_bucket)
        bucket_weights = _sum_bucket_weights(weights, asset_to_bucket)
        desired_buckets, violations, reasons = _clamp_bucket_weights(bucket_weights, policy)
        adjusted = _rebalance_assets_to_buckets(weights, asset_to_bucket, desired_buckets)
        adjusted_bucket_weights = _sum_bucket_weights(adjusted, asset_to_bucket)
        return RiskBudgetResult(
            adjusted_weights=adjusted,
            bucket_weights=adjusted_bucket_weights,
            violations=violations,
            reasons=reasons,
        )


def policy_from_profile(profile: dict) -> RiskBudgetPolicy:
    buckets = {
        name: RiskBucketRule(
            target=float(rule["target"]),
            min=float(rule["min"]),
            max=float(rule["max"]),
        )
        for name, rule in (profile.get("buckets") or {}).items()
    }
    return RiskBudgetPolicy(buckets=buckets)


def _normalize_with_zero_assets(
    asset_weights: dict[str, float],
    asset_to_bucket: dict[str, str],
) -> dict[str, float]:
    weights = {
        asset_code: max(float(asset_weights.get(asset_code, 0.0)), 0.0)
        for asset_code in set(asset_weights) | set(asset_to_bucket)
    }
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("asset weights must contain at least one positive value")
    return {asset_code: weight / total for asset_code, weight in weights.items()}


def _sum_bucket_weights(
    weights: dict[str, float],
    asset_to_bucket: dict[str, str],
) -> dict[str, float]:
    bucket_weights: dict[str, float] = {}
    for asset_code, weight in weights.items():
        bucket = asset_to_bucket.get(asset_code)
        if not bucket:
            continue
        bucket_weights[bucket] = bucket_weights.get(bucket, 0.0) + weight
    return bucket_weights


def _clamp_bucket_weights(
    bucket_weights: dict[str, float],
    policy: RiskBudgetPolicy,
) -> tuple[dict[str, float], list[str], list[str]]:
    desired = {
        bucket: bucket_weights.get(bucket, 0.0)
        for bucket in policy.buckets
    }
    violations: list[str] = []
    reasons: list[str] = []

    for bucket, rule in policy.buckets.items():
        original = desired.get(bucket, 0.0)
        if original < rule.min:
            desired[bucket] = rule.min
            violations.append(f"{bucket} below min")
            reasons.append(f"{bucket} raised to min {rule.min:.4f}")
        elif original > rule.max:
            desired[bucket] = rule.max
            violations.append(f"{bucket} above max")
            reasons.append(f"{bucket} lowered to max {rule.max:.4f}")

    for _ in range(20):
        total = sum(desired.values())
        if abs(total - 1.0) <= 1e-10:
            break
        if total > 1.0:
            excess = total - 1.0
            slack = {
                bucket: max(weight - policy.buckets[bucket].min, 0.0)
                for bucket, weight in desired.items()
            }
            _redistribute(desired, slack, -excess)
        else:
            deficit = 1.0 - total
            slack = {
                bucket: max(policy.buckets[bucket].max - weight, 0.0)
                for bucket, weight in desired.items()
            }
            _redistribute(desired, slack, deficit)

    total = sum(desired.values())
    if total > 0:
        desired = {bucket: weight / total for bucket, weight in desired.items()}
    return desired, violations, reasons


def _redistribute(
    desired: dict[str, float],
    slack: dict[str, float],
    amount: float,
) -> None:
    total_slack = sum(slack.values())
    if total_slack <= 0:
        return
    for bucket, available in slack.items():
        if available <= 0:
            continue
        desired[bucket] += amount * (available / total_slack)


def _rebalance_assets_to_buckets(
    weights: dict[str, float],
    asset_to_bucket: dict[str, str],
    desired_buckets: dict[str, float],
) -> dict[str, float]:
    assets_by_bucket: dict[str, list[str]] = {}
    for asset_code, bucket in asset_to_bucket.items():
        assets_by_bucket.setdefault(bucket, []).append(asset_code)

    current_buckets = _sum_bucket_weights(weights, asset_to_bucket)
    adjusted: dict[str, float] = {}
    for bucket, bucket_weight in desired_buckets.items():
        asset_codes = assets_by_bucket.get(bucket, [])
        if not asset_codes:
            continue
        current = current_buckets.get(bucket, 0.0)
        if current > 0:
            for asset_code in asset_codes:
                adjusted[asset_code] = weights.get(asset_code, 0.0) * bucket_weight / current
        else:
            each = bucket_weight / len(asset_codes)
            for asset_code in asset_codes:
                adjusted[asset_code] = each

    return _normalize_positive(adjusted)


def _normalize_positive(weights: dict[str, float]) -> dict[str, float]:
    positive = {
        asset_code: weight
        for asset_code, weight in weights.items()
        if weight > 0
    }
    total = sum(positive.values())
    if total <= 0:
        raise ValueError("risk budget produced no positive allocation weights")
    return {asset_code: weight / total for asset_code, weight in positive.items()}
