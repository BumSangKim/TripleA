from __future__ import annotations

from typing import Any, Protocol

from api.features.targets.models import TargetUpdateData


class ITargetsRepository(Protocol):
    def get_target_deviations(self, mode: Any) -> list[Any]: ...
    def update_target(self, data: TargetUpdateData) -> None: ...
