from __future__ import annotations

from api.features.calendar.schemas import CalendarEventSchema
from api.features.calendar.models import CalendarEventData
from api.features.calendar.ports import ICalendarRepository


def test_schema_instantiation():
    ev = CalendarEventSchema(id=1, date="2024-01-01", time="09:00", title="FOMC", country="US", importance="high")
    assert ev.title == "FOMC"


def test_model_instantiation():
    ev = CalendarEventData(id=1, date="2024-01-01", time=None, title="CPI", country="US", importance="medium")
    assert ev.date == "2024-01-01"


def test_protocol_import():
    assert ICalendarRepository is not None
