from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class MacroTelegramResponse(BaseModel):
    ok: bool
    sent: int
    skipped: int
    indicatorCount: int
    message: str
    messageId: Optional[int] = None
    text: Optional[str] = None


class MacroIndicator(BaseModel):
    key: str
    name: str
    value: Optional[float]
    unit: Optional[str]
    change: Optional[float]
    status: str
    date: Optional[str]
    history: Optional[List[float]] = None
