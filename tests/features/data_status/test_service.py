from __future__ import annotations

from typing import Any

from api.features.data_status.service import DataStatusService


class _FakeRepo:
    def get_status(self) -> Any:
        return {"status": "ok", "datasets": [], "lastIngestionRuns": []}

    def get_dataset_status(self, dataset_key: str) -> Any:
        return {"datasetKey": dataset_key, "status": "ok"}

    def get_latest_quotes(self, symbols: list[str], *, market: str = "KRX") -> Any:
        return {"symbols": symbols, "market": market}


def test_get_status():
    svc = DataStatusService(_FakeRepo())
    result = svc.get_status()
    assert result["status"] == "ok"


def test_get_dataset_status():
    svc = DataStatusService(_FakeRepo())
    result = svc.get_dataset_status("price_krx")
    assert result["datasetKey"] == "price_krx"


def test_service_no_db_import():
    from pathlib import Path
    src = Path("api/features/data_status/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
