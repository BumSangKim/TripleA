from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()


def _is_applied(conn: sqlite3.Connection, version: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
    ).fetchone()
    return bool(row)


def _record(conn: sqlite3.Connection, version: str) -> None:
    conn.execute(
        "INSERT INTO schema_migrations (version) VALUES (?)", (version,)
    )
    conn.commit()


def run_migrations(conn: sqlite3.Connection, migrations: list[tuple[str, Callable[[sqlite3.Connection], None]]]) -> None:
    """Apply pending migrations in order. Already-applied versions are skipped."""
    _ensure_migrations_table(conn)
    for version, apply_fn in migrations:
        if _is_applied(conn, version):
            continue
        apply_fn(conn)
        _record(conn, version)
