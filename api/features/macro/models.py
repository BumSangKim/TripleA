from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class MacroTelegramResult:
    ok: bool
    sent: int
    skipped: int
    indicator_count: int
    message: str
    message_id: Optional[int] = None
    text: Optional[str] = None
