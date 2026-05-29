from __future__ import annotations

from pathlib import Path

from api.features.targets.models import TargetUpdateData
from api.features.targets.service import TargetsService


class FakeTargetsRepository:
    def __init__(self):
        self._updated = []

    def get_target_deviations(self, mode) -> list:
        return [{"asset_class": "equity", "level": "normal"}]

    def update_target(self, data: TargetUpdateData) -> None:
        self._updated.append(data)


def test_get_target_deviations():
    service = TargetsService(FakeTargetsRepository())
    result = service.get_target_deviations("paper")
    assert result[0]["asset_class"] == "equity"


def test_update_target():
    repo = FakeTargetsRepository()
    service = TargetsService(repo)
    data = TargetUpdateData(asset_class="equity", target_value=60.0)
    service.update_target(data)
    assert len(repo._updated) == 1
    assert repo._updated[0].asset_class == "equity"


def test_service_no_db_dependency():
    src = Path("api/features/targets/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
