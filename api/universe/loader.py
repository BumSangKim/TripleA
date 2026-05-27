from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_asset_schema(base_path: str | Path = "config/universe") -> dict[str, Any]:
    return load_yaml(Path(base_path) / "schema.yml")


def load_asset_master(base_path: str | Path = "config/universe") -> dict[str, Any]:
    return load_yaml(Path(base_path) / "asset_master.yml")


def load_assets(base_path: str | Path = "config/universe") -> list[dict[str, Any]]:
    data = load_asset_master(base_path)
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise ValueError("asset_master.assets must be a list")
    return assets


def load_universe_selectors(base_path: str | Path = "config/universe") -> dict[str, Any]:
    return load_yaml(Path(base_path) / "universe_selectors.yml")
