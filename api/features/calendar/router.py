from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends

from api.features.calendar.dependencies import get_calendar_service
from api.features.calendar.schemas import CalendarEventSchema
from api.features.calendar.service import CalendarService

router = APIRouter(tags=["calendar"])


@router.get("/api/calendar/events", response_model=List[CalendarEventSchema])
def calendar_events(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    svc: CalendarService = Depends(get_calendar_service),
):
    return svc.get_events(from_date=from_date, to_date=to_date)
