from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class AlertItemSchema(BaseModel):
    id: int
    level: str
    category: Optional[str]
    title: str
    message: Optional[str]
    is_read: bool
    created_at: str


class TelegramNotifyResponse(BaseModel):
    ok: bool
    sent: int
    skipped: int = 0
    message: Optional[str] = None
