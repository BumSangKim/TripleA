from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StrategyMetadata:
    universes: dict[str, Any]
    profiles: dict[str, Any]
    sector_taxonomy: Any
