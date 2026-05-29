from __future__ import annotations

from pathlib import Path

from api.features.strategy.service import StrategyService


class FakeRepo:
    def get_universes(self): return {"u1": {}}
    def get_profiles(self): return {"p1": {}}
    def get_sector_taxonomy(self): return {"sectors": []}


def test_get_universes():
    assert "u1" in StrategyService(FakeRepo()).get_universes()


def test_get_profiles():
    assert "p1" in StrategyService(FakeRepo()).get_profiles()


def test_service_no_db():
    src = Path("api/features/strategy/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
