from __future__ import annotations

import sqlite3


def seed(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) FROM targets").fetchone()
    if row[0] > 0:
        return
    defaults = [
        ("asset_allocation", "국내주식",    25.0,  3.0,  5.0),
        ("asset_allocation", "해외주식",    35.0,  3.0,  5.0),
        ("asset_allocation", "채권",        15.0,  2.0,  4.0),
        ("asset_allocation", "ETF",          10.0,  2.0,  4.0),
        ("asset_allocation", "현금",         15.0,  2.0,  4.0),
        ("monthly_invest",   "월 투자 목표",  10_000_000, 10.0, 20.0),
        ("return_rate",      "연 수익률 목표", 8.0,        1.5,  3.0),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO targets (target_type, asset_class, target_value, warning_thr, danger_thr) VALUES (?,?,?,?,?)",
        defaults,
    )
