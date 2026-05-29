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
    data = _load_yaml(PROJECT_ROOT / "config" / "investment_universe.yaml")
    universes = data.get("universes") or {}
    rows = []
    for universe in universes.values():
        for item in universe.get("assets") or []:
            asset_code = (item.get("asset_code") or "").strip()
            if not asset_code:
                continue
            rows.append((
                asset_code,
                (item.get("symbol") or asset_code).strip(),
                item.get("name"),
                (item.get("asset_class") or item.get("role") or asset_code).strip(),
                item.get("market"),
                (item.get("currency") or universe.get("base_currency") or "KRW").strip(),
                (item.get("source_type") or "manual").strip(),
                1,
            ))
    if not rows:
        return
    conn.executemany("""
        INSERT INTO asset_universe
        (asset_code, symbol, name, asset_class, market, currency, source_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_code) DO NOTHING
    """, rows)
