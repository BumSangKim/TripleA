from __future__ import annotations

from typing import Any


class StrategyRepository:
    def get_universes(self) -> dict[str, Any]:
        from api.strategy_config import list_universe_ids, load_investment_universe
        return {uid: load_investment_universe(uid) for uid in list_universe_ids()}

    def get_profiles(self) -> dict[str, Any]:
        from api.strategy_config import list_risk_profiles, load_strategy_profile
        return {pid: load_strategy_profile(pid) for pid in list_risk_profiles()}

    def get_sector_taxonomy(self) -> Any:
        from api.strategy_config import load_sector_taxonomy
        return load_sector_taxonomy()
