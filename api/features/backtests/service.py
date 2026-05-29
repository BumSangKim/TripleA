from __future__ import annotations

from typing import Any

from api.features.backtests.ports import IBacktestsRepository


class BacktestsService:
    def __init__(self, repo: IBacktestsRepository) -> None:
        self._repo = repo

    def run_backtest(self, body: Any) -> Any:
        return self._repo.run_backtest(body)

    def list_runs(self, limit: int) -> list[Any]:
        return self._repo.list_runs(limit)

    def get_run(self, run_id: int) -> Any:
        return self._repo.get_run(run_id)

    def get_decisions(self, run_id: int) -> list[Any]:
        return self._repo.get_decisions(run_id)

    def get_positions(self, run_id: int) -> list[Any]:
        return self._repo.get_positions(run_id)

    def get_trades(self, run_id: int) -> list[Any]:
        return self._repo.get_trades(run_id)
