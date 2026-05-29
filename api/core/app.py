from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_cors_origins
from .dependencies import lifespan
from .errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="TripleA Dashboard API",
        version="1.0.0",
        description="개인 투자 대시보드 백엔드 API",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    from api.features.router_registry import include_feature_routers
    include_feature_routers(app)

    return app
