from __future__ import annotations

from api.features.market_data.schemas import (
    AssetUniverseSchema,
    AssetCoverageSchema,
    FxCoverageSchema,
    MarketDataCoverageResponse,
)
from api.features.market_data.models import (
    AssetUniverseData,
    AssetCoverageData,
    FxCoverageData,
    MarketDataCoverageData,
)
from api.features.market_data.ports import IMarketDataRepository


def test_schema_instantiation():
    item = AssetUniverseSchema(
        assetCode="KR123",
        symbol="005930",
        name="Samsung",
        assetClass="equity",
        market="KRX",
        currency="KRW",
        sourceType="manual",
        isActive=True,
    )
    assert item.assetCode == "KR123"


def test_model_instantiation():
    data = AssetUniverseData(
        asset_code="KR123",
        symbol="005930",
        name="Samsung",
        asset_class="equity",
        market="KRX",
        currency="KRW",
        source_type="manual",
        is_active=True,
    )
    assert data.asset_code == "KR123"


def test_protocol_import():
    assert IMarketDataRepository is not None
