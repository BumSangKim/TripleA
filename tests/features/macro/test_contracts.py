from __future__ import annotations

from api.features.macro.models import MacroTelegramResult
from api.features.macro.ports import IMacroRepository
from api.features.macro.schemas import MacroTelegramResponse


def test_macro_telegram_response_schema():
    r = MacroTelegramResponse(ok=True, sent=1, skipped=0, indicatorCount=5, message="ok")
    assert r.ok is True
    assert r.indicatorCount == 5


def test_macro_telegram_result_model():
    r = MacroTelegramResult(ok=True, sent=1, skipped=0, indicator_count=5, message="ok")
    assert r.indicator_count == 5


def test_imacro_repository_protocol_importable():
    assert IMacroRepository is not None
