from __future__ import annotations

from typing import Any

from api.features.targets.models import TargetUpdateData
from api.features.targets.ports import ITargetsRepository


class TargetsService:
    def __init__(self, repo: ITargetsRepository) -> None:
        self._repo = repo

    def get_target_deviations(self, mode: Any) -> list[Any]:
        return self._repo.get_target_deviations(mode)

    def update_target(self, data: TargetUpdateData) -> None:
        self._repo.update_target(data)
