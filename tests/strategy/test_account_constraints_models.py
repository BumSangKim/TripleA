import pytest

from api.strategy.account_constraints.models import (
    AccountConstraintModelError,
    AccountState,
    AccountType,
    AssetClass,
    ConstraintAction,
    ConstraintResult,
    ConstraintSeverity,
    IntentType,
    OrderIntent,
    ProductFlags,
    ProductMetadata,
    account_type_from_string,
)


def test_account_constraint_models_can_be_created():
    product = ProductMetadata(
        product_id="SPY",
        symbol="SPY",
        asset_class=AssetClass.EQUITY,
        tradable=True,
        is_risky_asset=True,
    )
    account = AccountState(
        account_type=AccountType.TAXABLE,
        total_value=100_000,
        cash_balance=10_000,
    )
    intent = OrderIntent(intent_type=IntentType.BUY, requested_quantity=1)

    assert product.flags.active_flags() == ()
    assert account.account_type == AccountType.TAXABLE
    assert intent.increases_risk is True


def test_invalid_account_type_raises():
    with pytest.raises(AccountConstraintModelError, match="unknown account type"):
        account_type_from_string("mystery")


def test_unknown_product_flag_does_not_become_active():
    flags = ProductFlags.from_iterable(["leveraged", "unknown_flag"])

    assert flags.leveraged is True
    assert "unknown_flag" not in flags.active_flags()


def test_constraint_result_serialization():
    result = ConstraintResult(
        allowed=False,
        action=ConstraintAction.REVIEW_REQUIRED,
        severity=ConstraintSeverity.REVIEW,
        constraint_type="data_completeness",
        reason_codes=("MISSING_PRODUCT_METADATA",),
        warnings=("review product metadata",),
        blocked_fields=("product",),
        review_required=True,
        audit={"as_of_date": "2026-05-27"},
    )

    serialized = result.to_dict()

    assert serialized["allowed"] is False
    assert serialized["action"] == "REVIEW_REQUIRED"
    assert serialized["reason_codes"] == ["MISSING_PRODUCT_METADATA"]
    assert serialized["audit"]["as_of_date"] == "2026-05-27"


def test_sell_intent_is_risk_reducing():
    intent = OrderIntent(intent_type=IntentType.SELL, requested_quantity=1)

    assert intent.reduces_risk is True
    assert intent.increases_risk is False
