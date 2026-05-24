from __future__ import annotations

import sqlite3

from .market_data_service import AssetUniverseItem, get_asset_universe, resolve_asset_class_to_asset_code
from .strategy.types import AllocationTarget

ASSET_CLASS_ALIASES = {
    "DOMESTIC_STOCK": "국내주식",
    "FOREIGN_STOCK": "해외주식",
    "BOND": "채권",
    "CASH": "현금",
}


class StaticTargetAllocator:
    """Map TripleA asset-class targets to concrete backtest assets."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def allocate(self, target_weights: dict[str, float]) -> list[AllocationTarget]:
        normalized = _normalize_weights(target_weights)
        assets_by_code = {
            asset.asset_code: asset
            for asset in get_asset_universe(self.conn)
        }
        result: list[AllocationTarget] = []
        for asset_class, weight in normalized.items():
            resolved_class = ASSET_CLASS_ALIASES.get(asset_class.upper(), asset_class)
            asset_code = resolve_asset_class_to_asset_code(self.conn, resolved_class)
            asset = assets_by_code.get(asset_code)
            if not asset:
                raise KeyError(f"Asset metadata is missing for {asset_code}")
            result.append(_allocation_target(asset, weight))
        return result


def _normalize_weights(target_weights: dict[str, float]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for asset_class, value in target_weights.items():
        name = (asset_class or "").strip()
        if not name:
            raise ValueError("target asset class must not be empty")
        if value < 0:
            raise ValueError("target weight must be zero or greater")
        weight = value / 100.0 if value > 1 else value
        if weight <= 0:
            continue
        weights[name] = weights.get(name, 0.0) + weight

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one positive target weight is required")
    return {asset_class: weight / total for asset_class, weight in weights.items()}


def _allocation_target(asset: AssetUniverseItem, weight: float) -> AllocationTarget:
    return AllocationTarget(
        asset_class=asset.asset_class,
        asset_code=asset.asset_code,
        currency=asset.currency,
        target_weight=weight,
    )
