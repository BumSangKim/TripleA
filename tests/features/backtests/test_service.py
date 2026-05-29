from __future__ import annotations

from pathlib import Path

from api.features.backtests.service import BacktestsService


class FakeRepo:
    def run_backtest(self, body): return {"run_id": 1}
    def list_runs(self, limit): return []
    def get_run(self, run_id): return {"run_id": run_id}
    def get_decisions(self, run_id): return []
    def get_positions(self, run_id): return []
    def get_trades(self, run_id): return []


def test_run_backtest():
    result = BacktestsService(FakeRepo()).run_backtest({"body": "x"})
    assert result["run_id"] == 1


def test_list_runs():
    assert BacktestsService(FakeRepo()).list_runs(20) == []


def test_service_no_db():
    src = Path("api/features/backtests/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
