from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .asset_universe_schema import (
    AssetDefinition,
    AssetUniverseSchemaError,
    parse_asset_definitions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_UNIVERSE_PATH = PROJECT_ROOT / "config" / "asset_universe.yaml"

NO_ACTION = "NO_ACTION"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
NO_ACTIVE_UNIVERSE = "NO_ACTIVE_UNIVERSE"


class AssetUniverseLoadError(RuntimeError):
    def __init__(self, message: str, *, state: str = REVIEW_REQUIRED):
        super().__init__(message)
        self.state = state


@dataclass(frozen=True)
class AssetUniverse:
    universe_id: str
    version: str
    description: str
    base_currency: str
    assets: tuple[AssetDefinition, ...]
    source_path: str
    conservative_state: str | None = None


def load_asset_universe(config_path: str | Path | None = None) -> AssetUniverse:
    path = Path(config_path) if config_path is not None else DEFAULT_ASSET_UNIVERSE_PATH
    if not path.exists():
        raise AssetUniverseLoadError(
            f"Asset universe config not found: {path}",
            state=NO_ACTIVE_UNIVERSE,
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AssetUniverseLoadError(
            f"Asset universe config is malformed: {path}",
            state=REVIEW_REQUIRED,
        ) from exc

    if not isinstance(raw, dict):
        raise AssetUniverseLoadError("Asset universe config must be an object", state=REVIEW_REQUIRED)

    try:
        universe_id = _required_string(raw, "universe_id")
        version = _required_string(raw, "version")
        description = _required_string(raw, "description")
        base_currency = _required_string(raw, "base_currency")
        raw_assets = raw.get("assets")
        if not isinstance(raw_assets, list):
            raise AssetUniverseSchemaError("assets must be a list")
        assets = tuple(parse_asset_definitions(raw_assets))
        _reject_duplicate_asset_ids(assets)
    except AssetUniverseSchemaError as exc:
        raise AssetUniverseLoadError(str(exc), state=REVIEW_REQUIRED) from exc

    conservative_state = None
    if not get_enabled_assets_from_list(assets):
        conservative_state = NO_ACTIVE_UNIVERSE

    return AssetUniverse(
        universe_id=universe_id,
        version=version,
        description=description,
        base_currency=base_currency,
        assets=assets,
        source_path=str(path),
        conservative_state=conservative_state,
    )


def get_enabled_assets(universe: AssetUniverse) -> list[AssetDefinition]:
    return get_enabled_assets_from_list(universe.assets)


def get_watchlist_assets(universe: AssetUniverse) -> list[AssetDefinition]:
    return [asset for asset in universe.assets if asset.role == "watchlist"]


def get_asset_by_id(universe: AssetUniverse, asset_id: str) -> AssetDefinition | None:
    for asset in universe.assets:
        if asset.asset_id == asset_id:
            return asset
    return None


def get_enabled_assets_from_list(assets: tuple[AssetDefinition, ...]) -> list[AssetDefinition]:
    return [asset for asset in assets if asset.enabled and asset.role != "watchlist"]


def _reject_duplicate_asset_ids(assets: tuple[AssetDefinition, ...]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for asset in assets:
        if asset.asset_id in seen:
            duplicates.add(asset.asset_id)
        seen.add(asset.asset_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise AssetUniverseSchemaError(f"Duplicate asset_id values: {duplicate_list}")


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AssetUniverseSchemaError(f"{field} must be a non-empty string")
    return value.strip()

