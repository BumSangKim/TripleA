from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from api.features.intraday.dependencies import get_intraday_service
from api.features.intraday.service import IntradayService


router = APIRouter(prefix="/api/intraday", tags=["intraday"])


@router.get("/snapshots/latest")
def get_latest_snapshots(
    market: str | None = None,
    symbols: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    service: IntradayService = Depends(get_intraday_service),
):
    symbol_list = _split_symbols(symbols)
    snapshots = service.latest_snapshots(market=market, symbols=symbol_list, limit=limit)
    return {"snapshots": [item.to_dict() for item in snapshots]}


@router.get("/snapshots/{symbol}")
def get_symbol_snapshots(
    symbol: str,
    market: str = "KRX",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    service: IntradayService = Depends(get_intraday_service),
):
    end = end_time or datetime.now().astimezone()
    start = start_time or (end - timedelta(hours=1))
    snapshots = service.snapshots_for_symbol(
        symbol=symbol,
        market=market,
        start_at=start,
        end_at=end,
        limit=limit,
    )
    return {"snapshots": [item.to_dict() for item in snapshots]}


@router.get("/events/recent")
def get_recent_intraday_events(
    event_type: str | None = None,
    event_level: str | None = None,
    acknowledged: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    service: IntradayService = Depends(get_intraday_service),
):
    events = service.recent_events(
        event_type=event_type,
        event_level=event_level,
        acknowledged=acknowledged,
        limit=limit,
    )
    return {"events": [item.to_dict() for item in events]}


@router.get("/events/{symbol}")
def get_symbol_intraday_events(
    symbol: str,
    limit: int = Query(100, ge=1, le=500),
    service: IntradayService = Depends(get_intraday_service),
):
    events = service.symbol_events(symbol=symbol, limit=limit)
    return {"events": [item.to_dict() for item in events]}


@router.post("/events/{event_id}/acknowledge")
def acknowledge_event(
    event_id: int,
    service: IntradayService = Depends(get_intraday_service),
):
    result = service.acknowledge_event(event_id)
    if not result.ok:
        raise HTTPException(status_code=404, detail="intraday event not found")
    return {"ok": True, "event_id": event_id}


@router.post("/collect/run-once")
def run_intraday_collection_once(
    force: bool = False,
    service: IntradayService = Depends(get_intraday_service),
):
    return service.collect_once(force=force).to_dict()


def _split_symbols(symbols: str | None) -> list[str] | None:
    if not symbols:
        return None
    values = [item.strip() for item in symbols.split(",") if item.strip()]
    return values or None
