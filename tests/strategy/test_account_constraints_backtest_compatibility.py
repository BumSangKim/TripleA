from api.strategy.account_constraints.engine import evaluate_account_constraints

from tests.strategy.account_constraint_fixtures import irp_backtest_limit_fixture


def test_same_inputs_return_same_constraint_result():
    fixture = irp_backtest_limit_fixture()

    first = evaluate_account_constraints(**fixture).to_dict()
    second = evaluate_account_constraints(**fixture).to_dict()

    assert first == second


def test_as_of_date_is_preserved_in_audit_payload():
    result = evaluate_account_constraints(**irp_backtest_limit_fixture())

    assert result.audit["as_of_date"] == "2024-12-31"


def test_backtest_fixture_reproduces_irp_limit_without_external_api():
    result = evaluate_account_constraints(**irp_backtest_limit_fixture())

    assert result.allowed is False
    assert "IRP_RISKY_ASSET_LIMIT_EXCEEDED" in result.reason_codes
    assert result.audit["product_id"] == "SPY"
