from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from api.universe.loader import load_asset_master, load_yaml


SEMICONDUCTOR_SUBSECTORS = frozenset(
    {
        "memory",
        "ai_fabless",
        "foundry",
        "semiconductor_equipment",
        "analog_mcu",
        "advanced_packaging",
        "broad_semiconductor_etf",
    }
)
VALID_BENCHMARK_ROLE = "core_benchmark"
VALID_OVERLAY_ROLE = "active_overlay"
VALID_ASSET_TYPES = frozenset({"ETF", "STOCK"})


class SemiconductorUniverseError(ValueError):
    pass


@dataclass(frozen=True)
class SemiconductorBenchmark:
    benchmark_id: str
    role: str
    tradeable: bool
    asset_master_asset_id: str | None
    activation_state: str


@dataclass(frozen=True)
class SemiconductorOverlay:
    overlay_id: str
    role: str
    activation_state: str


@dataclass(frozen=True)
class SemiconductorSubsector:
    subsector_id: str
    candidate_asset_ids: tuple[str, ...]
    activation_state: str


@dataclass(frozen=True)
class SemiconductorVerticalSliceUniverse:
    version: str
    as_of_date: str
    benchmark: SemiconductorBenchmark
    active_overlay: SemiconductorOverlay
    subsectors: tuple[SemiconductorSubsector, ...]

    @property
    def candidate_asset_ids(self) -> tuple[str, ...]:
        return tuple(asset_id for subsector in self.subsectors for asset_id in subsector.candidate_asset_ids)


def load_semiconductor_vertical_slice(
    *,
    config_path: str | Path = "config/universe/semiconductor_vertical_slice.yml",
    asset_master_path: str | Path = "config/universe/asset_master.yml",
) -> SemiconductorVerticalSliceUniverse:
    raw = load_yaml(config_path)
    asset_master = load_yaml(asset_master_path)
    return parse_semiconductor_vertical_slice(raw, asset_master=asset_master)


def parse_semiconductor_vertical_slice(
    raw: Mapping[str, Any],
    *,
    asset_master: Mapping[str, Any] | None = None,
) -> SemiconductorVerticalSliceUniverse:
    if not isinstance(raw, Mapping):
        raise SemiconductorUniverseError("semiconductor universe must be an object")
    benchmark = _parse_benchmark(raw.get("benchmark"))
    active_overlay = _parse_overlay(raw.get("active_overlay"))
    subsectors = _parse_subsectors(raw.get("subsectors"))
    universe = SemiconductorVerticalSliceUniverse(
        version=_text(raw.get("version"), "version"),
        as_of_date=_text(raw.get("as_of_date"), "as_of_date"),
        benchmark=benchmark,
        active_overlay=active_overlay,
        subsectors=subsectors,
    )
    _validate_candidate_assets(universe, asset_master or load_asset_master())
    return universe


def _parse_benchmark(raw: Any) -> SemiconductorBenchmark:
    if not isinstance(raw, Mapping):
        raise SemiconductorUniverseError("benchmark must be an object")
    benchmark = SemiconductorBenchmark(
        benchmark_id=_text(raw.get("benchmark_id"), "benchmark.benchmark_id"),
        role=_text(raw.get("role"), "benchmark.role"),
        tradeable=raw.get("tradeable"),
        asset_master_asset_id=_optional_text(raw.get("asset_master_asset_id"), "benchmark.asset_master_asset_id"),
        activation_state=_text(raw.get("activation_state"), "benchmark.activation_state"),
    )
    if benchmark.role != VALID_BENCHMARK_ROLE:
        raise SemiconductorUniverseError("benchmark.role must be core_benchmark")
    if benchmark.tradeable is not False:
        raise SemiconductorUniverseError("benchmark.tradeable must be false for a non-executable benchmark identity")
    return benchmark


def _parse_overlay(raw: Any) -> SemiconductorOverlay:
    if not isinstance(raw, Mapping):
        raise SemiconductorUniverseError("active_overlay must be an object")
    overlay = SemiconductorOverlay(
        overlay_id=_text(raw.get("overlay_id"), "active_overlay.overlay_id"),
        role=_text(raw.get("role"), "active_overlay.role"),
        activation_state=_text(raw.get("activation_state"), "active_overlay.activation_state"),
    )
    if overlay.role != VALID_OVERLAY_ROLE:
        raise SemiconductorUniverseError("active_overlay.role must be active_overlay")
    return overlay


def _parse_subsectors(raw: Any) -> tuple[SemiconductorSubsector, ...]:
    if not isinstance(raw, list):
        raise SemiconductorUniverseError("subsectors must be a list")
    subsectors = tuple(
        SemiconductorSubsector(
            subsector_id=_text(item.get("subsector_id"), "subsector.subsector_id"),
            candidate_asset_ids=_text_tuple(item.get("candidate_asset_ids"), "subsector.candidate_asset_ids"),
            activation_state=_text(item.get("activation_state"), "subsector.activation_state"),
        )
        for item in raw
        if isinstance(item, Mapping)
    )
    if len(subsectors) != len(raw):
        raise SemiconductorUniverseError("each subsector must be an object")
    identifiers = [item.subsector_id for item in subsectors]
    if set(identifiers) != SEMICONDUCTOR_SUBSECTORS:
        unknown = sorted(set(identifiers) - SEMICONDUCTOR_SUBSECTORS)
        missing = sorted(SEMICONDUCTOR_SUBSECTORS - set(identifiers))
        if unknown:
            raise SemiconductorUniverseError(f"unknown subsector: {unknown[0]}")
        raise SemiconductorUniverseError(f"missing subsector: {missing[0]}")
    if len(identifiers) != len(set(identifiers)):
        raise SemiconductorUniverseError("duplicate subsector_id found")
    return subsectors


def _validate_candidate_assets(
    universe: SemiconductorVerticalSliceUniverse,
    asset_master: Mapping[str, Any],
) -> None:
    assets = asset_master.get("assets") if isinstance(asset_master, Mapping) else None
    if not isinstance(assets, list):
        raise SemiconductorUniverseError("asset master assets must be a list")
    by_id = {str(asset.get("asset_id")): asset for asset in assets if isinstance(asset, Mapping)}
    candidate_ids = universe.candidate_asset_ids
    if len(candidate_ids) != len(set(candidate_ids)):
        raise SemiconductorUniverseError("duplicate candidate asset_id found")
    for asset_id in candidate_ids:
        asset = by_id.get(asset_id)
        if asset is None:
            raise SemiconductorUniverseError(f"unknown candidate asset_id: {asset_id}")
        if asset.get("asset_type") not in VALID_ASSET_TYPES:
            raise SemiconductorUniverseError(f"invalid asset type for candidate: {asset_id}")


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemiconductorUniverseError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name)


def _text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SemiconductorUniverseError(f"{field_name} must be a list")
    return tuple(_text(item, field_name) for item in value)
