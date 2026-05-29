import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.core.errors import register_exception_handlers
from api.domain.exceptions import (
    AccountNotFoundError,
    ConstraintViolationError,
    DataQualityError,
    DomainError,
    OrderBlockedError,
    StrategyValidationError,
)


def make_app(*routes) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    for route in routes:
        app.add_api_route(route["path"], route["endpoint"], methods=route.get("methods", ["GET"]))
    return app


# ---------------------------------------------------------------------------
# DomainError payload 테스트
# ---------------------------------------------------------------------------


class TestDomainErrorResponse:
    def test_account_not_found_returns_404(self):
        def raise_account_not_found():
            raise AccountNotFoundError("account 123 not found")

        app = make_app({"path": "/test", "endpoint": raise_account_not_found})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"] == "AccountNotFoundError"
        assert data["message"] == "account 123 not found"

    def test_order_blocked_returns_422(self):
        def raise_order_blocked():
            raise OrderBlockedError("order blocked")

        app = make_app({"path": "/test", "endpoint": raise_order_blocked})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 422
        assert resp.json()["error"] == "OrderBlockedError"

    def test_constraint_violation_returns_422(self):
        def raise_constraint():
            raise ConstraintViolationError("weight exceeded")

        app = make_app({"path": "/test", "endpoint": raise_constraint})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 422

    def test_data_quality_returns_422(self):
        def raise_data_quality():
            raise DataQualityError("stale data")

        app = make_app({"path": "/test", "endpoint": raise_data_quality})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 422

    def test_strategy_validation_returns_422(self):
        def raise_strategy():
            raise StrategyValidationError("invalid config")

        app = make_app({"path": "/test", "endpoint": raise_strategy})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 422

    def test_generic_domain_error_returns_500(self):
        def raise_generic():
            raise DomainError("unexpected domain error")

        app = make_app({"path": "/test", "endpoint": raise_generic})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 500
        assert resp.json()["error"] == "DomainError"


# ---------------------------------------------------------------------------
# details 필드 테스트
# ---------------------------------------------------------------------------


class TestDetailsField:
    def test_details_included_when_present(self):
        def raise_with_details():
            raise ConstraintViolationError(
                "weight exceeded", details={"asset": "SPY", "weight": 0.6}
            )

        app = make_app({"path": "/test", "endpoint": raise_with_details})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        data = resp.json()
        assert "details" in data
        assert data["details"]["asset"] == "SPY"

    def test_details_omitted_when_none(self):
        def raise_no_details():
            raise OrderBlockedError("blocked")

        app = make_app({"path": "/test", "endpoint": raise_no_details})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        data = resp.json()
        assert "details" not in data

    def test_details_list(self):
        def raise_list_details():
            raise DataQualityError("bad tickers", details=["SPY", "QQQ"])

        app = make_app({"path": "/test", "endpoint": raise_list_details})
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        data = resp.json()
        assert isinstance(data["details"], list)
        assert "SPY" in data["details"]


# ---------------------------------------------------------------------------
# RequestValidationError 테스트
# ---------------------------------------------------------------------------


class TestRequestValidationError:
    def test_validation_error_returns_422(self):
        from pydantic import BaseModel

        class Body(BaseModel):
            value: int

        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/test")
        def endpoint(body: Body):
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test", json={"value": "not_an_int"})
        assert resp.status_code == 422

    def test_validation_error_payload_structure(self):
        from pydantic import BaseModel

        class Body(BaseModel):
            value: int

        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/test")
        def endpoint(body: Body):
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test", json={"value": "not_an_int"})
        data = resp.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "details" in data
        assert isinstance(data["details"], list)
