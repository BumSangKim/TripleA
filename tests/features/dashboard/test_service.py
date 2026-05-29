from __future__ import annotations

from api.features.dashboard.models import DashboardData
from api.features.dashboard.service import DashboardService


class _FakeRepo:
    def get_summary(self, trading_mode):
        return DashboardData(
            mode=trading_mode, mode_info=None, kpi=None, macro=[],
            accounts=[], allocation=[], targets=[], suggestions=[],
            top_movers=[], calendar=[], alerts=[], insights=None,
        )


def test_get_summary():
    svc = DashboardService(_FakeRepo())
    result = svc.get_summary("test")
    assert result.mode == "test"
    assert result.macro == []


def test_service_no_db_import():
    from pathlib import Path
    src = Path("api/features/dashboard/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
