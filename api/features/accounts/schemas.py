from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CsvUploadResponse(BaseModel):
    ok: bool
    inserted: int


class RebalancingInclusionResponse(BaseModel):
    ok: bool
    account_id: int
    include: bool


class AccountSummary(BaseModel):
    id: int
    name: str
    type: Optional[str]
    value: float
    profit: float
    profitRate: float
    accountType: Optional[str] = None
    connectionStatus: Optional[str] = None
    tradeStatus: Optional[str] = None
    includeInRebalancing: bool = True
    dataSource: Optional[str] = None
    lastSyncedAt: Optional[str] = None


class AccountPolicyItem(BaseModel):
    id: int
    accountType: str
    role: str
    depositPolicy: Optional[str] = None
    allowedProducts: Optional[str] = None
    rebalancePriority: Optional[str] = None
    riskNote: Optional[str] = None


class AccountSnapshotCreate(BaseModel):
    totalValue: float
    cashValue: float = 0
    domesticStockValue: float = 0
    foreignStockValue: float = 0
    bondValue: float = 0
    etfValue: float = 0
    pensionValue: float = 0
    altValue: float = 0
    snapshotAt: Optional[str] = None


class AccountSnapshotItem(AccountSnapshotCreate):
    id: int
    accountId: int
    createdAt: Optional[str] = None


class AllocationItem(BaseModel):
    asset: str
    value: float
    ratio: float
