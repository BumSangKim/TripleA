from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query

from api.db import get_conn
from api.intraday.alert import acknowledge_intraday_event
from api.intraday.collector import collect_intraday_once
from api.intraday.config import load_intraday_config
from api.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.intraday.repository import latest_snapshots, recent_events, snapshots_for_symbol


router = APIRouter(prefix="/api/intraday", tags=["intraday"])


@router.get("/snapshots/latest")
def get_latest_snapshots(
    market: str | None = None,
    symbols: str | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    symbol_list = _split_symbols(symbols)
    with get_conn() as conn:
        snapshots = latest_snapshots(market=market, symbols=symbol_list, limit=limit, db_session=conn)
    return {"snapshots": [_snapshot_payload(item) for item in snapshots]}


@router.get("/snapshots/{symbol}")
def get_symbol_snapshots(
    symbol: str,
    market: str = "KRX",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
):
    end = end_time or datetime.now().astimezone()
    start = start_time or (end - timedelta(hours=1))
    with get_conn() as conn:
        snapshots = snapshots_for_symbol(
            symbol=symbol,
            market=market,
            start_at=start,
            end_at=end,
            db_session=conn,
        )[-limit:]
    return {"snapshots": [_snapshot_payload(item) for item in snapshots]}


@router.get("/events/recent")
def get_recent_intraday_events(
    event_type: str | None = None,
    event_level: str | None = None,
    acknowledged: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    with get_conn() as conn:
        events = recent_events(
            event_type=event_type,
            event_level=event_level,
            acknowledged=acknowledged,
            limit=limit,
            db_session=conn,
        )
    return {"events": [_event_payload(item) for item in events]}


@router.get("/events/{symbol}")
def get_symbol_intraday_events(symbol: str, limit: int = Query(100, ge=1, le=500)):
    with get_conn() as conn:
        events = recent_events(symbol=symbol, limit=limit, db_session=conn)
    return {"events": [_event_payload(item) for item in events]}


@router.post("/events/{event_id}/acknowledge")
def acknowledge_event(event_id: int):
    with get_conn() as conn:
        updated = acknowledge_intraday_event(conn, event_id)
    if not updated:
        raise HTTPException(status_code=404, detail="intraday event not found")
    return {"ok": True, "event_id": event_id}


@router.post("/collect/run-once")
def run_intraday_collection_once(force: bool = False):
    config = load_intraday_config()
    with get_conn() as conn:
        result = collect_intraday_once(conn, config=config, force=force)
    return {
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "requested_symbols": result.requested_symbols,
        "successful_symbols": result.successful_symbols,
        "failed_symbols": result.failed_symbols,
        "inserted_snapshots": result.inserted_snapshots,
        "status": result.status,
        "warnings": [warning.__dict__ for warning in result.warnings],
    }


def _split_symbols(symbols: str | None) -> list[str] | None:
    if not symbols:
        return None
    values = [item.strip() for item in symbols.split(",") if item.strip()]
    return values or None


def _snapshot_payload(snapshot: IntradayPriceSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "symbol": snapshot.symbol,
        "market": snapshot.market,
        "captured_at": snapshot.captured_at.isoformat(),
        "price": _decimal(snapshot.price),
        "open_price": _decimal(snapshot.open_price),
        "high_price": _decimal(snapshot.high_price),
        "low_price": _decimal(snapshot.low_price),
        "volume": _decimal(snapshot.volume),
        "value_traded": _decimal(snapshot.value_traded),
        "change_rate": _decimal(snapshot.change_rate),
        "source": snapshot.source,
        "quality_score": snapshot.quality_score,
        "is_stale": snapshot.is_stale,
    }


def _event_payload(event: IntradayEvent) -> dict:
    return {
        "id": event.id,
        "symbol": event.symbol,
        "market": event.market,
        "event_type": event.event_type,
        "event_level": event.event_level,
        "detected_at": event.detected_at.isoformat(),
        "lookback_minutes": event.lookback_minutes,
        "base_price": _decimal(event.base_price),
        "current_price": _decimal(event.current_price),
        "change_rate": _decimal(event.change_rate),
        "volume_ratio": _decimal(event.volume_ratio),
        "reason_code": event.reason_code,
        "message": event.message,
        "source_snapshot_id": event.source_snapshot_id,
        "acknowledged": event.acknowledged,
    }


def _decimal(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
