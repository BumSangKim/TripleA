from __future__ import annotations

import sqlite3

_DEFAULTS = [
    ("DEFENSIVE_CORE",    0.65, 0.55, 0.80),
    ("AGGRESSIVE_ALPHA",  0.30, 0.10, 0.40),
    ("LIQUIDITY",         0.05, 0.03, 0.20),
]


def seed(conn: sqlite3.Connection) -> None:
    conn.executemany("""
        INSERT INTO engine_allocations (strategy_bucket, target_ratio, min_ratio, max_ratio)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(strategy_bucket) DO UPDATE SET
            target_ratio=excluded.target_ratio,
            min_ratio=excluded.min_ratio,
            max_ratio=excluded.max_ratio,
            updated_at=datetime('now','localtime')
    """, _DEFAULTS)
