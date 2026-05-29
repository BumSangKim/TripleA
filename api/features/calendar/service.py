from __future__ import annotations

from typing import Any, Optional

from api.features.calendar.ports import ICalendarRepository


class CalendarService:
    def __init__(self, repo: ICalendarRepository) -> None:
        self._repo = repo

    def get_events(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[Any]:
        return self._repo.get_events(from_date=from_date, to_date=to_date)
