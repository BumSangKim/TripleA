from __future__ import annotations

from typing import Any, Optional, Protocol


class ICalendarRepository(Protocol):
    def get_events(self, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[Any]: ...
