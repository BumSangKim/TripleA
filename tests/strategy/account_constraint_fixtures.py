from api.strategy.account_constraints.config import load_account_constraint_config
from api.strategy.account_constraints.models import (
    AccountState,
    AccountType,
    AssetClass,
    IntentType,
    OrderIntent,
    ProductFlags,
    ProductMetadata,
)


def irp_backtest_limit_fixture():
    return {
        "account_config": load_account_constraint_config().accounts["irp"],
        "account_state": AccountState(
            account_type=AccountType.IRP,
            total_value=100_000,
            cash_balance=40_000,
            risky_asset_value=69_000,
            as_of_date="2024-12-31",
        ),
        "product": ProductMetadata(
            product_id="SPY",
            symbol="SPY",
            asset_class=AssetClass.EQUITY,
            tradable=True,
            flags=ProductFlags(),
            is_risky_asset=True,
            min_order_unit=1,
            price=1_000,
            market_status="open",
            account_eligibility={"irp": True},
            as_of_date="2024-12-31",
        ),
        "intent": OrderIntent(
            intent_type=IntentType.BUY,
            requested_quantity=2,
            requested_amount=2_000,
            as_of_date="2024-12-31",
        ),
    }
