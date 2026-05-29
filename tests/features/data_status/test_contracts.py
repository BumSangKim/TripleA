from __future__ import annotations

from api.features.data_status.schemas import DataStatusResponse
from api.features.data_status.models import DataStatusResult
from api.features.data_status.ports import IDataStatusRepository


def test_schema_instantiation():
    resp = DataStatusResponse(status="ok", datasets=[], lastIngestionRuns=[])
    assert resp.status == "ok"


def test_model_instantiation():
    data = DataStatusResult(status="ok", datasets=(), last_ingestion_runs=())
    assert data.status == "ok"


def test_protocol_import():
    assert IDataStatusRepository is not None
