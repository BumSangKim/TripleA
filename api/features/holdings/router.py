from __future__ import annotations

from fastapi import APIRouter, Depends

from api.features.holdings.dependencies import get_holdings_service
from api.features.holdings.service import HoldingsService

router = APIRouter(tags=["accounts"])


@router.get("/api/accounts/{account_id}/positions")
def get_positions(
    account_id: int,
    service: HoldingsService = Depends(get_holdings_service),
):
    return service.get_positions(account_id)
