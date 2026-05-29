from __future__ import annotations

from api.features.holdings.models import HoldingData
from api.features.holdings.ports import IHoldingsRepository
from api.features.holdings.schemas import HoldingResponse


def test_holding_response_schema():
    r = HoldingResponse(ticker="005930", name="Samsung", quantity=10.0)
    assert r.ticker == "005930"
    assert r.quantity == 10.0


def test_holding_data_model():
    d = HoldingData(ticker="005930", quantity=10.0)
    assert d.ticker == "005930"


def test_iholdings_repository_protocol_importable():
    assert IHoldingsRepository is not None
