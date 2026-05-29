import pytest

from api.domain.exceptions import (
    AccountNotFoundError,
    ConstraintViolationError,
    DataQualityError,
    DomainError,
    OrderBlockedError,
    StrategyValidationError,
)


class TestDomainError:
    def test_basic_creation(self):
        err = DomainError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert err.details is None

    def test_details_dict(self):
        err = DomainError("bad input", details={"field": "price", "value": -1})
        assert isinstance(err.details, dict)
        assert err.details["field"] == "price"

    def test_details_list(self):
        err = DomainError("multiple errors", details=[{"loc": "x"}, {"loc": "y"}])
        assert isinstance(err.details, list)
        assert len(err.details) == 2

    def test_details_none(self):
        err = DomainError("no details")
        assert err.details is None

    def test_no_status_code_attribute(self):
        err = DomainError("test")
        assert not hasattr(err, "status_code"), (
            "DomainError must not have a status_code attribute"
        )

    def test_is_exception(self):
        err = DomainError("test")
        assert isinstance(err, Exception)


class TestDomainErrorSubclasses:
    def test_account_not_found_error(self):
        err = AccountNotFoundError("account 123 not found")
        assert isinstance(err, DomainError)
        assert not hasattr(err, "status_code")

    def test_order_blocked_error(self):
        err = OrderBlockedError("order blocked by constraint")
        assert isinstance(err, DomainError)
        assert not hasattr(err, "status_code")

    def test_constraint_violation_error(self):
        err = ConstraintViolationError("max weight exceeded", details={"asset": "SPY", "weight": 0.6})
        assert isinstance(err, DomainError)
        assert err.details["asset"] == "SPY"
        assert not hasattr(err, "status_code")

    def test_data_quality_error(self):
        err = DataQualityError("stale price data", details=["SPY", "QQQ"])
        assert isinstance(err, DomainError)
        assert isinstance(err.details, list)
        assert not hasattr(err, "status_code")

    def test_strategy_validation_error(self):
        err = StrategyValidationError("invalid rebalancing config")
        assert isinstance(err, DomainError)
        assert not hasattr(err, "status_code")

    def test_all_subclasses_no_status_code(self):
        subclasses = [
            AccountNotFoundError("a"),
            OrderBlockedError("b"),
            ConstraintViolationError("c"),
            DataQualityError("d"),
            StrategyValidationError("e"),
        ]
        for err in subclasses:
            assert not hasattr(err, "status_code"), (
                f"{type(err).__name__} must not have status_code"
            )

    def test_details_inheritance(self):
        err = AccountNotFoundError("not found", details={"account_id": "ACC001"})
        assert err.details["account_id"] == "ACC001"
