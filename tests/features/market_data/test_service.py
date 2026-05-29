from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from api.features.market_data.service import MarketDataService


@dataclass
class _FakeAssetItem:
    asset_code: str


class _FakeRepo:
    def get_asset_universe(self, *, active_only: bool = True) -> list[Any]:
        return [_FakeAssetItem("KR001"), _FakeAssetItem("KR002")]

    def get_coverage(self, asset_codes: list[str], start: date, end: date) -> Any:
        return {"ok": True, "asset_codes": asset_codes}


def test_list_assets():
    svc = MarketDataService(_FakeRepo())
    items = svc.list_assets()
    assert len(items) == 2


def test_get_coverage():
    svc = MarketDataService(_FakeRepo())
    result = svc.get_coverage(date(2024, 1, 1), date(2024, 12, 31))
    assert result["ok"] is True
    assert "KR001" in result["asset_codes"]


def test_service_no_db_import():
    from pathlib import Path
    src = Path("api/features/market_data/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
