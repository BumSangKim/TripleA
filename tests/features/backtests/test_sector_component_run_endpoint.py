from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.backtests.dependencies import (
    get_backtests_service,
    get_sector_component_config,
    get_sector_component_portfolios,
)
from api.features.backtests.router import router
from api.features.backtests.sector_component_config import SectorComponentBacktestConfig, SectorComponentWeightSet
from api.features.backtests.sector_component_portfolios import SectorComponentSectorPortfolio, SectorPortfolioAsset
from api.features.backtests.sector_component_scope import (
    SectorComponentComparisonRow,
    SectorComponentScopedBacktestResult,
)


class FakeService:
    def __init__(self, *, fallback: bool = False, fail_unknown: bool = False) -> None:
        self.fallback = fallback
        self.fail_unknown = fail_unknown

    def run_backtest(self, body):
        return {
            "ok": True,
            "runId": 1,
            "name": body.name,
            "startDate": body.startDate,
            "endDate": body.endDate,
            "initialCapital": body.initialCapital,
            "strategyMode": body.strategyMode,
            "riskProfile": body.riskProfile,
            "universeId": body.universeId,
            "rebalanceFrequency": body.rebalanceFrequency,
            "baseCurrency": body.baseCurrency,
            "feeBps": body.feeBps,
            "slippageBps": body.slippageBps,
            "taxBps": body.taxBps,
            "dataLookbackYears": body.dataLookbackYears,
            "status": "COMPLETED",
            "totalReturn": 0.0,
            "annualReturn": 0.0,
            "maxDrawdown": 0.0,
            "volatility": 0.0,
            "points": [],
        }

    def run_sector_component_scope_backtest(self, scope, config, portfolios):
        if self.fail_unknown and scope.sector_id == "UNKNOWN":
            raise ValueError("unknown sector")
        status = "REVIEW_REQUIRED" if self.fallback else "OK"
        return SectorComponentScopedBacktestResult(
            sector_scope=scope,
            parameter_version=config.parameter_version,
            model_version=config.model_version,
            data_snapshot_id=f"scope:{scope.mode}:{scope.sector_id or 'ALL'}",
            status=status,
            comparison_rows=(
                SectorComponentComparisonRow(
                    sector_id=scope.sector_id or "SEMICONDUCTOR",
                    display_name="Semiconductor",
                    portfolio_id="sector_semiconductor_current_v1",
                    status=status,
                    total_return=0.01,
                    max_drawdown=0.0,
                    volatility=0.0,
                    hit_rate=1.0,
                    observation_count=2,
                    warning_count=1 if self.fallback else 0,
                    reason_codes=("SECTOR_COMPONENT_SCOPE_COMPLETED",),
                ),
            ),
            reason_codes=("REVIEW_REQUIRED",) if self.fallback else ("SECTOR_COMPONENT_SCOPE_COMPLETED",),
        )


def client(service: FakeService | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_sector_component_config] = config
    app.dependency_overrides[get_sector_component_portfolios] = portfolios
    if service is not None:
        app.dependency_overrides[get_backtests_service] = lambda: service
    return TestClient(app)


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


def portfolios() -> tuple[SectorComponentSectorPortfolio, ...]:
    return (
        SectorComponentSectorPortfolio(
            sector_id="SEMICONDUCTOR",
            display_name="Semiconductor",
            portfolio_id="sector_semiconductor_current_v1",
            assets=(SectorPortfolioAsset("SMH", 1.0),),
        ),
    )


def test_all_request_returns_scoped_response() -> None:
    response = client(FakeService()).post("/api/backtests/sector-components/run", json={"sectorScope": {"mode": "all"}})

    assert response.status_code == 200
    payload = response.json()
    assert payload["sectorScope"] == {"mode": "all", "sectorId": None}
    assert payload["semantics"] == "independent_enabled_sector_backtests"
    assert payload["comparisonRows"][0]["sectorId"] == "SEMICONDUCTOR"


def test_single_request_returns_selected_scope() -> None:
    response = client(FakeService()).post(
        "/api/backtests/sector-components/run",
        json={"sectorScope": {"mode": "single", "sectorId": "SEMICONDUCTOR"}},
    )

    assert response.status_code == 200
    assert response.json()["sectorScope"] == {"mode": "single", "sectorId": "SEMICONDUCTOR"}


def test_invalid_sector_request_maps_value_error_to_400() -> None:
    response = client(FakeService(fail_unknown=True)).post(
        "/api/backtests/sector-components/run",
        json={"sectorScope": {"mode": "single", "sectorId": "UNKNOWN"}},
    )

    assert response.status_code == 400
    assert "unknown sector" in response.json()["detail"]


def test_service_fallback_is_visible_in_response() -> None:
    response = client(FakeService(fallback=True)).post("/api/backtests/sector-components/run", json={"sectorScope": {"mode": "all"}})

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "REVIEW_REQUIRED"
    assert payload["comparisonRows"][0]["warningCount"] == 1


def test_existing_run_endpoint_regression() -> None:
    response = client(FakeService()).post(
        "/api/backtests/run",
        json={
            "name": "Regression",
            "startDate": "2020-01-01",
            "endDate": "2024-12-31",
            "initialCapital": 100000000,
            "rebalanceFrequency": "monthly",
        },
    )

    assert response.status_code == 200
    assert response.json()["runId"] == 1
    assert response.json()["name"] == "Regression"


def test_default_run_endpoint_uses_reference_portfolios_and_read_only_inputs() -> None:
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/api/backtests/sector-components/run",
        json={"sectorScope": {"mode": "single", "sectorId": "SEMICONDUCTOR"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sectorScope"] == {"mode": "single", "sectorId": "SEMICONDUCTOR"}
    assert payload["comparisonRows"][0]["sectorId"] == "SEMICONDUCTOR"
    assert payload["comparisonRows"][0]["portfolioId"] == "sector_semiconductor_trade_reference_v1"
    assert payload["comparisonRows"][0]["observationCount"] >= 1


def test_router_has_no_db_or_repository_import() -> None:
    source = Path("api/features/backtests/router.py").read_text(encoding="utf-8")

    assert "repository" not in source
    assert "from api.db" not in source
    assert "get_conn" not in source
