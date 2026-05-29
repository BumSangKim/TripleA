from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HoldingData:
    ticker: str
    name: Optional[str] = None
    quantity: Optional[float] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit: Optional[float] = None
