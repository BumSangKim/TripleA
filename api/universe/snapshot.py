from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from api.universe.selector import resolve_all_selectors


SNAPSHOT_ASSET_FIELDS = ("asset_id", "symbol", "market", "name", "asset_type")


def build_universe_snapshot(
    *,
    asset_master: dict[str, Any],
    selectors: dict[str, Any],
    as_of_date: date | str,
) -> dict[str, Any]:
    snapshot_date = _format_date(as_of_date)
    selector_map = selectors.get("selectors", selectors)
    resolved = resolve_all_selectors(asset_master["assets"], selector_map)

    return {
        "snapshot_id": f"universe_snapshot_{snapshot_date.replace('-', '')}",
        "asset_master_version": asset_master.get("version"),
        "selector_version": selectors.get("version"),
        "as_of_date": snapshot_date,
        "resolved": {
            name: [_snapshot_asset(asset) for asset in assets]
            for name, assets in resolved.items()
        },
    }


def write_universe_snapshot(snapshot: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _format_date(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(value).isoformat()


def _snapshot_asset(asset: dict[str, Any]) -> dict[str, Any]:
    return {field: asset[field] for field in SNAPSHOT_ASSET_FIELDS}
