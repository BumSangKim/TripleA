from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from api.features.alerts.dependencies import get_alerts_service
from api.features.alerts.schemas import AlertItemSchema
from api.features.alerts.service import AlertsService

router = APIRouter(tags=["alerts"])


@router.get("/api/alerts/recent", response_model=List[AlertItemSchema])
def recent_alerts(
    limit: int = 10,
    svc: AlertsService = Depends(get_alerts_service),
):
    return svc.list_recent(limit)


@router.patch("/api/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    svc: AlertsService = Depends(get_alerts_service),
):
    return svc.mark_read(alert_id)


@router.post("/api/alerts/generate")
def generate_alerts(svc: AlertsService = Depends(get_alerts_service)):
    return svc.generate_alerts()
