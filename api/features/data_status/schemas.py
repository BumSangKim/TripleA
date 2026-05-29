from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class DataStatusResponse(BaseModel):
    status: str
    datasets: List[Dict[str, Any]]
    lastIngestionRuns: List[Dict[str, Any]]
