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


def test_service_no_db_import():
    from pathlib import Path
    src = Path("api/features/alerts/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
