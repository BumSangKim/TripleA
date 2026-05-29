from __future__ import annotations

from fastapi import APIRouter, Depends

from api.features.strategy.dependencies import get_strategy_service
from api.features.strategy.service import StrategyService

router = APIRouter(tags=["strategy"])


@router.get("/api/strategy/universes")
def strategy_universes(service: StrategyService = Depends(get_strategy_service)):
    return service.get_universes()


@router.get("/api/strategy/profiles")
def strategy_profiles(service: StrategyService = Depends(get_strategy_service)):
    return service.get_profiles()


@router.get("/api/strategy/sector-taxonomy")
def strategy_sector_taxonomy(service: StrategyService = Depends(get_strategy_service)):
    return service.get_sector_taxonomy()
