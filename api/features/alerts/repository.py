from __future__ import annotations

import sqlite3
from typing import Any

from api.features.alerts.schemas import AlertItemSchema


class AlertsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_recent(self, limit: int) -> list[AlertItemSchema]:
        rows = self._conn.execute(
            "SELECT * FROM dashboard_alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            AlertItemSchema(
                id=r["id"], level=r["level"], category=r["category"],
                title=r["title"], message=r["message"],
                is_read=bool(r["is_read"]), created_at=r["created_at"],
            )
            for r in rows
        ]

    def mark_read(self, alert_id: int) -> None:
        self._conn.execute("UPDATE dashboard_alerts SET is_read=1 WHERE id=?", (alert_id,))
        self._conn.commit()

    def generate_target_alerts(self) -> int:
        from api.features.targets.repository import get_local_target_deviations

        targets = get_local_target_deviations(self._conn)
        created = 0
        for t in targets:
            if t.level == "normal":
                continue
            level_str = "danger" if t.level == "danger" else "warning"
            direction = "초과" if t.deviation > 0 else "부족"
            title = f"{t.asset_class} 비중 {direction} {abs(t.deviation):.1f}%"
            existing = self._conn.execute("""
                SELECT id FROM dashboard_alerts
                WHERE title=? AND date(created_at)=date('now','localtime') LIMIT 1
            """, (title,)).fetchone()
            if existing:
                continue
            self._conn.execute("""
                INSERT INTO dashboard_alerts (level, category, title, message)
                VALUES (?, 'target', ?, ?)
            """, (
                level_str,
                title,
                f"현재 {t.currentRatio:.1f}% / 목표 {t.targetRatio:.1f}% (편차 {t.deviation:+.1f}%)",
            ))
            created += 1
        if created:
            self._conn.commit()
        return created
