from __future__ import annotations

from typing import Any, Protocol

from api.features.macro.models import MacroTelegramResult


class IMacroRepository(Protocol):
    def get_indicators(self) -> list[Any]: ...
    def get_indicator_history(self, key: str, days: int) -> list[Any]: ...
    def send_telegram_report(self, force: bool, dry_run: bool) -> MacroTelegramResult: ...
