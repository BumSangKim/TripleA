from __future__ import annotations

from api.features.accounts.models import HoldingRow
from api.features.accounts.ports import IAccountsRepository
from api.features.accounts.schemas import CsvUploadResponse, RebalancingInclusionResponse


def test_csv_upload_response_schema():
    r = CsvUploadResponse(ok=True, inserted=3)
    assert r.ok is True
    assert r.inserted == 3


def test_rebalancing_inclusion_response_schema():
    r = RebalancingInclusionResponse(ok=True, account_id=1, include=False)
    assert r.account_id == 1
    assert r.include is False


def test_holding_row_model():
    row = HoldingRow(
        account_name="test",
        ticker="005930",
        name="Samsung",
        quantity=10.0,
        avg_price=70000.0,
        current_price=71000.0,
    )
    assert row.ticker == "005930"


def test_iaccounts_repository_protocol_importable():
    assert IAccountsRepository is not None
