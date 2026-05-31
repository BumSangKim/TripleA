from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from api.features.capex_cycle.dependencies import get_capex_cycle_service
from api.features.capex_cycle.report_schemas import CapexCycleReportResponse
from api.features.capex_cycle.report_service import CapexCycleReportService
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
)
from api.features.capex_cycle.service import CapexCycleService


router = APIRouter(tags=["capex-cycle"])


@router.get(
    "/api/capex-cycle/scores",
    response_model=list[CapexCycleScoreResponse | BioCapexBottleneckScoreResponse],
)
def capex_cycle_scores(
    as_of_date: date | None = None,
    asset_id: str | None = None,
    svc: CapexCycleService = Depends(get_capex_cycle_service),
):
    return svc.get_scores(as_of_date=as_of_date, asset_id=asset_id)


@router.get("/api/capex-cycle/scenarios", response_model=CapexScenarioResponse)
def capex_cycle_scenarios(
    as_of_date: date | None = None,
    svc: CapexCycleService = Depends(get_capex_cycle_service),
):
    return svc.get_scenario(as_of_date=as_of_date)


@router.get("/api/capex-cycle/valuation/{asset_id}", response_model=CapexValuationResponse)
def capex_cycle_valuation(
    asset_id: str,
    as_of_date: date | None = None,
    svc: CapexCycleService = Depends(get_capex_cycle_service),
):
    return svc.get_valuation(asset_id=asset_id, as_of_date=as_of_date)


@router.get("/api/capex-cycle/report", response_model=CapexCycleReportResponse)
def capex_cycle_report(
    as_of_date: date | None = None,
    asset_ids: list[str] | None = Query(default=None),
    svc: CapexCycleService = Depends(get_capex_cycle_service),
):
    return CapexCycleReportService(feature_service=svc).get_report(
        as_of_date=as_of_date,
        asset_ids=tuple(asset_ids) if asset_ids else None,
    )
