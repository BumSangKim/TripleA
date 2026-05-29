from __future__ import annotations

from api.features.alerts.schemas import AlertItemSchema, TelegramNotifyResponse
from api.features.alerts.models import AlertData, TelegramNotifyResult
from api.features.alerts.ports import IAlertsRepository


def test_schema_instantiation():
    item = AlertItemSchema(
        id=1,
        level="warning",
        category="target",
        title="Test Alert",
        message="some message",
        is_read=False,
        created_at="2024-01-01",
    )
    assert item.id == 1


def test_model_instantiation():
    data = AlertData(
        id=1,
        level="warning",
        category="target",
        title="Test Alert",
        message=None,
        is_read=False,
        created_at="2024-01-01",
    )
    assert data.level == "warning"


def test_protocol_import():
    assert IAlertsRepository is not None
