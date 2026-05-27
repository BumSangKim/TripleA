from api.strategy.account_constraints.config import load_account_constraint_config
from api.strategy.account_constraints.engine import evaluate_account_constraints
from api.strategy.account_constraints.models import (
    AccountState,
    AccountType,
    AssetClass,
    ConstraintAction,
    IntentType,
    OrderIntent,
    ProductFlags,
    ProductMetadata,
)


def _config():
    return load_account_constraint_config().accounts["irp"]


def _account(**overrides):
    state = {
        "account_type": AccountType.IRP,
        "total_value": 100_000,
        "cash_balance": 50_000,
        "risky_asset_value": 60_000,
        "as_of_date": "2026-05-27",
    }
    state.update(overrides)
    return AccountState(**state)


def _product(**overrides):
    product = {
        "product_id": "SPY",
        "symbol": "SPY",
        "asset_class": AssetClass.EQUITY,
        "tradable": True,
        "flags": ProductFlags(),
        "is_risky_asset": True,
        "min_order_unit": 1,
        "price": 1_000,
        "market_status": "open",
        "account_eligibility": {"irp": True},
        "as_of_date": "2026-05-27",
    }
    product.update(overrides)
    return ProductMetadata(**product)


def _buy(amount, quantity=None):
    return OrderIntent(
        intent_type=IntentType.BUY,
        requested_amount=amount,
        requested_quantity=quantity,
        as_of_date="2026-05-27",
    )


def test_irp_risky_asset_buy_below_limit_is_allowed():
    result = evaluate_account_constraints(_config(), _account(risky_asset_value=50_000), _product(), _buy(10_000, 10))

    assert result.allowed is True


def test_irp_risky_asset_buy_above_limit_is_blocked():
    result = evaluate_account_constraints(_config(), _account(risky_asset_value=65_000), _product(), _buy(10_000, 10))

    assert result.allowed is False
    assert result.action == ConstraintAction.BLOCK
    assert "IRP_RISKY_ASSET_LIMIT_EXCEEDED" in result.reason_codes
    assert result.adjusted_quantity == 5
    assert result.adjusted_weight == 0.70


def test_irp_risk_reducing_sell_is_allowed_even_when_above_limit():
    intent = OrderIntent(intent_type=IntentType.SELL, requested_amount=10_000, requested_quantity=10)
    result = evaluate_account_constraints(
        _config(),
        _account(risky_asset_value=80_000),
        _product(),
        intent,
    )

    assert result.allowed is True


def test_irp_missing_valuation_uses_conservative_fallback():
    result = evaluate_account_constraints(
        _config(),
        _account(total_value=None, risky_asset_value=None),
        _product(),
        _buy(10_000, 10),
    )

    assert result.allowed is False
    assert result.action == ConstraintAction.REVIEW_REQUIRED
    assert "IRP_RISKY_ASSET_DATA_MISSING" in result.reason_codes


def test_irp_missing_risky_asset_category_uses_conservative_fallback():
    result = evaluate_account_constraints(
        _config(),
        _account(),
        _product(is_risky_asset=None),
        _buy(10_000, 10),
    )

    assert result.allowed is False
    assert result.action == ConstraintAction.REVIEW_REQUIRED
    assert "IRP_RISKY_ASSET_DATA_MISSING" in result.reason_codes
