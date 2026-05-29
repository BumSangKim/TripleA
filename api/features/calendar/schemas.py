from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class CalendarEventSchema(BaseModel):
    id: Optional[int] = None
    date: str
    time: Optional[str]
    title: str
    country: str
    importance: str
