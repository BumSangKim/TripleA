from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from api.features.backtests.service import BacktestsService
from api.features.backtests.sector_component_config import SectorComponentBacktestConfig, SectorComponentWeightSet
from api.features.backtests.sector_component_models import SectorComponentObservation
from api.features.backtests.sector_component_portfolios import SectorComponentSectorPortfolio, SectorPortfolioAsset
from api.features.backtests.sector_component_runner import SectorComponentReturnRecord
from api.features.backtests.sector_component_scope import (
    SectorComponentScope,
    SectorComponentScopedBacktestResult,
)


class FakeRepo:
    def run_backtest(self, body): return {"run_id": 1, "body": body}
    def list_runs(self, limit): return [{"limit": limit}]
    def get_run(self, run_id): return {"run_id": run_id}
    def get_decisions(self, run_id): return [{"run_id": run_id, "type": "decision"}]
    def get_positions(self, run_id): return [{"run_id": run_id, "type": "position"}]
    def get_trades(self, run_id): return [{"run_id": run_id, "type": "trade"}]


class FakeDataProvider:
    def __init__(self, observations, returns, regimes=()) -> None:
        self.observations = observations
        self.returns = returns
        self.regimes = regimes
        self.calls: list[str] = []

    def list_sector_component_observations(self, config):
        self.calls.append("observations")
        return self.observations

    def list_sector_component_returns(self, config):
        self.calls.append("returns")
        return self.returns

    def list_sector_component_regimes(self, config):
        self.calls.append("regimes")
        return self.regimes


class FakeScopeRunner:
    def __init__(self) -> None:
        self.called_with = None

    def __call__(self, config, observations, historical_returns, macro_regime_records, portfolios, scope):
        self.called_with = (config, observations, historical_returns, macro_regime_records, portfolios, scope)
        return SectorComponentScopedBacktestResult(
            sector_scope=scope,
            parameter_version=config.parameter_version,
            model_version=config.model_version,
            data_snapshot_id="scope-result-1",
            status="OK",
            reason_codes=("SECTOR_COMPONENT_SCOPE_COMPLETED",),
        )


def config() -> SectorComponentBacktestConfig:
    return SectorComponentBacktestConfig(
        parameter_version="p1",
        model_version="m1",
        enabled_components=("trade",),
        component_weight_grid=(SectorComponentWeightSet("baseline", {"trade": 1.0}),),
        rebalance_frequency="monthly",
        decision_lag_days=1,
        transaction_cost_bps=0.0,
        tax_assumption_enabled=False,
        stress_periods=(),
        required_metrics=("total_return",),
        fallback_policy="REVIEW_REQUIRED",
    )


def scope() -> SectorComponentScope:
    return SectorComponentScope(mode="single", sector_id="SEMICONDUCTOR")


def portfolios() -> tuple[SectorComponentSectorPortfolio, ...]:
    return (
        SectorComponentSectorPortfolio(
            sector_id="SEMICONDUCTOR",
            display_name="Semiconductor",
            portfolio_id="sector_semiconductor_current_v1",
            assets=(SectorPortfolioAsset("SMH", 1.0),),
        ),
    )


def observation() -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name="trade",
        score=0.7,
        as_of_date=date(2026, 1, 31),
        available_at=datetime(2026, 1, 30, 9, tzinfo=UTC),
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="raw-1",
    )


def test_provider_and_scope_runner_are_called() -> None:
    provider = FakeDataProvider([observation()], [SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 1, 31), 0.01)])
    runner = FakeScopeRunner()
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=provider,
        sector_component_scope_runner=runner,
    )

    result = service.run_sector_component_scope_backtest(scope(), config(), portfolios())

    assert result.status == "OK"
    assert provider.calls == ["observations", "returns", "regimes"]
    assert runner.called_with is not None
    assert len(runner.called_with[1]) == 1
    assert len(runner.called_with[2]) == 1


def test_missing_provider_returns_conservative_fallback() -> None:
    result = BacktestsService(FakeRepo(), sector_component_scope_runner=FakeScopeRunner()).run_sector_component_scope_backtest(
        scope(),
        config(),
        portfolios(),
    )

    assert result.status == "REVIEW_REQUIRED"
    assert result.warnings[0].code == "SECTOR_COMPONENT_DATA_PROVIDER_NOT_CONFIGURED"


def test_missing_scope_runner_returns_conservative_fallback() -> None:
    provider = FakeDataProvider([observation()], [])
    result = BacktestsService(FakeRepo(), sector_component_data_provider=provider).run_sector_component_scope_backtest(
        scope(),
        config(),
        portfolios(),
    )

    assert result.status == "REVIEW_REQUIRED"
    assert result.warnings[0].code == "SECTOR_COMPONENT_SCOPE_RUNNER_NOT_CONFIGURED"


def test_missing_observations_returns_conservative_fallback_without_runner_call() -> None:
    provider = FakeDataProvider([], [])
    runner = FakeScopeRunner()
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=provider,
        sector_component_scope_runner=runner,
    )

    result = service.run_sector_component_scope_backtest(scope(), config(), portfolios())

    assert result.status == "REVIEW_REQUIRED"
    assert result.warnings[0].code == "SECTOR_COMPONENT_OBSERVATIONS_MISSING"
    assert provider.calls == ["observations", "returns", "regimes"]
    assert runner.called_with is None


def test_existing_service_methods_are_preserved() -> None:
    service = BacktestsService(FakeRepo())

    assert service.run_backtest({"x": 1}) == {"run_id": 1, "body": {"x": 1}}
    assert service.list_runs(20) == [{"limit": 20}]
    assert service.get_run(7) == {"run_id": 7}
    assert service.get_decisions(7) == [{"run_id": 7, "type": "decision"}]
    assert service.get_positions(7) == [{"run_id": 7, "type": "position"}]
    assert service.get_trades(7) == [{"run_id": 7, "type": "trade"}]


def test_service_has_no_db_fastapi_or_execution_imports() -> None:
    source = Path("api/features/backtests/service.py").read_text(encoding="utf-8")

    assert "sqlite3" not in source
    assert "from fastapi" not in source
    assert "HTTPException" not in source
    assert "api.features.orders" not in source
    assert "api.brokers" not in source
