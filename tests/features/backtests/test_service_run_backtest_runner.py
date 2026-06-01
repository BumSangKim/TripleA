from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from api.backtest_engine import BacktestConfig
from api.features.backtests.schemas import BacktestRunRequest
from api.features.backtests.service import BacktestsService


@dataclass
class FakeBacktestResult:
    marker: str = "engine-result"


class FakeRunner:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.configs: list[BacktestConfig] = []

    def run(self, config: BacktestConfig) -> FakeBacktestResult:
        self.calls.append("runner.run")
        self.configs.append(config)
        return FakeBacktestResult()


class FakePersistingRepository:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.saved: tuple[Any, BacktestConfig, FakeBacktestResult] | None = None

    def run_backtest(self, body: Any) -> dict:
        self.calls.append("repo.run_backtest")
        return {"path": "legacy"}

    def save_backtest_result(
        self,
        body: Any,
        config: BacktestConfig,
        result: FakeBacktestResult,
    ) -> dict:
        self.calls.append("repo.save_backtest_result")
        self.saved = (body, config, result)
        return {"path": "runner", "marker": result.marker}


class FakeLegacyRepository:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def run_backtest(self, body: Any) -> dict:
        self.calls.append("repo.run_backtest")
        return {"path": "legacy"}


def test_backtests_service_run_backtest_calls_runner_then_repository_persistence():
    calls: list[str] = []
    repo = FakePersistingRepository(calls)
    runner = FakeRunner(calls)
    request = _request()

    response = BacktestsService(repo, backtest_execution_runner=runner).run_backtest(request)

    assert response == {"path": "runner", "marker": "engine-result"}
    assert calls == ["runner.run", "repo.save_backtest_result"]
    assert runner.configs[0].start_date == date(2024, 1, 2)
    assert runner.configs[0].end_date == date(2024, 1, 3)
    assert runner.configs[0].initial_capital == 100_000
    assert repo.saved is not None
    assert repo.saved[0] is request
    assert repo.saved[1] is runner.configs[0]


def test_backtests_service_run_backtest_keeps_legacy_pass_through_until_repository_persistence_exists():
    calls: list[str] = []
    repo = FakeLegacyRepository(calls)
    runner = FakeRunner(calls)

    response = BacktestsService(repo, backtest_execution_runner=runner).run_backtest(_request())

    assert response == {"path": "legacy"}
    assert calls == ["repo.run_backtest"]


def test_backtests_service_run_backtest_without_runner_uses_repository_pass_through():
    calls: list[str] = []
    repo = FakePersistingRepository(calls)

    response = BacktestsService(repo).run_backtest(_request())

    assert response == {"path": "legacy"}
    assert calls == ["repo.run_backtest"]


def _request() -> BacktestRunRequest:
    return BacktestRunRequest(
        startDate="2024-01-02",
        endDate="2024-01-03",
        initialCapital=100_000,
        rebalanceFrequency="monthly",
        strategyMode="triplea_dynamic",
        riskProfile="balanced",
        universeId="default_global",
        baseCurrency="KRW",
        feeBps=5,
        slippageBps=6,
        taxBps=7,
        dataLookbackYears=3,
    )
