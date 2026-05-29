from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AlertData:
    id: int
    level: str
    category: Optional[str]
    title: str
    message: Optional[str]
    is_read: bool
    created_at: str


@dataclass(frozen=True)
class TelegramNotifyResult:
    ok: bool
    sent: int
    skipped: int = 0
    message: Optional[str] = None
