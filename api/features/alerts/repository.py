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
        from api.providers.router import provider_router
        from api.providers.modes import TradingMode

        targets = provider_router.get(TradingMode.TEST).get_target_deviations(self._conn)
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

    def get_pending_telegram_alerts(
        self, level_filter: str
    ) -> tuple[list[Any], list[tuple[Any, str]], int, str]:
        if level_filter == "all":
            rows = self._conn.execute(
                "SELECT * FROM dashboard_alerts WHERE is_read=0 ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM dashboard_alerts WHERE is_read=0 AND level=? ORDER BY created_at DESC LIMIT 20",
                (level_filter,),
            ).fetchall()
        send_date = self._conn.execute("SELECT date('now','localtime')").fetchone()[0]
        alerts = [dict(r) for r in rows]
        pending, skipped = self._collect_pending(alerts, send_date)
        return alerts, pending, skipped, send_date

    def _collect_pending(
        self, alerts: list[dict], send_date: str
    ) -> tuple[list[tuple[dict, str]], int]:
        pending: list[tuple[dict, str]] = []
        skipped = 0
        for alert in alerts:
            dedup_key = self._dedup_key(alert, send_date)
            existing = self._conn.execute(
                """
                SELECT id FROM notification_logs
                WHERE channel_type='TELEGRAM' AND dedup_key=? AND status='SENT'
                LIMIT 1
                """,
                (dedup_key,),
            ).fetchone()
            if existing:
                skipped += 1
            else:
                pending.append((alert, dedup_key))
        return pending, skipped

    def _dedup_key(self, alert: dict, send_date: str) -> str:
        category = alert.get("category") or "general"
        return f"telegram:{send_date}:{alert.get('level')}:{category}:{alert.get('title')}"

    def record_telegram_logs(
        self, pending: list[tuple[Any, str]], status: str, error: str | None = None
    ) -> None:
        self._conn.executemany(
            """
            INSERT INTO notification_logs
            (channel_type, alert_type, message, dedup_key, status, sent_at, error_message)
            VALUES ('TELEGRAM', ?, ?, ?, ?, datetime('now','localtime'), ?)
            """,
            [
                (
                    alert.get("level"),
                    f"{alert.get('title')}\n{alert.get('message') or ''}".strip(),
                    dedup_key,
                    status,
                    error,
                )
                for alert, dedup_key in pending
            ],
        )
        self._conn.commit()
