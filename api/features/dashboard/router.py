from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.features.dashboard.dependencies import get_dashboard_service
from api.features.dashboard.schemas import DashboardSummarySchema
from api.features.dashboard.service import DashboardService
from api.providers.modes import normalize_mode

router = APIRouter(tags=["dashboard"])


def _parse_mode(mode: Optional[str]):
    try:
        return normalize_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/api/dashboard/summary", response_model=DashboardSummarySchema)
def dashboard_summary(
    mode: Optional[str] = None,
    svc: DashboardService = Depends(get_dashboard_service),
):
    trading_mode = _parse_mode(mode)
    data = svc.get_summary(trading_mode)
    return DashboardSummarySchema(
        mode=data.mode,
        modeInfo=data.mode_info,
        kpi=data.kpi,
        macro=data.macro,
        accounts=data.accounts,
        allocation=data.allocation,
        targets=data.targets,
        suggestions=data.suggestions,
        topMovers=data.top_movers,
        calendar=data.calendar,
        alerts=data.alerts,
        insights=data.insights,
    )
