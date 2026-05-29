from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.features.targets.dependencies import get_targets_service
from api.features.targets.models import TargetUpdateData
from api.features.targets.schemas import TargetItem, TargetUpdate, TargetUpdateResponse
from api.features.targets.service import TargetsService
from api.providers.modes import normalize_mode

router = APIRouter(tags=["targets"])


def _parse_mode(mode: Optional[str]):
    try:
        return normalize_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/api/targets", response_model=List[TargetItem])
def get_targets(
    mode: Optional[str] = None,
    service: TargetsService = Depends(get_targets_service),
):
    return service.get_target_deviations(_parse_mode(mode))


@router.put("/api/targets", response_model=TargetUpdateResponse)
def update_target(
    body: TargetUpdate,
    service: TargetsService = Depends(get_targets_service),
):
    data = TargetUpdateData(
        asset_class=body.asset_class,
        target_value=body.target_value,
        warning_thr=body.warning_thr,
        danger_thr=body.danger_thr,
    )
    service.update_target(data)
    return TargetUpdateResponse(ok=True)
