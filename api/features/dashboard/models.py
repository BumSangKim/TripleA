from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DashboardData:
    mode: Any
    mode_info: Any
    kpi: Any
    macro: list
    accounts: list
    allocation: list
    targets: list
    suggestions: list
    top_movers: list
    calendar: list
    alerts: list
    insights: Any
