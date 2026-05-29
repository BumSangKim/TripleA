from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.features.alerts.dependencies import get_alerts_service
from api.features.alerts.schemas import AlertItemSchema, TelegramNotifyResponse
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


@router.post("/api/alerts/notify/telegram", response_model=TelegramNotifyResponse)
def notify_telegram(
    level_filter: str = "danger",
    svc: AlertsService = Depends(get_alerts_service),
):
    try:
        result = svc.notify_telegram(level_filter)
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith("config:"):
            raise HTTPException(status_code=503, detail=msg[7:]) from e
        elif msg.startswith("send:"):
            raise HTTPException(status_code=502, detail=f"Telegram 전송 실패: {msg[5:]}") from e
        raise
    return TelegramNotifyResponse(
        ok=result.ok,
        sent=result.sent,
        skipped=result.skipped,
        message=result.message,
    )
