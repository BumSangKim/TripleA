from __future__ import annotations

from fastapi import APIRouter, Depends

from api.features.data_status.dependencies import get_data_status_service
from api.features.data_status.service import DataStatusService

router = APIRouter(tags=["data"])


@router.get("/api/data/status")
def data_status(svc: DataStatusService = Depends(get_data_status_service)):
    return svc.get_status()


@router.get("/api/data/status/{dataset_key:path}")
def data_status_detail(
    dataset_key: str,
    svc: DataStatusService = Depends(get_data_status_service),
):
    return svc.get_dataset_status(dataset_key)


@router.get("/api/data/quotes/latest")
def data_latest_quotes(
    symbols: str,
    market: str = "KRX",
    svc: DataStatusService = Depends(get_data_status_service),
):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return svc.get_latest_quotes(symbol_list, market=market)
