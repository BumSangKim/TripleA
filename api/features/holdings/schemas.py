from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class HoldingResponse(BaseModel):
    id: Optional[int] = None
    account_id: Optional[int] = None
    ticker: str
    name: Optional[str] = None
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit: Optional[float] = None


class TopMover(BaseModel):
    symbol: str
    name: Optional[str]
    price: Optional[float]
    changeRate: float
    contribution: Optional[float]
