from __future__ import annotations

from typing import Any

from .config import AccountRuleConfig
from .fallbacks import build_conservative_result
from .models import (
    AccountState,
    ConstraintAction,
    ConstraintResult,
    ConstraintSeverity,
    OrderIntent,
    ProductMetadata,
)


def evaluate_account_constraints(
    account_config: AccountRuleConfig | None,
    account_state: AccountState | None,
    product: ProductMetadata | None,
    intent: OrderIntent | None,
) -> ConstraintResult:
    evaluated_rules: list[str] = []
    reason_codes: list[str] = []
    warnings: list[str] = []
    blocked_fields: list[str] = []
    review_required = False
    adjusted_quantity: float | None = None
    adjusted_weight: float | None = None

    if account_config is None:
        return build_conservative_result("MISSING_ACCOUNT_CONFIG", context={"blocked_fields": ["account_config"]})
    if account_state is None:
        return build_conservative_result("MISSING_ACCOUNT_STATE", context={"blocked_fields": ["account_state"]})
    if product is None:
        return build_conservative_result("MISSING_PRODUCT_METADATA", context={"blocked_fields": ["product"]})
    if intent is None:
        return build_conservative_result("API_STATE_UNKNOWN", context={"blocked_fields": ["intent"]})

    account_type = account_config.account_type
    audit_base = _audit_payload(account_config, account_state, product, intent, evaluated_rules)

    evaluated_rules.append("data_completeness")
    if product.tradable is None:
        reason_codes.append("MISSING_PRODUCT_METADATA")
        blocked_fields.append("product.tradable")
        review_required = True
    if product.market_status is None:
        reason_codes.append("API_STATE_UNKNOWN")
        blocked_fields.append("product.market_status")
        review_required = True

    evaluated_rules.append("account_eligibility")
    eligibility = product.account_eligibility.get(account_type)
    if eligibility is False:
        reason_codes.append("PRODUCT_NOT_TRADABLE")
        blocked_fields.append("account_eligibility")

    evaluated_rules.append("product_eligibility")
    if product.tradable is False:
        reason_codes.append("PRODUCT_NOT_TRADABLE")
        blocked_fields.append("product.tradable")
    if product.market_status not in {None, "open", "tradable"}:
        reason_codes.append("MARKET_NOT_TRADABLE")
        blocked_fields.append("product.market_status")
    if product.asset_class.value not in account_config.allowed_asset_classes:
        reason_codes.append("ASSET_CLASS_NOT_ALLOWED")
        blocked_fields.append("asset_class")
    restricted_flags = sorted(set(product.flags.active_flags()) & set(account_config.blocked_product_flags))
    if restricted_flags:
        reason_codes.append("PRODUCT_FLAG_RESTRICTED")
        blocked_fields.extend(f"product_flags.{flag}" for flag in restricted_flags)

    evaluated_rules.append("account_specific_limits")
    warnings.extend(_max_weight_warnings(account_config, product))
    if account_type == "irp" and intent.increases_risk:
        limit_result = _evaluate_irp_risky_asset_limit(account_config, account_state, product, intent)
        if limit_result:
            reason_codes.append(limit_result["reason_code"])
            blocked_fields.extend(limit_result["blocked_fields"])
            review_required = review_required or limit_result["review_required"]
            adjusted_quantity = limit_result.get("adjusted_quantity")
            adjusted_weight = limit_result.get("adjusted_weight")

    evaluated_rules.append("cash_order_sizing")
    if intent.increases_risk:
        if intent.requested_amount is not None:
            if account_state.cash_balance is None or account_state.total_value is None:
                reason_codes.append("MISSING_BALANCE")
                blocked_fields.append("cash_balance")
                review_required = True
            else:
                required_cash = intent.requested_amount + account_state.total_value * account_config.minimum_cash_buffer_ratio
                if account_state.cash_balance < required_cash:
                    reason_codes.append("INSUFFICIENT_CASH")
                    blocked_fields.append("cash_balance")
        if product.min_order_unit is not None and intent.requested_quantity is not None:
            if not _quantity_satisfies_min_unit(intent.requested_quantity, product.min_order_unit):
                reason_codes.append("MIN_ORDER_UNIT_NOT_SATISFIED")
                blocked_fields.append("requested_quantity")

    evaluated_rules.append("review_audit")
    audit = {
        **audit_base,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "warnings": list(warnings),
        "evaluated_rules": list(evaluated_rules),
    }

    if reason_codes:
        unique_reasons = tuple(dict.fromkeys(reason_codes))
        hard_block = any(
            code
            in {
                "PRODUCT_NOT_TRADABLE",
                "ASSET_CLASS_NOT_ALLOWED",
                "PRODUCT_FLAG_RESTRICTED",
                "INSUFFICIENT_CASH",
                "MIN_ORDER_UNIT_NOT_SATISFIED",
                "MARKET_NOT_TRADABLE",
                "IRP_RISKY_ASSET_LIMIT_EXCEEDED",
            }
            for code in unique_reasons
        )
        action = ConstraintAction.BLOCK if hard_block else ConstraintAction.REVIEW_REQUIRED
        severity = ConstraintSeverity.BLOCK if hard_block else ConstraintSeverity.REVIEW
        audit.update(
            {
                "allowed": False,
                "action": action.value,
                "severity": severity.value,
                "blocked_fields": list(dict.fromkeys(blocked_fields)),
                "adjusted_quantity": adjusted_quantity,
                "adjusted_weight": adjusted_weight,
            }
        )
        return ConstraintResult(
            allowed=False,
            action=action,
            severity=severity,
            constraint_type="hard_constraint" if hard_block else "data_completeness",
            reason_codes=unique_reasons,
            warnings=tuple(warnings),
            blocked_fields=tuple(dict.fromkeys(blocked_fields)),
            adjusted_quantity=adjusted_quantity,
            adjusted_weight=adjusted_weight,
            review_required=review_required or not hard_block,
            audit=audit,
        )

    audit.update(
        {
            "allowed": True,
            "action": ConstraintAction.ALLOW.value,
            "severity": ConstraintSeverity.INFO.value,
            "blocked_fields": [],
        }
    )
    return ConstraintResult.allow(audit=audit, warnings=tuple(warnings))


def _evaluate_irp_risky_asset_limit(
    account_config: AccountRuleConfig,
    account_state: AccountState,
    product: ProductMetadata,
    intent: OrderIntent,
) -> dict[str, Any] | None:
    if product.is_risky_asset is False:
        return None
    if product.is_risky_asset is None:
        return {
            "reason_code": "IRP_RISKY_ASSET_DATA_MISSING",
            "blocked_fields": ["product.is_risky_asset"],
            "review_required": True,
        }
    if account_config.risky_asset_limit is None:
        return {
            "reason_code": "INVALID_CONSTRAINT_CONFIG",
            "blocked_fields": ["risky_asset_limit"],
            "review_required": True,
        }
    if account_state.total_value is None or account_state.risky_asset_value is None:
        return {
            "reason_code": "IRP_RISKY_ASSET_DATA_MISSING",
            "blocked_fields": ["total_value", "risky_asset_value"],
            "review_required": True,
        }
    if account_state.total_value <= 0:
        return {
            "reason_code": "IRP_RISKY_ASSET_DATA_MISSING",
            "blocked_fields": ["total_value"],
            "review_required": True,
        }
    intended_amount = intent.requested_amount
    if intended_amount is None and intent.requested_quantity is not None and product.price is not None:
        intended_amount = intent.requested_quantity * product.price
    if intended_amount is None:
        return {
            "reason_code": "IRP_RISKY_ASSET_DATA_MISSING",
            "blocked_fields": ["requested_amount"],
            "review_required": True,
        }
    projected_ratio = (account_state.risky_asset_value + intended_amount) / account_state.total_value
    if projected_ratio <= account_config.risky_asset_limit:
        return None
    remaining_risky_capacity = max(
        account_state.total_value * account_config.risky_asset_limit - account_state.risky_asset_value,
        0.0,
    )
    adjusted_quantity = None
    if product.price is not None and product.price > 0 and intent.requested_quantity is not None:
        adjusted_quantity = min(intent.requested_quantity, remaining_risky_capacity / product.price)
    return {
        "reason_code": "IRP_RISKY_ASSET_LIMIT_EXCEEDED",
        "blocked_fields": ["risky_asset_limit"],
        "review_required": False,
        "adjusted_quantity": adjusted_quantity,
        "adjusted_weight": account_config.risky_asset_limit,
    }


def _audit_payload(
    account_config: AccountRuleConfig,
    account_state: AccountState,
    product: ProductMetadata,
    intent: OrderIntent,
    evaluated_rules: list[str],
) -> dict[str, Any]:
    return {
        "account_type": account_config.account_type,
        "account_role": account_config.role,
        "product_id": product.product_id,
        "symbol": product.symbol,
        "intent_type": intent.intent_type.value,
        "requested_quantity": intent.requested_quantity,
        "requested_weight": intent.requested_weight,
        "requested_amount": intent.requested_amount,
        "adjusted_quantity": None,
        "adjusted_weight": None,
        "allowed": None,
        "action": None,
        "severity": None,
        "as_of_date": intent.as_of_date or product.as_of_date or account_state.as_of_date,
        "config_version": None,
        "evaluated_rules": evaluated_rules,
    }


def _max_weight_warnings(account_config: AccountRuleConfig, product: ProductMetadata) -> list[str]:
    limit = account_config.max_account_weight_by_asset_class.get(product.asset_class.value)
    if limit is None:
        return []
    return [f"asset class {product.asset_class.value} has max account weight {limit:.4f}"]


def _quantity_satisfies_min_unit(quantity: float, min_order_unit: float) -> bool:
    if quantity <= 0 or min_order_unit <= 0:
        return False
    ratio = quantity / min_order_unit
    return abs(ratio - round(ratio)) <= 1e-9
