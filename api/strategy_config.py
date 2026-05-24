from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
INVESTMENT_UNIVERSE_YAML = CONFIG_DIR / "investment_universe.yaml"
STRATEGY_PROFILES_YAML = CONFIG_DIR / "strategy_profiles.yaml"
SECTOR_TAXONOMY_YAML = CONFIG_DIR / "sector_taxonomy.yaml"


def list_universe_ids(path: Path = INVESTMENT_UNIVERSE_YAML) -> list[str]:
    return sorted(_load_yaml(path).get("universes", {}).keys())


def load_investment_universe(universe_id: str, path: Path = INVESTMENT_UNIVERSE_YAML) -> dict[str, Any]:
    universes = _load_yaml(path).get("universes", {})
    try:
        return universes[universe_id]
    except KeyError as exc:
        raise KeyError(f"Unknown investment universe: {universe_id}") from exc


def list_risk_profiles(path: Path = STRATEGY_PROFILES_YAML) -> list[str]:
    return sorted(_load_yaml(path).get("profiles", {}).keys())


def load_strategy_profile(profile_id: str, path: Path = STRATEGY_PROFILES_YAML) -> dict[str, Any]:
    profiles = _load_yaml(path).get("profiles", {})
    try:
        return profiles[profile_id]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy profile: {profile_id}") from exc


def load_sector_taxonomy(path: Path = SECTOR_TAXONOMY_YAML) -> dict[str, Any]:
    return _load_yaml(path).get("sectors", {})


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
