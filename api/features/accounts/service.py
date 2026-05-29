from __future__ import annotations

from typing import Any

from api.features.accounts.ports import IAccountsRepository


class AccountsService:
    def __init__(self, repo: IAccountsRepository) -> None:
        self._repo = repo

    def get_accounts(self, mode: Any) -> list[Any]:
        return self._repo.get_accounts(mode)

    def get_account_policies(self) -> list[Any]:
        return self._repo.get_account_policies()

    def get_snapshots(self, account_id: int, limit: int) -> list[Any]:
        return self._repo.get_snapshots(account_id, limit)

    def save_manual_snapshot(self, account_id: int, body: Any) -> Any:
        return self._repo.save_manual_snapshot(account_id, body)

    def set_rebalancing_inclusion(self, account_id: int, include: bool) -> bool:
        return self._repo.set_rebalancing_inclusion(account_id, include)

    def upsert_holdings_from_rows(self, rows: list[dict]) -> int:
        return self._repo.upsert_holdings_from_rows(rows)

    def get_allocation(self) -> list[Any]:
        return self._repo.get_allocation()
