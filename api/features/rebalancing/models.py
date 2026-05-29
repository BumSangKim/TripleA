from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RebalanceRunData:
    run_id: int
    rows: list[Any]
