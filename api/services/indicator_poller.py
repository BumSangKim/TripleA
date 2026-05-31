"""
api/services/indicator_poller.py

실시간 수집 가능한 지표를 config/indicators.yaml의 collect_interval_seconds 주기로 폴링한다.
- yahoo_quote / hybrid_market_fred 계열 지표가 대상 (1분 주기)
- FRED / ecos_keystat / fmp_capex 등은 collect_interval_seconds 미설정 → 폴링 비대상
- FastAPI lifespan 에서 start_poller() / stop_poller() 를 호출한다.
- 외부 의존성 추가 없음 (APScheduler 불필요) — asyncio + ThreadPoolExecutor 사용
- 1분 폴링은 yfinance fast_info.last_price(실시간 호가)를 사용, 종가가 아닌 현재가를 upsert한다.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import TYPE_CHECKING, Any

from api.macro_indicator_collector import load_indicator_catalog
from api.db.connection import get_conn

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("uvicorn.error")

# I/O 스레드풀: yfinance 등 blocking I/O 분리
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="poller")

# app.state에 저장할 태스크 목록 키
_TASKS_KEY = "poll_tasks"

# yahoo_quote / hybrid_market_fred 만 fast_info 폴링 대상
_REALTIME_SOURCE_TYPES = {"yahoo_quote", "hybrid_market_fred"}


def load_poll_groups() -> dict[int, list[str]]:
    """
    indicators.yaml 을 읽어 {interval_seconds: [indicator_id, ...]} 딕셔너리를 반환한다.
    collect_interval_seconds 가 없거나 null 인 지표는 제외된다.
    """
    catalog = load_indicator_catalog()
    groups: dict[int, list[str]] = {}
    for key, meta in catalog.items():
        interval = meta.get("collect_interval_seconds")
        if not interval:
            continue
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            continue
        if interval <= 0:
            continue
        groups.setdefault(interval, []).append(key)
    return groups


def _resolve_meta(indicator: str) -> dict[str, Any]:
    """YAML 메타 + _INDICATOR_OVERRIDES 병합."""
    from api.macro_indicator_collector import _INDICATOR_OVERRIDES
    catalog = load_indicator_catalog()
    meta = {**catalog.get(indicator, {}), **_INDICATOR_OVERRIDES.get(indicator, {})}
    return meta


def _fetch_realtime_quotes(indicators: list[str]) -> list[tuple[str, str, float, str, str | None]]:
    """
    yfinance fast_info.last_price 를 사용해 현재 실시간 호가를 조회한다.
    반환: [(date_str, indicator, value, source, unit), ...]
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[poller] yfinance not installed; skipping realtime fetch")
        return []

    today = date.today().isoformat()
    rows: list[tuple[str, str, float, str, str | None]] = []

    for ind in indicators:
        meta = _resolve_meta(ind)
        source_type = meta.get("source_type", "")
        if source_type not in _REALTIME_SOURCE_TYPES:
            continue
        symbol = meta.get("symbol")
        if not symbol:
            continue
        try:
            ticker = yf.Ticker(symbol)
            price = getattr(ticker.fast_info, "last_price", None)
            if price is None or price != price:  # None 또는 NaN 제외
                logger.debug("[poller] %s (%s) fast_info.last_price 없음", ind, symbol)
                continue
            rows.append((today, ind, float(price), f"Yahoo:{symbol}", meta.get("unit")))
        except Exception as exc:
            logger.warning("[poller] %s (%s) fast_info 오류: %s", ind, symbol, exc)

    return rows


def _poll_once(indicators: list[str]) -> dict[str, int]:
    """
    blocking: 지정된 지표 목록의 현재 실시간 호가를 수집해 DB에 upsert한다.
    ThreadPoolExecutor 내부에서 실행된다.
    """
    rows = _fetch_realtime_quotes(indicators)
    results: dict[str, int] = {ind: 0 for ind in indicators}

    if not rows:
        return results

    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO indicators
            (date, indicator, value, source, unit, updated)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
            """,
            rows,
        )
        conn.commit()

    for _date, ind, _value, _source, _unit in rows:
        results[ind] = 1

    return results


async def _poll_loop(interval: int, indicators: list[str]) -> None:
    """interval 초마다 indicators를 폴링하는 무한 루프."""
    loop = asyncio.get_running_loop()
    logger.info("[poller] interval=%ds: %d개 지표 폴링 시작 → %s", interval, len(indicators), indicators)
    while True:
        try:
            results = await loop.run_in_executor(
                _EXECUTOR,
                _poll_once,
                indicators,
            )
            updated = {k: v for k, v in results.items() if v > 0}
            if updated:
                logger.info("[poller] interval=%ds 수집 완료: %d개 갱신", interval, len(updated))
        except asyncio.CancelledError:
            logger.info("[poller] interval=%ds 폴링 태스크 취소됨", interval)
            raise
        except Exception as exc:
            logger.warning("[poller] interval=%ds 폴링 오류: %s", interval, exc)
        await asyncio.sleep(interval)


async def start_poller(app: FastAPI) -> None:
    """
    indicators.yaml 을 읽어 interval 그룹별로 asyncio 태스크를 생성하고
    app.state.poll_tasks 에 저장한다.
    """
    groups = load_poll_groups()
    if not groups:
        logger.info("[poller] collect_interval_seconds 설정된 지표 없음, 폴링 비활성")
        return

    tasks: list[asyncio.Task] = []
    for interval, indicators in groups.items():
        task = asyncio.create_task(
            _poll_loop(interval, indicators),
            name=f"poller_{interval}s",
        )
        tasks.append(task)

    app.state.poll_tasks = tasks
    logger.info("[poller] %d개 폴링 태스크 시작 완료", len(tasks))


async def stop_poller(app: FastAPI) -> None:
    """
    app.state.poll_tasks 의 모든 태스크를 취소하고 완료를 기다린다.
    """
    tasks: list[asyncio.Task] = getattr(app.state, _TASKS_KEY, [])
    if not tasks:
        return
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("[poller] 모든 폴링 태스크 종료")
