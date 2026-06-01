from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from api.bottleneck_data_service import get_sector_asset_mappings
from api.strategy_config import load_investment_universe, load_strategy_profile

from .bottleneck_sector_engine import BottleneckSectorEngine
from .data_ports import MacroSnapshotReader
from .macro_engine import MacroEngine, MacroRegimeDecision
from .risk_budget_engine import RiskBudgetEngine, policy_from_profile
from .sector_tilt_engine import SectorTiltEngine
from .trade_data_ports import TradeSnapshotReader
from .types import AllocationDecision, SectorBottleneckScore


class TripleAAllocator:
    """Initial dynamic allocator driven by strategy profile and universe config."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        risk_profile: str = "balanced",
        universe_id: str = "default_global",
        strategy_mode: str = "triplea_dynamic",
        macro_snapshot_reader: MacroSnapshotReader | None = None,
        trade_snapshot_reader: TradeSnapshotReader | None = None,
    ):
        self.conn = conn
        self.risk_profile = risk_profile
        self.universe_id = universe_id
        self.strategy_mode = strategy_mode
        self.macro_snapshot_reader = macro_snapshot_reader
        self.trade_snapshot_reader = trade_snapshot_reader

    @classmethod
    def from_config(
        cls,
        conn: sqlite3.Connection,
        *,
        risk_profile: str,
        universe_id: str,
        strategy_mode: str = "triplea_dynamic",
        macro_snapshot_reader: MacroSnapshotReader | None = None,
        trade_snapshot_reader: TradeSnapshotReader | None = None,
    ) -> "TripleAAllocator":
        return cls(
            conn,
            risk_profile=risk_profile,
            universe_id=universe_id,
            strategy_mode=strategy_mode,
            macro_snapshot_reader=macro_snapshot_reader,
            trade_snapshot_reader=trade_snapshot_reader,
        )

    def asset_codes(self) -> list[str]:
        universe = load_investment_universe(self.universe_id)
        return [
            asset["asset_code"]
            for asset in universe.get("assets") or []
            if asset.get("asset_code")
        ]

    def allocate(
        self,
        as_of_date: date,
        *,
        previous_weights: dict[str, float] | None = None,
    ) -> AllocationDecision:
        macro = (
            MacroEngine.from_reader(self.macro_snapshot_reader).evaluate(as_of_date)
            if self.macro_snapshot_reader is not None
            else MacroEngine().evaluate(as_of_date)
        )
        final_weights, bucket_weights, profile_reasons, bottleneck_scores, sector_scores = self._profile_weights(
            as_of_date,
            macro,
        )
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
            bottleneck_scores=bottleneck_scores,
            sector_scores=sector_scores,
            reasons=reasons,
        )

    def _profile_weights(
        self,
        as_of_date: date,
        macro: MacroRegimeDecision,
    ) -> tuple[dict[str, float], dict[str, float], list[str], dict[str, float], list[SectorBottleneckScore]]:
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
        sector_scores = BottleneckSectorEngine(
            self.conn,
            trade_snapshot_reader=self.trade_snapshot_reader,
        ).score(as_of_date)
        sector_assets = _sector_asset_codes(self.conn, assets)
        tilt_result = SectorTiltEngine().apply(
            _normalize(weights),
            sector_scores,
            sector_assets,
            asset_to_bucket,
            macro_regime=macro.regime,
        )
        risk_result = RiskBudgetEngine().apply(
            tilt_result.adjusted_weights,
            asset_to_bucket,
            policy_from_profile(profile),
        )
        return (
            risk_result.adjusted_weights,
            risk_result.bucket_weights,
            [*tilt_result.reasons, *risk_result.reasons],
            {score.sector_code: score.total_score for score in sector_scores},
            sector_scores,
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


def _sector_asset_codes(
    conn: sqlite3.Connection,
    assets: list[dict[str, Any]],
) -> dict[str, list[str]]:
    mappings = get_sector_asset_mappings(conn)
    configured = {
        sector: [item.asset_code for item in items]
        for sector, items in mappings.items()
    }
    for asset in assets:
        sector = asset.get("sector")
        asset_code = asset.get("asset_code")
        if sector and asset_code:
            configured.setdefault(sector, [])
            if asset_code not in configured[sector]:
                configured[sector].append(asset_code)
    return configured


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
