from __future__ import annotations

from typing import Any

from api.features.macro.models import MacroTelegramResult
from api.features.macro.ports import IMacroRepository


class MacroService:
    def __init__(self, repo: IMacroRepository) -> None:
        self._repo = repo

    def get_indicators(self) -> list[Any]:
        return self._repo.get_indicators()

    def get_indicator_history(self, key: str, days: int) -> list[Any]:
        return self._repo.get_indicator_history(key, days)

    def send_telegram_report(self, force: bool, dry_run: bool) -> MacroTelegramResult:
        return self._repo.send_telegram_report(force, dry_run)
