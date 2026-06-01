from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class RebalanceRunResult(BaseModel):
    ok: bool


class SuggestionItem(BaseModel):
    asset: str
    action: str
    reason: str
    deviation: float


class RebalanceResultItem(BaseModel):
    id: Optional[int] = None
    runId: Optional[int] = None
    mode: str
    accountId: Optional[int] = None
    accountType: Optional[str] = None
    assetClass: str
    currentRatio: float
    targetRatio: float
    deviation: float
    action: str
    amount: float
    reason: str
    createdAt: Optional[str] = None


class RebalanceRunResponse(BaseModel):
    ok: bool
    mode: str
    runId: int
    saved: int
    results: List[RebalanceResultItem]


class RiskBudgetItem(BaseModel):
    strategyBucket: str
    currentRatio: float
    targetRatio: float
    minRatio: Optional[float] = None
    maxRatio: Optional[float] = None
    deviation: float
    level: str
    action: str
    reason: str
