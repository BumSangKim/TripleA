from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.features.orders.dependencies import get_orders_service
from api.features.orders.models import OrderDraftParams, OrderExecuteParams
from api.features.orders.schemas import OrderDraftRequest, OrderDraftResponse, OrderExecuteRequest
from api.features.orders.service import OrdersService
from api.providers.modes import normalize_mode

router = APIRouter(tags=["orders"])


@router.get("/api/orders/drafts", response_model=List[OrderDraftResponse])
def order_drafts(
    mode: Optional[str] = None,
    limit: int = 20,
    service: OrdersService = Depends(get_orders_service),
):
    from api.providers.modes import normalize_mode as _nm
    trading_mode = _nm(mode) if mode else None
    return service.list_drafts(trading_mode, limit)


@router.post("/api/orders/draft", response_model=OrderDraftResponse)
def draft_orders(
    body: OrderDraftRequest,
    service: OrdersService = Depends(get_orders_service),
):
    try:
        params = OrderDraftParams(
            mode=body.mode,
            source=body.source,
            max_order_amount=body.maxOrderAmount,
        )
        return service.create_draft(params)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/orders/execute", response_model=OrderDraftResponse)
def execute_order_draft(
    body: OrderExecuteRequest,
    service: OrdersService = Depends(get_orders_service),
):
    try:
        params = OrderExecuteParams(
            mode=body.mode,
            order_draft_id=body.orderDraftId,
            confirm_text=body.confirmText,
        )
        return service.execute_draft(params)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
