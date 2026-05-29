from __future__ import annotations

import sqlite3
from typing import Any


class SearchRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def search(self, q: str) -> list[Any]:
        q_lower = q.lower()
        results: list[dict] = []

        rows = self._conn.execute(
            "SELECT indicator, unit FROM indicators WHERE lower(indicator) LIKE ? GROUP BY indicator LIMIT 5",
            (f"%{q_lower}%",),
        ).fetchall()
        for r in rows:
            results.append({"type": "macro", "key": r["indicator"], "title": r["indicator"], "url": "/macro"})

        rows = self._conn.execute(
            "SELECT id, title, type FROM documents WHERE lower(title) LIKE ? OR lower(tags) LIKE ? LIMIT 5",
            (f"%{q_lower}%", f"%{q_lower}%"),
        ).fetchall()
        for r in rows:
            results.append({"type": "document", "key": str(r["id"]), "title": r["title"], "url": "/documents"})

        rows = self._conn.execute(
            "SELECT id, title FROM dashboard_alerts WHERE lower(title) LIKE ? LIMIT 3",
            (f"%{q_lower}%",),
        ).fetchall()
        for r in rows:
            results.append({"type": "alert", "key": str(r["id"]), "title": r["title"], "url": "/alerts"})

        return results[:10]
