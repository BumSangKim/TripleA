from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from api.features.backtests.service import BacktestsService
from api.features.backtests.sector_component_config import (
    SectorComponentBacktestConfig,
    SectorComponentWeightSet,
)
from api.features.backtests.sector_component_models import (
    SectorComponentBacktestResult,
    SectorComponentMetricSummary,
    SectorComponentObservation,
)
from api.features.backtests.sector_component_runner import SectorComponentReturnRecord


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

    def list_sector_component_observations(self, config):
        return self.observations

    def list_sector_component_returns(self, config):
        return self.returns

    def list_sector_component_regimes(self, config):
        return self.regimes


class FakeRunner:
    def __init__(self) -> None:
        self.called_with = None

    def __call__(self, config, observations, historical_returns, *, macro_regime_records=()):
        self.called_with = (config, observations, historical_returns, macro_regime_records)
        return result()


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


def observation() -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name="trade",
        score=0.7,
        as_of_date=date(2026, 1, 31),
        available_at=datetime(2026, 1, 30, 9, tzinfo=UTC),
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="raw:trade:2026-01-31",
    )


def result() -> SectorComponentBacktestResult:
    metric = SectorComponentMetricSummary(
        sector_id="SEMICONDUCTOR",
        as_of_date=date(2026, 1, 31),
        available_at=datetime(2026, 1, 31, 9, tzinfo=UTC),
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="metric:1",
        total_return=0.01,
        observation_count=1,
    )
    return SectorComponentBacktestResult(
        sector_id="SEMICONDUCTOR",
        as_of_date=date(2026, 1, 31),
        available_at=datetime(2026, 1, 31, 9, tzinfo=UTC),
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="result:1",
        metric_summaries=(metric,),
        status="OK",
    )


def test_service_calls_runner_and_returns_result() -> None:
    runner = FakeRunner()
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FakeDataProvider(
            [observation()],
            [SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 1, 31), 0.02)],
        ),
        sector_component_runner=runner,
    )

    actual = service.run_sector_component_backtest(config())

    assert actual.status == "OK"
    assert runner.called_with is not None
    assert len(runner.called_with[1]) == 1
    assert len(runner.called_with[2]) == 1


def test_missing_historical_data_returns_conservative_result() -> None:
    runner = FakeRunner()
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FakeDataProvider([observation()], []),
        sector_component_runner=runner,
    )

    actual = service.run_sector_component_backtest(config())

    assert actual.status == "REVIEW_REQUIRED"
    assert actual.reason_codes == ("REVIEW_REQUIRED", "SECTOR_COMPONENT_HISTORICAL_DATA_MISSING")
    assert runner.called_with is None


def test_missing_provider_or_runner_returns_conservative_result() -> None:
    actual = BacktestsService(FakeRepo()).run_sector_component_backtest(config())

    assert actual.status == "REVIEW_REQUIRED"
    assert actual.warnings[0].code == "SECTOR_COMPONENT_SERVICE_NOT_CONFIGURED"


def test_existing_service_methods_are_preserved() -> None:
    service = BacktestsService(FakeRepo())

    assert service.run_backtest({"x": 1}) == {"run_id": 1, "body": {"x": 1}}
    assert service.list_runs(20) == [{"limit": 20}]
    assert service.get_run(7) == {"run_id": 7}
    assert service.get_decisions(7) == [{"run_id": 7, "type": "decision"}]
    assert service.get_positions(7) == [{"run_id": 7, "type": "position"}]
    assert service.get_trades(7) == [{"run_id": 7, "type": "trade"}]


def test_unit_integration_requires_no_db_repository() -> None:
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FakeDataProvider(
            [observation()],
            [SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 1, 31), 0.02)],
        ),
        sector_component_runner=FakeRunner(),
    )

    assert service.run_sector_component_backtest(config()).metric_summaries[0].total_return == 0.01


def test_service_and_ports_do_not_import_account_order_or_execution_dependencies() -> None:
    source = (
        Path("api/features/backtests/service.py").read_text(encoding="utf-8")
        + Path("api/features/backtests/ports.py").read_text(encoding="utf-8")
    )

    assert "api.features.accounts" not in source
    assert "api.features.orders" not in source
    assert "api.brokers" not in source
    assert "api.domain.execution" not in source
    assert "sqlite3" not in source
    assert "get_conn" not in source
