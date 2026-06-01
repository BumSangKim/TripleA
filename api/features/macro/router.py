from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from api.features.macro.dependencies import get_macro_service
from api.features.macro.schemas import MacroIndicator
from api.features.macro.service import MacroService

router = APIRouter(tags=["macro"])


@router.get("/api/macro/summary", response_model=List[MacroIndicator])
def macro_summary(service: MacroService = Depends(get_macro_service)):
    return service.get_indicators()


@router.get("/api/macro/history/{indicator}")
def macro_history(
    indicator: str,
    days: int = 30,
    service: MacroService = Depends(get_macro_service),
):
    return service.get_indicator_history(indicator, days)


@router.get("/api/indicators/{key}/history")
def indicator_history(
    key: str,
    days: int = 180,
    service: MacroService = Depends(get_macro_service),
):
    return service.get_indicator_history(key, days)
