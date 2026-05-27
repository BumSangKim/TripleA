import pytest

from api.strategy.account_constraints.fallbacks import build_conservative_result
from api.strategy.account_constraints.models import ConstraintAction


@pytest.mark.parametrize(
    "reason_code,blocked_field",
    [
        ("UNKNOWN_ACCOUNT_TYPE", "account_type"),
        ("MISSING_ACCOUNT_CONFIG", "account_config"),
        ("MISSING_BALANCE", "cash_balance"),
        ("MISSING_POSITION_VALUATION", "positions"),
        ("MISSING_PRODUCT_METADATA", "product"),
        ("IRP_RISKY_ASSET_DATA_MISSING", "product.is_risky_asset"),
        ("INVALID_CONSTRAINT_CONFIG", "config"),
        ("API_STATE_UNKNOWN", "api_state"),
    ],
)
def test_missing_or_unknown_context_falls_back_conservatively(reason_code, blocked_field):
    result = build_conservative_result(reason_code, context={"blocked_fields": [blocked_field]})

    assert result.allowed is False
    assert result.action in {
        ConstraintAction.NO_ACTION,
        ConstraintAction.HOLD,
        ConstraintAction.REVIEW_REQUIRED,
        ConstraintAction.RISK_REDUCE_ONLY,
    }
    assert result.reason_codes == (reason_code,)
    assert blocked_field in result.blocked_fields


def test_invalid_fallback_action_is_not_allowed():
    result = build_conservative_result("MISSING_PRODUCT_METADATA", action=ConstraintAction.ALLOW)

    assert result.allowed is False
    assert result.action == ConstraintAction.REVIEW_REQUIRED


def test_risk_reduce_only_fallback_serializes():
    result = build_conservative_result(
        "MISSING_POSITION_VALUATION",
        action=ConstraintAction.RISK_REDUCE_ONLY,
        context={"as_of_date": "2026-05-27"},
    )
    serialized = result.to_dict()

    assert serialized["allowed"] is False
    assert serialized["action"] == "RISK_REDUCE_ONLY"
    assert serialized["audit"]["as_of_date"] == "2026-05-27"
