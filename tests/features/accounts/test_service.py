from __future__ import annotations

from pathlib import Path
from typing import Any

from api.features.accounts.service import AccountsService


class FakeAccountsRepository:
    def get_accounts(self, mode: Any) -> list:
        return [{"id": 1, "name": "Test Account"}]

    def get_account_policies(self) -> list:
        return [{"accountType": "GENERAL"}]

    def get_snapshots(self, account_id: int, limit: int) -> list:
        return []

    def save_manual_snapshot(self, account_id: int, body: Any) -> Any:
        return {"accountId": account_id}

    def set_rebalancing_inclusion(self, account_id: int, include: bool) -> bool:
        return True

    def upsert_holdings_from_rows(self, rows: list[dict]) -> int:
        return len(rows)

    def get_allocation(self) -> list:
        return [{"ticker": "005930", "weight": 1.0}]


def _service() -> AccountsService:
    return AccountsService(FakeAccountsRepository())


def test_get_accounts():
    result = _service().get_accounts("paper")
    assert result[0]["id"] == 1


def test_get_account_policies():
    result = _service().get_account_policies()
    assert result[0]["accountType"] == "GENERAL"


def test_upsert_holdings_from_rows():
    rows = [{"account_name": "Test", "ticker": "005930", "name": "Samsung",
             "quantity": "1", "avg_price": "70000", "current_price": "71000"}]
    assert _service().upsert_holdings_from_rows(rows) == 1


def test_repository_import_smoke():
    from api.features.accounts.repository import AccountsRepository
    assert AccountsRepository is not None


def test_service_no_db_dependency():
    src = Path("api/features/accounts/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
