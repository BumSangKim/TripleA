from __future__ import annotations

import sqlite3
from typing import Any, Optional

from api.features.calendar.schemas import CalendarEventSchema


class CalendarRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_events(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[CalendarEventSchema]:
        try:
            where_clauses = ["event_date >= date('now')"]
            params: list = []
            if from_date:
                where_clauses = ["event_date >= ?"]
                params.append(from_date)
            if to_date:
                where_clauses.append("event_date <= ?")
                params.append(to_date)
            where_sql = " AND ".join(where_clauses)
            rows = self._conn.execute(f"""
                SELECT id, event_date, event_time, event_name, country
                FROM economic_events
                WHERE {where_sql}
                ORDER BY event_date, event_time
                LIMIT 50
            """, params).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return [
            CalendarEventSchema(
                id=r["id"], date=r["event_date"], time=r["event_time"],
                title=r["event_name"], country=r["country"], importance="medium",
            )
            for r in rows
        ]
