from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def seed(conn: sqlite3.Connection) -> None:
    taxonomy = _load_yaml(PROJECT_ROOT / "config" / "sector_taxonomy.yaml")
    universes = _load_yaml(PROJECT_ROOT / "config" / "investment_universe.yaml").get("universes") or {}
    default_assets = {
        item.get("asset_code"): item
        for item in (universes.get("default_global") or {}).get("assets", [])
        if item.get("asset_code")
    }

    trade_rows, sector_asset_rows = [], []
    for sector_code, sector in (taxonomy.get("sectors") or {}).items():
        for item_code in sector.get("trade_items") or []:
            trade_rows.append((item_code, sector_code, None, 1, "sector_taxonomy.yaml", 1))
        for priority, asset_code in enumerate(sector.get("assets") or [], start=1):
            asset = default_assets.get(asset_code, {})
            sector_asset_rows.append((
                sector_code, asset_code, asset.get("name"), asset.get("role"),
                asset.get("currency") or "USD", priority, 1,
            ))

    if trade_rows:
        conn.executemany("""
            INSERT INTO trade_item_sector_map (item_code, sector_code, item_name, weight, source, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_code, sector_code) DO UPDATE SET
                item_name=excluded.item_name, weight=excluded.weight,
                source=excluded.source, is_active=excluded.is_active,
                updated_at=datetime('now','localtime')
        """, trade_rows)

    if sector_asset_rows:
        conn.executemany("""
            INSERT INTO sector_asset_map (sector_code, asset_code, asset_name, asset_type, currency, priority, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sector_code, asset_code) DO UPDATE SET
                asset_name=excluded.asset_name, asset_type=excluded.asset_type,
                currency=excluded.currency, priority=excluded.priority,
                is_active=excluded.is_active, updated_at=datetime('now','localtime')
        """, sector_asset_rows)
