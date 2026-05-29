from __future__ import annotations

from pathlib import Path

from api.features.rebalancing.models import RebalanceRunData
from api.features.rebalancing.service import RebalancingService


class FakeRepo:
    def get_suggestions(self, mode): return [{"asset_class": "equity"}]
    def run_rebalancing(self, mode): return RebalanceRunData(run_id=1, rows=[])
    def get_results(self, mode, limit): return []
    def get_risk_budget(self): return []


def test_get_suggestions():
    s = RebalancingService(FakeRepo())
    assert s.get_suggestions("paper")[0]["asset_class"] == "equity"


def test_run_rebalancing():
    s = RebalancingService(FakeRepo())
    result = s.run_rebalancing("paper")
    assert result.run_id == 1


def test_service_no_db():
    src = Path("api/features/rebalancing/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
