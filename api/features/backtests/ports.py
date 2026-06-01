from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Sequence

if TYPE_CHECKING:
    from api.backtest_engine import BacktestConfig, BacktestEngineResult


class IBacktestsRepository(Protocol):
    def run_backtest(self, body: Any) -> Any: ...
    def list_runs(self, limit: int) -> list[Any]: ...
    def get_run(self, run_id: int) -> Any: ...
    def get_decisions(self, run_id: int) -> list[Any]: ...
    def get_positions(self, run_id: int) -> list[Any]: ...
    def get_trades(self, run_id: int) -> list[Any]: ...


class IBacktestExecutionRunner(Protocol):
    def run(self, config: BacktestConfig) -> BacktestEngineResult: ...


class ISectorComponentBacktestDataProvider(Protocol):
    def list_sector_component_observations(self, config: Any) -> Sequence[Any]: ...
    def list_sector_component_returns(self, config: Any) -> Sequence[Any]: ...
    def list_sector_component_regimes(self, config: Any) -> Sequence[Any]: ...


class ISectorComponentBacktestRunner(Protocol):
    def __call__(
        self,
        config: Any,
        observations: Sequence[Any],
        historical_returns: Sequence[Any],
        *,
        macro_regime_records: Sequence[Any] = (),
    ) -> Any: ...


class ISectorComponentScopeBacktestRunner(Protocol):
    def __call__(
        self,
        config: Any,
        observations: Sequence[Any],
        historical_returns: Sequence[Any],
        macro_regime_records: Sequence[Any],
        portfolios: Sequence[Any],
        scope: Any,
    ) -> Any: ...
