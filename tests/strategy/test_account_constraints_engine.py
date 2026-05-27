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


def _config(account_type="taxable"):
    return load_account_constraint_config().accounts[account_type]


def _account(account_type=AccountType.TAXABLE, **overrides):
    state = {
        "account_type": account_type,
        "total_value": 100_000,
        "cash_balance": 20_000,
        "risky_asset_value": 30_000,
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
        "price": 500,
        "market_status": "open",
        "account_eligibility": {"taxable": True, "irp": True, "isa": True, "pension": True},
        "as_of_date": "2026-05-27",
    }
    product.update(overrides)
    return ProductMetadata(**product)


def _intent(**overrides):
    intent = {
        "intent_type": IntentType.BUY,
        "requested_quantity": 1,
        "requested_amount": 500,
        "as_of_date": "2026-05-27",
    }
    intent.update(overrides)
    return OrderIntent(**intent)


def test_normal_allowed_case():
    result = evaluate_account_constraints(_config(), _account(), _product(), _intent())

    assert result.allowed is True
    assert result.action == ConstraintAction.ALLOW
    assert result.audit["evaluated_rules"]


def test_unknown_or_missing_account_config_is_review_required():
    result = evaluate_account_constraints(None, _account(), _product(), _intent())

    assert result.allowed is False
    assert result.action == ConstraintAction.REVIEW_REQUIRED
    assert result.reason_codes == ("MISSING_ACCOUNT_CONFIG",)


def test_product_not_tradable_is_blocked():
    result = evaluate_account_constraints(_config(), _account(), _product(tradable=False), _intent())

    assert result.allowed is False
    assert result.action == ConstraintAction.BLOCK
    assert "PRODUCT_NOT_TRADABLE" in result.reason_codes


def test_restricted_flag_is_blocked():
    result = evaluate_account_constraints(
        _config(),
        _account(),
        _product(flags=ProductFlags(leveraged=True)),
        _intent(),
    )

    assert result.allowed is False
    assert "PRODUCT_FLAG_RESTRICTED" in result.reason_codes


def test_missing_metadata_is_review_required():
    result = evaluate_account_constraints(_config(), _account(), _product(tradable=None), _intent())

    assert result.allowed is False
    assert result.action == ConstraintAction.REVIEW_REQUIRED
    assert "MISSING_PRODUCT_METADATA" in result.reason_codes


def test_multiple_reason_codes_are_accumulated():
    result = evaluate_account_constraints(
        _config(),
        _account(cash_balance=100),
        _product(flags=ProductFlags(inverse=True), min_order_unit=1),
        _intent(requested_quantity=0.5, requested_amount=500),
    )

    assert result.allowed is False
    assert {
        "PRODUCT_FLAG_RESTRICTED",
        "INSUFFICIENT_CASH",
        "MIN_ORDER_UNIT_NOT_SATISFIED",
    }.issubset(result.reason_codes)
