from __future__ import annotations

from api.features.capex_cycle.service import CapexCycleService


def get_capex_cycle_service() -> CapexCycleService:
    return CapexCycleService()
