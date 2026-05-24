from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from api.strategy_config import load_investment_universe, load_strategy_profile

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
        weights, _ = self._profile_weights()
        return [asset_code for asset_code, weight in weights.items() if weight > 0]

    def allocate(
        self,
        as_of_date: date,
        *,
        previous_weights: dict[str, float] | None = None,
    ) -> AllocationDecision:
        final_weights, bucket_weights = self._profile_weights()
        reasons = [
            f"risk profile '{self.risk_profile}' selected bucket targets",
            "manual target weights are ignored in triplea_dynamic mode",
            "satellite sector tilts are pending bottleneck engine implementation",
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
            macro_regime="neutral",
            macro_score=50,
            bucket_weights=bucket_weights,
            final_weights=final_weights,
            bottleneck_scores={},
            reasons=reasons,
        )

    def _profile_weights(self) -> tuple[dict[str, float], dict[str, float]]:
        universe = load_investment_universe(self.universe_id)
        profile = load_strategy_profile(self.risk_profile)
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

        final_weights = _normalize(weights)
        bucket_weights = _bucket_weights(final_weights, assets)
        return final_weights, bucket_weights

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


def _bucket_weights(
    weights: dict[str, float],
    assets: list[dict[str, Any]],
) -> dict[str, float]:
    buckets_by_asset = {
        asset.get("asset_code"): asset.get("bucket")
        for asset in assets
        if asset.get("asset_code") and asset.get("bucket")
    }
    bucket_weights: dict[str, float] = {}
    for asset_code, weight in weights.items():
        bucket = buckets_by_asset.get(asset_code)
        if not bucket:
            continue
        bucket_weights[bucket] = bucket_weights.get(bucket, 0.0) + weight
    return bucket_weights
