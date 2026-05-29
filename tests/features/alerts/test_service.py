from __future__ import annotations

from typing import Any

from api.features.alerts.service import AlertsService


class _FakeRepo:
    def list_recent(self, limit: int) -> list[Any]:
        return [{"id": 1, "level": "warning", "title": "Test", "is_read": False}]

    def mark_read(self, alert_id: int) -> None:
        pass

    def generate_target_alerts(self) -> int:
        return 3

    def get_pending_telegram_alerts(self, level_filter: str):
        return [], [], 0, "2024-01-01"

    def record_telegram_logs(self, pending, status, error=None) -> None:
        pass


def test_list_recent():
    svc = AlertsService(_FakeRepo())
    items = svc.list_recent(10)
    assert len(items) == 1


def test_mark_read():
    svc = AlertsService(_FakeRepo())
    result = svc.mark_read(1)
    assert result["ok"] is True


def test_generate_alerts():
    svc = AlertsService(_FakeRepo())
    result = svc.generate_alerts()
    assert result["created"] == 3


def test_notify_telegram_no_alerts():
    svc = AlertsService(_FakeRepo())
    result = svc.notify_telegram("danger")
    assert result.ok is True
    assert result.sent == 0


def test_service_no_db_import():
    from pathlib import Path
    src = Path("api/features/alerts/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
