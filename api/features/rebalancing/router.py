from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.features.rebalancing.dependencies import get_rebalancing_service
from api.features.rebalancing.schemas import (
    RebalanceResultItem,
    RebalanceRunResponse,
    RiskBudgetItem,
    SuggestionItem,
)
from api.features.rebalancing.service import RebalancingService
from api.providers.modes import TradingMode, normalize_mode
from api.providers.router import provider_router

router = APIRouter(tags=["rebalancing"])


def _parse_mode(mode: Optional[str]) -> TradingMode:
    try:
        return normalize_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _check_write_allowed(mode: TradingMode) -> None:
    try:
        provider_router.get(mode).assert_user_write_allowed()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/api/rebalancing/suggestions", response_model=List[SuggestionItem])
def rebalancing_suggestions(
    mode: Optional[str] = None,
    service: RebalancingService = Depends(get_rebalancing_service),
):
    return service.get_suggestions(_parse_mode(mode))


@router.post("/api/rebalancing/run", response_model=RebalanceRunResponse)
def run_rebalancing(
    mode: Optional[str] = None,
    service: RebalancingService = Depends(get_rebalancing_service),
):
    trading_mode = _parse_mode(mode)
    _check_write_allowed(trading_mode)
    data = service.run_rebalancing(trading_mode)
    return RebalanceRunResponse(
        ok=True,
        mode=trading_mode,
        runId=data.run_id,
        saved=len(data.rows),
        results=data.rows,
    )


@router.get("/api/rebalancing/results", response_model=List[RebalanceResultItem])
def list_rebalance_results(
    mode: Optional[str] = None,
    limit: int = 50,
    service: RebalancingService = Depends(get_rebalancing_service),
):
    trading_mode = _parse_mode(mode) if mode else None
    return service.get_results(trading_mode, limit)


@router.get("/api/engine/risk-budget", response_model=List[RiskBudgetItem])
def risk_budget(service: RebalancingService = Depends(get_rebalancing_service)):
    return service.get_risk_budget()
