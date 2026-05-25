from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from api.strategy_config import load_investment_universe, load_strategy_profile

from .macro_engine import MacroEngine, MacroRegimeDecision
from .risk_budget_engine import RiskBudgetEngine, policy_from_profile
from .types import AllocationDecision


class TripleAAllocator:
    """Initial dynamic allocator driven by strategy profile and universe config."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        risk_profile: str = "balanced",
        universe_id: str = "default_global",
        strategy_mode: str = "triplea_dynamic",
    ):
        self.conn = conn
        self.risk_profile = risk_profile
        self.universe_id = universe_id
        self.strategy_mode = strategy_mode

    @classmethod
    def from_config(
        cls,
        conn: sqlite3.Connection,
        *,
        risk_profile: str,
        universe_id: str,
        strategy_mode: str = "triplea_dynamic",
    ) -> "TripleAAllocator":
        return cls(
            conn,
            risk_profile=risk_profile,
            universe_id=universe_id,
            strategy_mode=strategy_mode,
        )

    def asset_codes(self) -> list[str]:
        weights, _, _ = self._profile_weights(_neutral_macro())
        return [asset_code for asset_code, weight in weights.items() if weight > 0]

    def allocate(
        self,
        as_of_date: date,
        *,
        previous_weights: dict[str, float] | None = None,
    ) -> AllocationDecision:
        macro = MacroEngine(self.conn).evaluate(as_of_date)
        final_weights, bucket_weights, profile_reasons = self._profile_weights(macro)
        reasons = [
            f"macro regime {macro.regime} scored {macro.score}",
            *macro.reasons,
            "risk budget min/max constraints checked",
            "manual target weights are ignored in triplea_dynamic mode",
            "satellite sector tilts are pending bottleneck engine implementation",
            *profile_reasons,
        ]
        if previous_weights:
            turnover = sum(
                abs(final_weights.get(code, 0.0) - previous_weights.get(code, 0.0))
                for code in set(final_weights) | set(previous_weights)
            )
            reasons.append(f"estimated rebalance turnover {turnover:.4f}")

        return AllocationDecision(
            as_of_date=as_of_date,
            strategy_mode=self.strategy_mode,
            risk_profile=self.risk_profile,
            universe_id=self.universe_id,
            macro_regime=macro.regime,
            macro_score=macro.score,
            bucket_weights=bucket_weights,
            final_weights=final_weights,
            bottleneck_scores={},
            reasons=reasons,
        )

    def _profile_weights(
        self,
        macro: MacroRegimeDecision,
    ) -> tuple[dict[str, float], dict[str, float], list[str]]:
        universe = load_investment_universe(self.universe_id)
        profile = _macro_adjusted_profile(load_strategy_profile(self.risk_profile), macro.regime)
        assets = universe.get("assets") or []

        weights: dict[str, float] = {}
        for bucket, policy in (profile.get("buckets") or {}).items():
            bucket_assets = [
                asset
                for asset in assets
                if asset.get("bucket") == bucket and not asset.get("satellite", False)
            ]
            if not bucket_assets:
                bucket_assets = [
                    asset
                    for asset in assets
                    if asset.get("bucket") == bucket
                ]
            self._assign_bucket(weights, bucket_assets, float(policy["target"]))

        asset_to_bucket = _asset_to_bucket(assets)
        risk_result = RiskBudgetEngine().apply(
            _normalize(weights),
            asset_to_bucket,
            policy_from_profile(profile),
        )
        return (
            risk_result.adjusted_weights,
            risk_result.bucket_weights,
            risk_result.reasons,
        )

    def _assign_bucket(
        self,
        weights: dict[str, float],
        assets: list[dict[str, Any]],
        target_weight: float,
    ) -> None:
        if not assets or target_weight <= 0:
            return
        each = target_weight / len(assets)
        for asset in assets:
            asset_code = asset.get("asset_code")
            if asset_code:
                weights[asset_code] = weights.get(asset_code, 0.0) + each


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    positive = {code: weight for code, weight in weights.items() if weight > 0}
    total = sum(positive.values())
    if total <= 0:
        raise ValueError("strategy profile produced no positive allocation weights")
    return {code: weight / total for code, weight in positive.items()}


def _asset_to_bucket(assets: list[dict[str, Any]]) -> dict[str, str]:
    return {
        asset.get("asset_code"): asset.get("bucket")
        for asset in assets
        if asset.get("asset_code") and asset.get("bucket")
    }


def _macro_adjusted_profile(profile: dict[str, Any], macro_regime: str) -> dict[str, Any]:
    buckets = {
        name: dict(rule)
        for name, rule in (profile.get("buckets") or {}).items()
    }
    adjusted = {"buckets": buckets}
    if macro_regime == "risk_off":
        _shift_bucket_weight(buckets, "AGGRESSIVE_ALPHA", "DEFENSIVE_CORE", 0.10)
        _shift_bucket_weight(buckets, "AGGRESSIVE_ALPHA", "LIQUIDITY", 0.05)
    elif macro_regime == "cautious":
        _shift_bucket_weight(buckets, "AGGRESSIVE_ALPHA", "DEFENSIVE_CORE", 0.03)
        _shift_bucket_weight(buckets, "AGGRESSIVE_ALPHA", "LIQUIDITY", 0.02)
    elif macro_regime == "risk_on":
        _shift_bucket_weight(buckets, "DEFENSIVE_CORE", "AGGRESSIVE_ALPHA", 0.03)
        _shift_bucket_weight(buckets, "LIQUIDITY", "AGGRESSIVE_ALPHA", 0.02)
    return adjusted


def _shift_bucket_weight(
    buckets: dict[str, dict[str, float]],
    source: str,
    destination: str,
    requested_amount: float,
) -> None:
    source_rule = buckets.get(source)
    destination_rule = buckets.get(destination)
    if not source_rule or not destination_rule:
        return
    available = max(float(source_rule["target"]) - float(source_rule["min"]), 0.0)
    capacity = max(float(destination_rule["max"]) - float(destination_rule["target"]), 0.0)
    amount = min(requested_amount, available, capacity)
    if amount <= 0:
        return
    source_rule["target"] = float(source_rule["target"]) - amount
    destination_rule["target"] = float(destination_rule["target"]) + amount


def _neutral_macro() -> MacroRegimeDecision:
    return MacroRegimeDecision(
        as_of_date=date.min,
        regime="neutral",
        score=50,
        indicators={},
        reasons=[],
    )
