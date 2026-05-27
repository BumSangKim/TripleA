from __future__ import annotations

from dataclasses import dataclass

from .types import SectorBottleneckScore
from api.strategy.adaptive_offsets import AdaptiveOffsets, AdaptivePermissions, BLOCK
from api.strategy.sector_allocation_pressure import SectorAllocationPressure


@dataclass(frozen=True)
class SectorTiltPolicy:
    max_total_tilt: float = 0.15
    max_sector_tilt: float = 0.05
    emerging_sector_tilt: float = 0.02
    reduce_on_risk_off: bool = True


@dataclass(frozen=True)
class SectorTiltResult:
    adjusted_weights: dict[str, float]
    applied_tilts: dict[str, float]
    reasons: list[str]


class SectorTiltEngine:
    def apply(
        self,
        asset_weights: dict[str, float],
        sector_scores: list[SectorBottleneckScore],
        sector_assets: dict[str, list[str]],
        asset_to_bucket: dict[str, str],
        *,
        macro_regime: str = "neutral",
        policy: SectorTiltPolicy | None = None,
        sector_pressures: list[SectorAllocationPressure] | None = None,
        adaptive_offsets: AdaptiveOffsets | None = None,
        adaptive_permissions: AdaptivePermissions | None = None,
    ) -> SectorTiltResult:
        policy = policy or SectorTiltPolicy()
        if sector_pressures is not None:
            return _apply_pressure_tilts(asset_weights, sector_pressures, sector_assets, asset_to_bucket, policy, adaptive_offsets, adaptive_permissions)
        weights = dict(asset_weights)
        applied: dict[str, float] = {}
        reasons: list[str] = []
        total_tilt = 0.0

        for score in sorted(sector_scores, key=lambda item: item.total_score, reverse=True):
            sector_tilt = _tilt_for_score(score, policy)
            if sector_tilt <= 0:
                continue
            if policy.reduce_on_risk_off and macro_regime == "risk_off":
                sector_tilt *= 0.5
            sector_tilt = min(sector_tilt, policy.max_total_tilt - total_tilt)
            if sector_tilt <= 0:
                break

            target_assets = [asset for asset in sector_assets.get(score.sector_code, []) if asset in asset_to_bucket]
            if not target_assets:
                continue
            bucket = asset_to_bucket[target_assets[0]]
            donors = [
                asset
                for asset, asset_bucket in asset_to_bucket.items()
                if asset_bucket == bucket and asset not in target_assets and weights.get(asset, 0.0) > 0
            ]
            donated = _take_from_donors(weights, donors, sector_tilt)
            if donated <= 0:
                continue
            each = donated / len(target_assets)
            for asset in target_assets:
                weights[asset] = weights.get(asset, 0.0) + each
            applied[score.sector_code] = donated
            total_tilt += donated
            reasons.append(f"{score.sector_code} {score.regime} tilt +{donated:.4f}")

        return SectorTiltResult(
            adjusted_weights=_normalize(weights),
            applied_tilts=applied,
            reasons=reasons,
        )


def _tilt_for_score(score: SectorBottleneckScore, policy: SectorTiltPolicy) -> float:
    if score.regime == "active":
        return policy.max_sector_tilt
    if score.regime == "emerging":
        return min(policy.emerging_sector_tilt, policy.max_sector_tilt)
    return 0.0


def _apply_pressure_tilts(
    asset_weights: dict[str, float],
    sector_pressures: list[SectorAllocationPressure],
    sector_assets: dict[str, list[str]],
    asset_to_bucket: dict[str, str],
    policy: SectorTiltPolicy,
    adaptive_offsets: AdaptiveOffsets | None,
    adaptive_permissions: AdaptivePermissions | None,
) -> SectorTiltResult:
    weights = dict(asset_weights)
    applied: dict[str, float] = {}
    reasons: list[str] = []
    if adaptive_permissions and adaptive_permissions.sector_expansion == BLOCK:
        return SectorTiltResult(_normalize(weights), {}, ["sector expansion blocked by adaptive permission"])
    max_total = max(0.0, policy.max_total_tilt + (adaptive_offsets.risk.sector_pressure_cap_offset if adaptive_offsets else 0.0))
    max_sector = max(0.0, policy.max_sector_tilt + (adaptive_offsets.risk.single_sector_max_offset if adaptive_offsets else 0.0))
    total_tilt = 0.0
    for pressure in sorted(sector_pressures, key=lambda item: item.allocation_pressure, reverse=True):
        sector_tilt = min(max((pressure.allocation_pressure - 0.5) * 0.10, 0.0), max_sector, max_total - total_tilt)
        if sector_tilt <= 0:
            continue
        targets = [asset for asset in sector_assets.get(pressure.sector_code, []) if asset in asset_to_bucket]
        if not targets:
            continue
        bucket = asset_to_bucket[targets[0]]
        donors = [asset for asset, asset_bucket in asset_to_bucket.items() if asset_bucket == bucket and asset not in targets and weights.get(asset, 0.0) > 0]
        donated = _take_from_donors(weights, donors, sector_tilt)
        if donated <= 0:
            continue
        for asset in targets:
            weights[asset] = weights.get(asset, 0.0) + donated / len(targets)
        applied[pressure.sector_code] = donated
        total_tilt += donated
        reasons.append(f"{pressure.sector_code} pressure tilt +{donated:.4f}")
    return SectorTiltResult(_normalize(weights), applied, reasons)


def _take_from_donors(
    weights: dict[str, float],
    donors: list[str],
    requested: float,
) -> float:
    available = sum(weights.get(asset, 0.0) for asset in donors)
    amount = min(requested, available)
    if amount <= 0 or available <= 0:
        return 0.0
    for asset in donors:
        current = weights.get(asset, 0.0)
        weights[asset] = max(current - amount * (current / available), 0.0)
    return amount


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    positive = {asset: weight for asset, weight in weights.items() if weight > 0}
    total = sum(positive.values())
    if total <= 0:
        raise ValueError("sector tilt produced no positive allocation weights")
    return {asset: weight / total for asset, weight in positive.items()}
