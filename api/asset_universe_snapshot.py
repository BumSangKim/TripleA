from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .asset_universe_loader import AssetUniverseLoadError, get_enabled_assets, get_watchlist_assets, load_asset_universe
from .asset_universe_validator import AssetUniverseValidationResult, validate_asset_universe


def export_asset_universe_snapshot(
    config_path: str | Path | None = None,
    *,
    created_at: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    created_at = created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        universe = load_asset_universe(config_path)
    except AssetUniverseLoadError as exc:
        snapshot = _error_snapshot(
            config_path=str(config_path or ""),
            created_at=created_at,
            error=str(exc),
            conservative_state=exc.state,
        )
    else:
        validation = validate_asset_universe(universe)
        assets = sorted((asset.to_dict() for asset in universe.assets), key=lambda item: item["asset_id"])
        enabled_assets = get_enabled_assets(universe)
        watchlist_assets = get_watchlist_assets(universe)
        snapshot_body = {
            "config_path": universe.source_path,
            "universe_id": universe.universe_id,
            "metadata_version": universe.version,
            "base_currency": universe.base_currency,
            "asset_count_total": len(universe.assets),
            "asset_count_enabled": len(enabled_assets),
            "asset_count_watchlist": len(watchlist_assets),
            "validation": _validation_to_dict(validation),
            "assets": assets,
        }
        snapshot = {
            "snapshot_id": _stable_snapshot_id(snapshot_body),
            "created_at": created_at,
            **snapshot_body,
        }

    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return snapshot


def _error_snapshot(
    *,
    config_path: str,
    created_at: str,
    error: str,
    conservative_state: str,
) -> dict[str, Any]:
    snapshot_body = {
        "config_path": config_path,
        "universe_id": None,
        "metadata_version": None,
        "base_currency": None,
        "asset_count_total": 0,
        "asset_count_enabled": 0,
        "asset_count_watchlist": 0,
        "validation": {
            "is_valid": False,
            "errors": [{"asset_id": None, "field": "config", "message": error}],
            "warnings": [],
            "review_required_assets": [],
            "active_asset_count": 0,
            "conservative_state": conservative_state,
        },
        "assets": [],
    }
    return {
        "snapshot_id": _stable_snapshot_id(snapshot_body),
        "created_at": created_at,
        **snapshot_body,
    }


def _validation_to_dict(result: AssetUniverseValidationResult) -> dict[str, Any]:
    return {
        "is_valid": result.is_valid,
        "errors": [issue.__dict__ for issue in result.errors],
        "warnings": [issue.__dict__ for issue in result.warnings],
        "review_required_assets": result.review_required_assets,
        "active_asset_count": result.active_asset_count,
        "conservative_state": result.conservative_state,
    }


def _stable_snapshot_id(snapshot_body: dict[str, Any]) -> str:
    payload = json.dumps(snapshot_body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

