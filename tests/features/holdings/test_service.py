from __future__ import annotations

from pathlib import Path

from api.features.holdings.service import HoldingsService


class FakeHoldingsRepository:
    def get_positions(self, account_id: int) -> list:
        return [{"ticker": "005930", "account_id": account_id}]


def test_get_positions_delegates_to_repo():
    service = HoldingsService(FakeHoldingsRepository())
    result = service.get_positions(1)
    assert len(result) == 1
    assert result[0]["ticker"] == "005930"


def test_repository_import_smoke():
    from api.features.holdings.repository import HoldingsRepository
    assert HoldingsRepository is not None


def test_service_no_db_dependency():
    src = Path("api/features/holdings/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
