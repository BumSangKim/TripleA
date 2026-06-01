from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class MacroIndicator(BaseModel):
    key: str
    name: str
    value: Optional[float]
    unit: Optional[str]
    change: Optional[float]
    status: str
    date: Optional[str]
    history: Optional[List[float]] = None
