from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from api.features.system.models import SystemStatusData


class SystemRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_status_data(self) -> SystemStatusData:
        macro_last = self._conn.execute(
            "SELECT MAX(updated) as t FROM indicators"
        ).fetchone()["t"]

        total_rows = self._conn.execute(
            "SELECT COUNT(*) as c FROM indicators"
        ).fetchone()["c"]

        recent_rows = self._conn.execute("""
            SELECT COUNT(*) as c FROM indicators
            WHERE date >= date('now', '-7 days', 'localtime')
        """).fetchone()["c"]

        holdings_last = self._conn.execute(
            "SELECT MAX(updated_at) as t FROM holdings"
        ).fetchone()["t"]

        unread = self._conn.execute(
            "SELECT COUNT(*) as c FROM dashboard_alerts WHERE is_read=0"
        ).fetchone()["c"]

        success_rate = min(99.9, (recent_rows / 50) * 100) if recent_rows > 0 else 0.0

        return SystemStatusData(
            macro_last_update=macro_last,
            holdings_last_update=holdings_last,
            total_indicators=total_rows,
            recent_7d_rows=recent_rows,
            success_rate=round(success_rate, 1),
            unread_alerts=unread,
            pipeline_status="정상" if recent_rows > 0 else "미확인",
            timestamp=datetime.now().isoformat(),
        )

    def list_modes(self) -> list[Any]:
        from api.providers.router import provider_router
        return [p.mode_info() for p in provider_router.list()]

    def get_mode_info(self, mode: Any) -> Any:
        from api.providers.router import provider_router
        return provider_router.get(mode).mode_info()

    def sync_accounts(self, mode: Any) -> Any:
        from api.providers.router import provider_router
        return provider_router.get(mode).sync_accounts(self._conn)
