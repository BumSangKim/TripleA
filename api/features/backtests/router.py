from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.features.backtests.dependencies import get_backtests_service
from api.features.backtests.schemas import (
    BacktestDecision,
    BacktestPosition,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestTrade,
)
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
