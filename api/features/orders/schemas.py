from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from api.providers.modes import TradingMode


class OrderDraftRequest(BaseModel):
    mode: TradingMode = TradingMode.PAPER
    source: str = "rebalancing"
    maxOrderAmount: Optional[float] = None


class OrderExecuteRequest(BaseModel):
    mode: TradingMode
    orderDraftId: int
    confirmText: Optional[str] = None


class OrderItem(BaseModel):
    id: Optional[int] = None
    draftId: Optional[int] = None
    accountId: Optional[int] = None
    assetClass: str
    side: str
    amount: float
    status: str
    reason: Optional[str] = None
    createdAt: Optional[str] = None


class OrderDraftResponse(BaseModel):
    ok: bool
    draftId: int
    mode: TradingMode
    source: str
    status: str
    totalAmount: float
    itemCount: int
    items: List[OrderItem]
    message: Optional[str] = None
