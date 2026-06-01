from __future__ import annotations

import sqlite3
from typing import Any

from api.features.targets.models import TargetUpdateData
from api.features.targets.schemas import TargetItem


class TargetsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_target_deviations(self, mode: Any) -> list[Any]:
        return get_local_target_deviations(self._conn)

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


def get_local_target_deviations(conn: sqlite3.Connection) -> list[TargetItem]:
    targets = conn.execute(
        "SELECT id, target_type, asset_class, target_value, warning_thr, danger_thr FROM targets"
    ).fetchall()
    allocation = _allocation_from_holdings(conn)
    result: list[TargetItem] = []
    for target in targets:
        target_type = target["target_type"] or "asset_allocation"
        target_value = float(target["target_value"] or 0)
        if target_type == "asset_allocation":
            current = allocation.get(target["asset_class"], 0.0)
            unit = "%"
        else:
            current = target_value
            unit = "%"
        deviation = round(current - target_value, 2)
        if abs(deviation) >= float(target["danger_thr"] or 0):
            level = "danger"
        elif abs(deviation) >= float(target["warning_thr"] or 0):
            level = "warning"
        else:
            level = "normal"
        result.append(TargetItem(
            id=target["id"],
            asset_class=target["asset_class"],
            target_type=target_type,
            currentRatio=current,
            targetRatio=target_value,
            deviation=deviation,
            level=level,
            unit=unit,
        ))
    return result


def _allocation_from_holdings(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT asset_class, SUM(COALESCE(market_value, value, 0)) AS total
        FROM holdings
        WHERE asset_class IS NOT NULL
        GROUP BY asset_class
        """
    ).fetchall()
    grand_total = sum(float(row["total"] or 0) for row in rows)
    if grand_total <= 0:
        return {}
    return {
        row["asset_class"]: round(float(row["total"] or 0) / grand_total * 100, 2)
        for row in rows
    }
