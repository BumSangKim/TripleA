from __future__ import annotations

import csv
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.features.accounts.dependencies import get_accounts_service
from api.features.accounts.schemas import (
    AccountPolicyItem,
    AccountSnapshotCreate,
    AccountSnapshotItem,
    AccountSummary,
    AllocationItem,
    CsvUploadResponse,
    RebalancingInclusionResponse,
)
from api.features.accounts.service import AccountsService

router = APIRouter(tags=["accounts"])


def _parse_mode(mode: Optional[str]) -> str:
    normalized = (mode or "local").strip().lower()
    if normalized not in {"local", "backtest"}:
        raise HTTPException(status_code=422, detail="Allowed simplified modes: local, backtest")
    return normalized


def _check_write_allowed(mode: str) -> None:
    if mode != "local":
        raise HTTPException(status_code=403, detail=f"{mode} mode is read-only")


@router.get("/api/accounts", response_model=List[AccountSummary])
def list_accounts(
    mode: Optional[str] = None,
    service: AccountsService = Depends(get_accounts_service),
):
    return service.get_accounts(_parse_mode(mode))


@router.get("/api/account-policies", response_model=List[AccountPolicyItem])
def account_policies(service: AccountsService = Depends(get_accounts_service)):
    return service.get_account_policies()



@router.get("/api/accounts/{account_id}/snapshots", response_model=List[AccountSnapshotItem])
def list_account_snapshots(
    account_id: int,
    limit: int = 20,
    service: AccountsService = Depends(get_accounts_service),
):
    return service.get_snapshots(account_id, limit)


@router.post("/api/accounts/{account_id}/manual-snapshot", response_model=AccountSnapshotItem)
def create_manual_snapshot(
    account_id: int,
    body: AccountSnapshotCreate,
    mode: Optional[str] = None,
    service: AccountsService = Depends(get_accounts_service),
):
    _check_write_allowed(_parse_mode(mode))
    try:
        return service.save_manual_snapshot(account_id, body)
    except KeyError:
        raise HTTPException(status_code=404, detail="계좌를 찾을 수 없습니다")


@router.patch("/api/accounts/{account_id}/rebalancing-inclusion", response_model=RebalancingInclusionResponse)
def update_rebalancing_inclusion(
    account_id: int,
    include: bool,
    mode: Optional[str] = None,
    service: AccountsService = Depends(get_accounts_service),
):
    _check_write_allowed(_parse_mode(mode))
    updated = service.set_rebalancing_inclusion(account_id, include)
    if not updated:
        raise HTTPException(status_code=404, detail="계좌를 찾을 수 없습니다")
    return RebalancingInclusionResponse(ok=True, account_id=account_id, include=include)


@router.post("/api/accounts/upload-csv", response_model=CsvUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    mode: Optional[str] = None,
    service: AccountsService = Depends(get_accounts_service),
):
    _check_write_allowed(_parse_mode(mode))
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    expected_fields = {"ticker", "name", "quantity", "avg_price", "current_price"}
    if not reader.fieldnames or not expected_fields.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=f"CSV 필드 누락. 필수: {expected_fields}",
        )
    rows = list(reader)
    inserted = service.upsert_holdings_from_rows(rows)
    return CsvUploadResponse(ok=True, inserted=inserted)


@router.get("/api/allocation", response_model=List[AllocationItem])
def get_allocation(service: AccountsService = Depends(get_accounts_service)):
    return service.get_allocation()
