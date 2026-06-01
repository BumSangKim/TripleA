from __future__ import annotations

from typing import Any

from api.features.alerts.ports import IAlertsRepository


class AlertsService:
    def __init__(self, repo: IAlertsRepository) -> None:
        self._repo = repo

    def list_recent(self, limit: int) -> list[Any]:
        return self._repo.list_recent(limit)

    def mark_read(self, alert_id: int) -> dict:
        self._repo.mark_read(alert_id)
        return {"ok": True}

    def generate_alerts(self) -> dict:
        n = self._repo.generate_target_alerts()
        return {"ok": True, "created": n}
