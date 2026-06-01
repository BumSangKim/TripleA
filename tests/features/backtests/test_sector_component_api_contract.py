from __future__ import annotations

from typing import Any

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


FORBIDDEN_OUTPUT_KEYS = {"account_id", "accountId", "order", "orders", "orderCandidate", "execution", "broker"}


class FakeService:
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
        return SectorComponentScopedBacktestResult(
            sector_scope=scope,
            parameter_version=config.parameter_version,
            model_version=config.model_version,
            data_snapshot_id="scope-contract-1",
            status="REVIEW_REQUIRED",
            comparison_rows=(
                SectorComponentComparisonRow(
                    sector_id=scope.sector_id or "SEMICONDUCTOR",
                    display_name="Semiconductor",
                    portfolio_id="sector_semiconductor_current_v1",
                    status="REVIEW_REQUIRED",
                    total_return=0.01,
                    max_drawdown=0.0,
                    volatility=0.0,
                    hit_rate=1.0,
                    observation_count=2,
                    warning_count=1,
                    reason_codes=("REVIEW_REQUIRED",),
                ),
            ),
            reason_codes=("REVIEW_REQUIRED", "SECTOR_COMPONENT_SCOPE_COMPLETED"),
        )


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_backtests_service] = lambda: FakeService()
    app.dependency_overrides[get_sector_component_config] = config
    app.dependency_overrides[get_sector_component_portfolios] = portfolios
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
            warnings=("ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED:SMH",),
        ),
    )


def test_metadata_contract_uses_camel_case_and_audit_fields() -> None:
    payload = client().get("/api/backtests/sector-components/ui-metadata").json()

    assert {"parameterVersion", "modelVersion", "allSectorOption", "sectorOptions", "reasonCodes"} <= set(payload)
    assert "parameter_version" not in payload
    assert payload["allSectorOption"]["sectorScope"] == {"mode": "all", "sectorId": None}
    assert payload["sectorOptions"][0]["reasonCodes"]
    assert payload["sectorOptions"][0]["warnings"]


def test_run_contract_uses_camel_case_and_status_fields() -> None:
    payload = client().post("/api/backtests/sector-components/run", json={"sectorScope": {"mode": "all"}}).json()

    assert {"sectorScope", "dataSnapshotId", "comparisonRows", "sectorResults", "warnings", "reasonCodes", "status"} <= set(payload)
    assert "data_snapshot_id" not in payload
    assert payload["status"] == "REVIEW_REQUIRED"
    assert payload["reasonCodes"]
    assert payload["comparisonRows"][0]["warningCount"] == 1


def test_invalid_sector_component_payload_contract() -> None:
    response = client().post("/api/backtests/sector-components/run", json={"sectorScope": {"mode": "all", "sectorId": "SEMICONDUCTOR"}})

    assert response.status_code == 422


def test_new_endpoints_do_not_return_account_order_or_execution_fields() -> None:
    metadata = client().get("/api/backtests/sector-components/ui-metadata").json()
    run = client().post("/api/backtests/sector-components/run", json={"sectorScope": {"mode": "all"}}).json()

    assert _find_forbidden_keys(metadata) == []
    assert _find_forbidden_keys(run) == []


def test_existing_backtest_run_request_still_forbids_extra_fields() -> None:
    response = client().post(
        "/api/backtests/run",
        json={
            "startDate": "2020-01-01",
            "endDate": "2024-12-31",
            "initialCapital": 100000000,
            "rebalanceFrequency": "monthly",
            "sectorScope": {"mode": "all"},
        },
    )

    assert response.status_code == 422


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_OUTPUT_KEYS:
                matches.append(child_path)
            matches.extend(_find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_find_forbidden_keys(child, f"{path}[{index}]"))
    return matches
