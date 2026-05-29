from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemStatusData:
    macro_last_update: Optional[str]
    holdings_last_update: Optional[str]
    total_indicators: int
    recent_7d_rows: int
    success_rate: float
    unread_alerts: int
    pipeline_status: str
    timestamp: str
