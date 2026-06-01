from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.features.backtests.dependencies import (
    get_backtests_service,
    get_sector_component_config,
    get_sector_component_portfolios,
)
from api.features.backtests.ai_capex_token_diagnostic import build_ai_capex_token_backtest_diagnostic
from api.features.backtests.schemas import (
    AICapexTokenDiagnosticResponse,
    BacktestDecision,
    BacktestPosition,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestTrade,
    SectorComponentRunRequest,
    SectorComponentRunResponse,
    SectorComponentUiMetadataResponse,
)
from api.features.backtests.sector_component_config import SectorComponentBacktestConfig
from api.features.backtests.sector_component_portfolios import SectorComponentSectorPortfolio
from api.features.backtests.sector_component_scope import SectorComponentScope, SectorComponentScopedBacktestResult
from api.features.backtests.sector_component_ui_metadata import build_sector_component_ui_metadata
from api.features.backtests.service import BacktestsService

router = APIRouter(tags=["backtests"])


@router.post("/api/backtests/run", response_model=BacktestRunResponse)
def run_backtest_endpoint(
    body: BacktestRunRequest,
    service: BacktestsService = Depends(get_backtests_service),
):
    try:
        return service.run_backtest(body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/backtests/runs", response_model=List[BacktestRunResponse])
def backtest_runs(
    limit: int = 20,
    service: BacktestsService = Depends(get_backtests_service),
):
    return service.list_runs(limit)


@router.get("/api/backtests/sector-components/ui-metadata", response_model=SectorComponentUiMetadataResponse)
def sector_component_ui_metadata(
    config: SectorComponentBacktestConfig = Depends(get_sector_component_config),
    portfolios: tuple[SectorComponentSectorPortfolio, ...] = Depends(get_sector_component_portfolios),
):
    try:
        return build_sector_component_ui_metadata(config, portfolios)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/backtests/sector-components/run", response_model=SectorComponentRunResponse)
def sector_component_run(
    body: SectorComponentRunRequest,
    service: BacktestsService = Depends(get_backtests_service),
    config: SectorComponentBacktestConfig = Depends(get_sector_component_config),
    portfolios: tuple[SectorComponentSectorPortfolio, ...] = Depends(get_sector_component_portfolios),
):
    try:
        scope = SectorComponentScope(mode=body.sectorScope.mode, sector_id=body.sectorScope.sectorId)
        result = service.run_sector_component_scope_backtest(scope, config, portfolios)
        return _sector_component_run_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/backtests/ai-capex-token/diagnostic/run", response_model=AICapexTokenDiagnosticResponse)
def ai_capex_token_diagnostic_run():
    return build_ai_capex_token_backtest_diagnostic()


@router.get("/api/backtests/runs/{run_id}", response_model=BacktestRunResponse)
def backtest_run(
    run_id: int,
    service: BacktestsService = Depends(get_backtests_service),
):
    try:
        return service.get_run(run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/backtests/runs/{run_id}/decisions", response_model=List[BacktestDecision])
def backtest_decisions(
    run_id: int,
    service: BacktestsService = Depends(get_backtests_service),
):
    try:
        return service.get_decisions(run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/backtests/runs/{run_id}/positions", response_model=List[BacktestPosition])
def backtest_positions(
    run_id: int,
    service: BacktestsService = Depends(get_backtests_service),
):
    try:
        return service.get_positions(run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/backtests/runs/{run_id}/trades", response_model=List[BacktestTrade])
def backtest_trades(
    run_id: int,
    service: BacktestsService = Depends(get_backtests_service),
):
    try:
        return service.get_trades(run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def _sector_component_run_response(result: SectorComponentScopedBacktestResult) -> dict:
    payload = result.to_dict()
    return {
        "ok": True,
        "sectorScope": {
            "mode": payload["sector_scope"]["mode"],
            "sectorId": payload["sector_scope"].get("sector_id"),
        },
        "semantics": payload["semantics"],
        "parameterVersion": payload["parameter_version"],
        "modelVersion": payload["model_version"],
        "dataSnapshotId": payload["data_snapshot_id"],
        "status": payload["status"],
        "comparisonRows": [_comparison_row_response(row) for row in payload["comparison_rows"]],
        "sectorResults": payload["sector_results"],
        "warnings": payload["warnings"],
        "reasonCodes": payload["reason_codes"],
    }


def _comparison_row_response(row: dict) -> dict:
    return {
        "sectorId": row["sector_id"],
        "displayName": row["display_name"],
        "portfolioId": row["portfolio_id"],
        "status": row["status"],
        "totalReturn": row["total_return"],
        "maxDrawdown": row["max_drawdown"],
        "volatility": row["volatility"],
        "hitRate": row["hit_rate"],
        "observationCount": row["observation_count"],
        "warningCount": row["warning_count"],
        "reasonCodes": row["reason_codes"],
    }
