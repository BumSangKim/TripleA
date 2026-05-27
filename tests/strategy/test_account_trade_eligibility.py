from api.asset_universe_schema import AssetDefinition
from api.strategy.account_constraints.config import load_account_constraint_config
from api.strategy.account_constraints.eligibility import (
    product_metadata_from_asset_definition,
    validate_trade_eligibility,
)
from api.strategy.account_constraints.models import (
    AssetClass,
    ConstraintAction,
    IntentType,
    OrderIntent,
    ProductFlags,
    ProductMetadata,
)


def _configs():
    return load_account_constraint_config().accounts


def _intent():
    return OrderIntent(intent_type=IntentType.BUY, requested_quantity=1, as_of_date="2026-05-27")


def _product(**overrides):
    product = {
        "product_id": "SPY",
        "symbol": "SPY",
        "asset_class": AssetClass.EQUITY,
        "tradable": True,
        "flags": ProductFlags(),
        "is_risky_asset": True,
        "min_order_unit": 1,
        "market_status": "open",
        "account_eligibility": {"taxable": True, "isa": True, "irp": True},
        "as_of_date": "2026-05-27",
    }
    product.update(overrides)
    return ProductMetadata(**product)


def test_taxable_allows_plain_equity_or_etf_product():
    result = validate_trade_eligibility(_configs()["taxable"], _product(), _intent())

    assert result.allowed is True


def test_irp_blocks_restricted_product_flags():
    result = validate_trade_eligibility(
        _configs()["irp"],
        _product(flags=ProductFlags(inverse=True)),
        _intent(),
    )

    assert result.allowed is False
    assert result.action == ConstraintAction.BLOCK
    assert "PRODUCT_FLAG_RESTRICTED" in result.reason_codes


def test_isa_blocks_or_reviews_unallowed_product_group():
    result = validate_trade_eligibility(
        _configs()["isa"],
        _product(asset_class=AssetClass.ALTERNATIVE),
        _intent(),
    )

    assert result.allowed is False
    assert "ASSET_CLASS_NOT_ALLOWED" in result.reason_codes


def test_product_tradable_false_is_blocked():
    result = validate_trade_eligibility(_configs()["taxable"], _product(tradable=False), _intent())

    assert result.allowed is False
    assert "PRODUCT_NOT_TRADABLE" in result.reason_codes


def test_missing_product_metadata_is_review_required():
    result = validate_trade_eligibility(_configs()["taxable"], None, _intent())

    assert result.allowed is False
    assert result.action == ConstraintAction.REVIEW_REQUIRED
    assert result.reason_codes == ("MISSING_PRODUCT_METADATA",)


def test_asset_universe_adapter_preserves_account_eligibility():
    asset = AssetDefinition.from_dict(
        {
            "asset_id": "WATCH",
            "symbol": "WATCH",
            "name": "Watchlist",
            "asset_class": "equity",
            "sector": "technology",
            "region": "US",
            "currency": "USD",
            "instrument_type": "ETF",
            "enabled": False,
            "role": "watchlist",
            "risk_tier": "high",
            "liquidity_tier": "low",
            "min_order_unit": 1,
            "data_requirements": ["REVIEW_REQUIRED"],
            "account_eligibility": {
                "taxable": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "isa": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "pension": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "irp": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            },
            "review_required": True,
            "notes": "review required",
        }
    )

    product = product_metadata_from_asset_definition(asset, account_type="taxable", as_of_date="2026-05-27")

    assert product.tradable is False
    assert product.account_eligibility["taxable"] is False
