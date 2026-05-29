from __future__ import annotations

from pathlib import Path

from api.features.system.models import SystemStatusData
from api.features.system.service import SystemService


class FakeSystemRepository:
    def get_status_data(self) -> SystemStatusData:
        return SystemStatusData(
            macro_last_update="2026-01-01",
            holdings_last_update="2026-01-01",
            total_indicators=100,
            recent_7d_rows=50,
            success_rate=99.0,
            unread_alerts=2,
            pipeline_status="정상",
            timestamp="2026-01-01T00:00:00",
        )

    def list_modes(self) -> list:
        return ["mock", "paper"]

    def get_mode_info(self, mode):
        return {"mode": mode}

    def sync_accounts(self, mode):
        return {"ok": True, "mode": mode}


def test_get_status_delegates_to_repo():
    service = SystemService(FakeSystemRepository())
    status = service.get_status()
    assert isinstance(status, SystemStatusData)
    assert status.total_indicators == 100


def test_list_modes_delegates_to_repo():
    service = SystemService(FakeSystemRepository())
    modes = service.list_modes()
    assert "mock" in modes


def test_get_mode_info_delegates_to_repo():
    service = SystemService(FakeSystemRepository())
    info = service.get_mode_info("paper")
    assert info == {"mode": "paper"}


def test_sync_accounts_delegates_to_repo():
    service = SystemService(FakeSystemRepository())
    result = service.sync_accounts("paper")
    assert result["ok"] is True


def test_repository_import_smoke():
    from api.features.system.repository import SystemRepository

    assert SystemRepository is not None


def test_service_no_db_dependency():
    src = Path("api/features/system/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
