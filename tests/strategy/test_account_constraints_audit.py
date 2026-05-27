from api.strategy.account_constraints.audit import REQUIRED_AUDIT_FIELDS, export_constraint_audit
from api.strategy.account_constraints.engine import evaluate_account_constraints
from api.strategy.account_constraints.models import ConstraintAction, ProductFlags

from tests.strategy.test_account_constraints_engine import _account, _config, _intent, _product


def test_allowed_case_audit_payload_contains_required_fields():
    result = evaluate_account_constraints(_config(), _account(), _product(), _intent())
    audit = export_constraint_audit(result)

    assert REQUIRED_AUDIT_FIELDS.issubset(audit)
    assert audit["allowed"] is True
    assert audit["action"] == "ALLOW"


def test_blocked_case_audit_payload_contains_reasons_and_warnings():
    result = evaluate_account_constraints(
        _config(),
        _account(),
        _product(flags=ProductFlags(leveraged=True)),
        _intent(),
    )
    audit = export_constraint_audit(result)

    assert audit["allowed"] is False
    assert audit["action"] == "BLOCK"
    assert "PRODUCT_FLAG_RESTRICTED" in audit["reason_codes"]
    assert "product_flags.leveraged" in audit["blocked_fields"]


def test_review_required_audit_payload_contains_reason_codes():
    result = evaluate_account_constraints(_config(), _account(), _product(tradable=None), _intent())
    audit = export_constraint_audit(result)

    assert result.action == ConstraintAction.REVIEW_REQUIRED
    assert audit["severity"] == "review"
    assert "MISSING_PRODUCT_METADATA" in audit["reason_codes"]


def test_audit_export_reports_missing_fields_for_manual_result():
    from api.strategy.account_constraints.models import ConstraintResult, ConstraintSeverity

    result = ConstraintResult(
        allowed=False,
        action=ConstraintAction.REVIEW_REQUIRED,
        severity=ConstraintSeverity.REVIEW,
        constraint_type="manual",
        reason_codes=("MISSING_PRODUCT_METADATA",),
        audit={},
    )
    audit = export_constraint_audit(result)

    assert "missing_audit_fields" in audit
