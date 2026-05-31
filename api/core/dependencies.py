from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.db.connection import get_conn
from api.db.initialize import initialize_database
from api.services.indicator_poller import start_poller, stop_poller

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    from api.features.alerts.repository import AlertsRepository
    with get_conn() as conn:
        n = AlertsRepository(conn).generate_target_alerts()
    if n:
        logger.info(f"[startup] {n}개 목표 이탈 알림 생성")
    await start_poller(app)
    yield
    await stop_poller(app)
