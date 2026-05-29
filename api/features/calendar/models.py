from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CalendarEventData:
    id: Optional[int]
    date: str
    time: Optional[str]
    title: str
    country: str
    importance: str
