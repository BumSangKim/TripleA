from __future__ import annotations

from fastapi import FastAPI

from api.features.router_registry import include_feature_routers


def test_include_feature_routers_adds_intraday_routes():
    app = FastAPI()
    include_feature_routers(app)
    routes = {r.path for r in app.routes}
    assert any("/api/intraday" in r for r in routes)


def test_include_feature_routers_is_callable():
    app = FastAPI()
    include_feature_routers(app)
    assert len(app.routes) > 0
