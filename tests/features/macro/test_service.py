from __future__ import annotations

from pathlib import Path

from api.features.macro.service import MacroService


class FakeMacroRepository:
    def get_indicators(self) -> list:
        return [{"key": "FEDFUNDS", "value": 5.25}]

    def get_indicator_history(self, key: str, days: int) -> list:
        return [{"date": "2026-01-01", "value": 5.25}]



def test_get_indicators_delegates_to_repo():
    service = MacroService(FakeMacroRepository())
    result = service.get_indicators()
    assert len(result) == 1
    assert result[0]["key"] == "FEDFUNDS"


def test_get_indicator_history_delegates_to_repo():
    service = MacroService(FakeMacroRepository())
    result = service.get_indicator_history("FEDFUNDS", 30)
    assert len(result) == 1
    assert result[0]["date"] == "2026-01-01"


def test_repository_import_smoke():
    from api.features.macro.repository import MacroRepository

    assert MacroRepository is not None


def test_service_no_db_dependency():
    src = Path("api/features/macro/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
