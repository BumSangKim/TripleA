from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TargetUpdateData:
    asset_class: str
    target_value: float
    warning_thr: Optional[float] = 3.0
    danger_thr: Optional[float] = 5.0
