from __future__ import annotations

from typing import Any

from api.features.system.models import SystemStatusData
from api.features.system.ports import ISystemRepository


class SystemService:
    def __init__(self, repo: ISystemRepository) -> None:
        self._repo = repo

    def get_status(self) -> SystemStatusData:
        return self._repo.get_status_data()

    def list_modes(self) -> list[Any]:
        return self._repo.list_modes()

    def get_mode_info(self, mode: Any) -> Any:
        return self._repo.get_mode_info(mode)

    def sync_accounts(self, mode: Any) -> Any:
        return self._repo.sync_accounts(mode)
