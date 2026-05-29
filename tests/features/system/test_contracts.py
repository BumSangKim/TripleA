from __future__ import annotations

from api.features.system.models import SystemStatusData
from api.features.system.ports import ISystemRepository
from api.features.system.schemas import HealthResponse, SystemStatusResponse


def test_health_response_schema():
    r = HealthResponse(status="ok", timestamp="2026-01-01T00:00:00")
    assert r.status == "ok"
    assert r.timestamp


def test_system_status_response_schema():
    r = SystemStatusResponse(
        macro_last_update=None,
        holdings_last_update=None,
        total_indicators=10,
        recent_7d_rows=5,
        success_rate=90.0,
        unread_alerts=0,
        pipeline_status="정상",
        timestamp="2026-01-01T00:00:00",
    )
    assert r.total_indicators == 10
    assert r.pipeline_status == "정상"


def test_system_status_data_model():
    d = SystemStatusData(
        macro_last_update=None,
        holdings_last_update=None,
        total_indicators=0,
        recent_7d_rows=0,
        success_rate=0.0,
        unread_alerts=0,
        pipeline_status="미확인",
        timestamp="2026-01-01T00:00:00",
    )
    assert d.pipeline_status == "미확인"


def test_isystem_repository_protocol_importable():
    assert ISystemRepository is not None
