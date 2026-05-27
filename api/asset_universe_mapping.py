from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .asset_universe_loader import PROJECT_ROOT
from .asset_universe_schema import AssetDefinition


DEFAULT_MAPPING_PATH = PROJECT_ROOT / "config" / "asset_universe_mappings.yaml"


class AssetUniverseMappingError(ValueError):
    pass


@dataclass(frozen=True)
class AssetUniverseMapping:
    version: str
    asset_classes: set[str]
    sectors: set[str]
    asset_class_aliases: dict[str, str]
    sector_aliases: dict[str, str]


def load_asset_universe_mapping(path: str | Path | None = None) -> AssetUniverseMapping:
    mapping_path = Path(path) if path is not None else DEFAULT_MAPPING_PATH
    raw = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise AssetUniverseMappingError("mapping config must be an object")
    return AssetUniverseMapping(
        version=_required_string(raw, "version"),
        asset_classes=set(_mapping_section(raw, "asset_classes")),
        sectors=set(_mapping_section(raw, "sectors")),
        asset_class_aliases=_aliases(raw, "asset_classes"),
        sector_aliases=_aliases(raw, "sectors"),
    )


def normalize_asset_class(value: str, mapping: AssetUniverseMapping | None = None) -> str:
    mapping = mapping or load_asset_universe_mapping()
    return _normalize(value, mapping.asset_classes, mapping.asset_class_aliases, "asset_class")


def normalize_sector(value: str | None, mapping: AssetUniverseMapping | None = None) -> str:
    mapping = mapping or load_asset_universe_mapping()
    return _normalize(value or "none", mapping.sectors, mapping.sector_aliases, "sector")


def validate_asset_categories(
    asset: AssetDefinition,
    mapping: AssetUniverseMapping | None = None,
) -> list[str]:
    mapping = mapping or load_asset_universe_mapping()
    issues: list[str] = []
    try:
        asset_class = normalize_asset_class(asset.asset_class, mapping)
    except AssetUniverseMappingError as exc:
        issues.append(str(exc))
    else:
        if asset_class == "unknown" and (asset.enabled or not asset.review_required):
            issues.append("unknown asset_class is allowed only for disabled review-required assets")

    try:
        sector = normalize_sector(asset.sector, mapping)
    except AssetUniverseMappingError as exc:
        issues.append(str(exc))
    else:
        if sector == "none" and asset.role == "satellite":
            issues.append("satellite assets must use a canonical non-none sector")
    return issues


def _normalize(value: str, canonicals: set[str], aliases: dict[str, str], field: str) -> str:
    normalized = str(value or "").strip()
    if normalized in canonicals:
        return normalized
    alias_key = normalized.lower()
    if alias_key in aliases:
        return aliases[alias_key]
    raise AssetUniverseMappingError(f"unknown {field}: {value}")


def _mapping_section(raw: dict[str, Any], section: str) -> dict[str, Any]:
    value = raw.get(section)
    if not isinstance(value, dict) or not value:
        raise AssetUniverseMappingError(f"{section} must be a non-empty object")
    return value


def _aliases(raw: dict[str, Any], section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for canonical, metadata in _mapping_section(raw, section).items():
        if not isinstance(canonical, str) or not canonical.strip():
            raise AssetUniverseMappingError(f"{section} contains an invalid canonical key")
        if not isinstance(metadata, dict):
            raise AssetUniverseMappingError(f"{section}.{canonical} must be an object")
        for alias in metadata.get("aliases") or []:
            if not isinstance(alias, str) or not alias.strip():
                raise AssetUniverseMappingError(f"{section}.{canonical}.aliases contains an invalid alias")
            result[alias.strip().lower()] = canonical
    return result


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AssetUniverseMappingError(f"{field} must be a non-empty string")
    return value.strip()

