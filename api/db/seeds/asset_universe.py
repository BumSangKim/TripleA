from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def seed(conn: sqlite3.Connection) -> None:
    config_path = PROJECT_ROOT / "config" / "backtest_assets.yaml"
    if not config_path.exists():
        return
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    default_assets = data.get("default_assets") or {}
    rows = []
    for item in default_assets.values():
        asset_code = (item.get("asset_code") or "").strip()
        symbol = (item.get("symbol") or "").strip()
        asset_class = (item.get("asset_class") or "").strip()
        source_type = (item.get("source_type") or "").strip()
        currency = (item.get("currency") or "KRW").strip()
        if not all([asset_code, symbol, asset_class, source_type, currency]):
            continue
        rows.append((
            asset_code, symbol, item.get("name"), asset_class,
            item.get("market"), currency, source_type,
            1 if item.get("is_active", True) else 0,
        ))
    if not rows:
        return
    conn.executemany("""
        INSERT INTO asset_universe
        (asset_code, symbol, name, asset_class, market, currency, source_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_code) DO UPDATE SET
            symbol=excluded.symbol, name=excluded.name,
            asset_class=excluded.asset_class, market=excluded.market,
            currency=excluded.currency, source_type=excluded.source_type,
            is_active=excluded.is_active, updated_at=datetime('now','localtime')
    """, rows)
