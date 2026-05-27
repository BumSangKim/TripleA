from __future__ import annotations

from api.asset_universe_schema import AssetDefinition, get_account_eligibility

from .config import AccountRuleConfig
from .engine import evaluate_account_constraints
from .models import (
    AssetClass,
    OrderIntent,
    ProductFlags,
    ProductMetadata,
)


def validate_trade_eligibility(
    account_config: AccountRuleConfig | None,
    product: ProductMetadata | None,
    intent: OrderIntent | None,
):
    return evaluate_account_constraints(
        account_config,
        account_state=_minimal_account_state(account_config),
        product=product,
        intent=intent,
    )


def product_metadata_from_asset_definition(
    asset: AssetDefinition,
    *,
    account_type: str,
    as_of_date: str | None = None,
) -> ProductMetadata:
    eligibility = get_account_eligibility(asset, account_type)
    flags = _flags_from_asset(asset)
    return ProductMetadata(
        product_id=asset.asset_id,
        symbol=asset.symbol,
        asset_class=_asset_class(asset.asset_class),
        tradable=asset.enabled and asset.eligible_for_order_candidate,
        flags=flags,
        is_risky_asset=_is_risky_asset(asset.asset_class, asset.risk_tier),
        min_order_unit=asset.min_order_unit,
        price=None,
        market_status="open" if asset.enabled else "disabled",
        account_eligibility={eligibility.account_type: eligibility.is_actionable()},
        as_of_date=as_of_date,
    )


def _minimal_account_state(account_config: AccountRuleConfig | None):
    from .models import AccountState, AccountType

    try:
        account_type = AccountType((account_config.account_type if account_config else "taxable"))
    except ValueError:
        account_type = AccountType.TAXABLE
    return AccountState(
        account_type=account_type,
        total_value=0,
        cash_balance=0,
        risky_asset_value=0,
    )


def _asset_class(value: str) -> AssetClass:
    try:
        return AssetClass(str(value or "").strip())
    except ValueError:
        return AssetClass.UNKNOWN


def _flags_from_asset(asset: AssetDefinition) -> ProductFlags:
    text = " ".join(
        str(value or "").lower()
        for value in (asset.instrument_type, asset.notes, asset.name)
    )
    return ProductFlags(
        leveraged="leveraged" in text,
        inverse="inverse" in text,
        futures_like="futures" in text or "futures_like" in text,
        complex_product="complex" in text,
    )


def _is_risky_asset(asset_class: str, risk_tier: str) -> bool | None:
    normalized_class = str(asset_class or "").strip()
    normalized_risk = str(risk_tier or "").strip()
    if normalized_class in {"cash", "bond"} and normalized_risk in {"low", "medium"}:
        return False
    if normalized_class in {"equity", "commodity", "real_asset", "alternative", "hedge"}:
        return True
    return None
