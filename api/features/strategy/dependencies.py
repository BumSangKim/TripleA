from __future__ import annotations

from api.features.strategy.repository import StrategyRepository
from api.features.strategy.service import StrategyService


def get_strategy_service() -> StrategyService:
    return StrategyService(StrategyRepository())
