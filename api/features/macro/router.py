from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.features.macro.dependencies import get_macro_service
from api.features.macro.schemas import MacroIndicator, MacroTelegramResponse
from api.features.macro.service import MacroService
from api.telegram_service import TelegramConfigError, TelegramSendError

router = APIRouter(tags=["macro"])


@router.get("/api/macro/summary", response_model=List[MacroIndicator])
def macro_summary(service: MacroService = Depends(get_macro_service)):
    return service.get_indicators()


@router.get("/api/macro/history/{indicator}")
def macro_history(
    indicator: str,
    days: int = 30,
    service: MacroService = Depends(get_macro_service),
):
    return service.get_indicator_history(indicator, days)


@router.get("/api/indicators/{key}/history")
def indicator_history(
    key: str,
    days: int = 180,
    service: MacroService = Depends(get_macro_service),
):
    return service.get_indicator_history(key, days)


@router.post("/api/macro/notify/telegram", response_model=MacroTelegramResponse)
def notify_macro_telegram(
    force: bool = False,
    dry_run: bool = False,
    service: MacroService = Depends(get_macro_service),
):
    try:
        result = service.send_telegram_report(force=force, dry_run=dry_run)
    except TelegramConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except TelegramSendError as e:
        raise HTTPException(status_code=502, detail=f"Telegram 전송 실패: {e}") from e
    return MacroTelegramResponse(
        ok=result.ok,
        sent=result.sent,
        skipped=result.skipped,
        indicatorCount=result.indicator_count,
        message=result.message,
        messageId=result.message_id,
        text=result.text if dry_run else None,
    )
