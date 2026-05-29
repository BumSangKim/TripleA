from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class TargetUpdateResponse(BaseModel):
    ok: bool


class TargetItem(BaseModel):
    id: Optional[int] = None
    asset_class: str
    target_type: Optional[str] = "asset_allocation"
    currentRatio: float
    targetRatio: float
    deviation: float
    level: str
    unit: Optional[str] = "%"


class TargetUpdate(BaseModel):
    asset_class: str
    target_value: float
    warning_thr: Optional[float] = 3.0
    danger_thr: Optional[float] = 5.0
