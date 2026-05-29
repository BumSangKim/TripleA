from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.domain.exceptions import (
    AccountNotFoundError,
    ConstraintViolationError,
    DataQualityError,
    DomainError,
    OrderBlockedError,
    StrategyValidationError,
)

_STATUS_MAP: dict[type[DomainError], int] = {
    AccountNotFoundError: 404,
    OrderBlockedError: 422,
    ConstraintViolationError: 422,
    DataQualityError: 422,
    StrategyValidationError: 422,
}


def _domain_error_response(err: DomainError, status_code: int) -> JSONResponse:
    body: dict = {
        "error": type(err).__name__,
        "message": err.message,
    }
    if err.details is not None:
        body["details"] = err.details
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status_code = _STATUS_MAP.get(type(exc), 500)
        return _domain_error_response(exc, status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body: dict = {
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "details": exc.errors(),
        }
        return JSONResponse(status_code=422, content=body)
