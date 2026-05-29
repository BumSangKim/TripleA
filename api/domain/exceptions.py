from __future__ import annotations

from typing import Union


class DomainError(Exception):
    """Base class for all domain errors.

    Deliberately has no HTTP status_code. HTTP mapping lives in api/core/errors.py.
    """

    def __init__(
        self,
        message: str,
        *,
        details: Union[dict, list, None] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class AccountNotFoundError(DomainError):
    """Raised when a referenced account does not exist."""


class OrderBlockedError(DomainError):
    """Raised when an order cannot be placed due to business rules."""


class ConstraintViolationError(DomainError):
    """Raised when a portfolio or risk constraint is violated."""


class DataQualityError(DomainError):
    """Raised when input data fails quality or integrity checks."""


class StrategyValidationError(DomainError):
    """Raised when strategy configuration or parameters are invalid."""
