from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from api.strategy_config import load_investment_universe, load_sector_taxonomy


def load_observation_universe(universe_id: str = "default_observation") -> dict[str, Any]:
    path = Path("config/observation_universe.yaml")
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        universe = (data.get("universes") or {}).get(universe_id)
        if universe:
            return universe
    legacy = load_investment_universe("default_global")
    return {
        "assets": [
            {
                **asset,
                "observation_enabled": True,
                "investable_enabled": True,
                "sector_codes": [asset["sector"]] if asset.get("sector") else [],
                "theme_codes": [],
                "factor_codes": [],
                "min_history_days": 252,
                "liquidity_requirement": "REVIEW_REQUIRED",
            }
            for asset in legacy.get("assets", [])
        ]
    }


def load_scoreflow_sector_taxonomy() -> dict[str, Any]:
    taxonomy = load_sector_taxonomy()
    return {
        code: {
            "sector_code": code,
            "name": values.get("name", code),
            "enabled": values.get("enabled", True),
            "common_scoring_enabled": values.get("common_scoring_enabled", True),
            "specialized_plugins": values.get("specialized_plugins") or (["bottleneck"] if values.get("trade_items") else []),
            "benchmark_asset_code": (values.get("assets") or [None])[0],
        }
        for code, values in taxonomy.items()
    }
