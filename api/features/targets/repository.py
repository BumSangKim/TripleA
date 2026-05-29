from __future__ import annotations

import sqlite3
from typing import Any

from api.features.targets.models import TargetUpdateData


class TargetsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_target_deviations(self, mode: Any) -> list[Any]:
        from api.providers.router import provider_router
        return provider_router.get(mode).get_target_deviations(self._conn)

    def update_target(self, data: TargetUpdateData) -> None:
        self._conn.execute(
            """
            UPDATE targets
            SET target_value=?, warning_thr=?, danger_thr=?,
                updated_at=datetime('now','localtime')
            WHERE asset_class=?
            """,
            (data.target_value, data.warning_thr, data.danger_thr, data.asset_class),
        )
        self._conn.commit()
