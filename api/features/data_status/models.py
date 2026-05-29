from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DataStatusResult:
    status: str
    datasets: tuple
    last_ingestion_runs: tuple
