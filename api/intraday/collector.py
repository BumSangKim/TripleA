from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from api.intraday.config import IntradayMonitoringConfig, load_intraday_config
from api.intraday.models import IntradayPriceSnapshot, ensure_aware
from api.intraday.provider import IntradaySnapshotProvider, get_intraday_provider
from api.intraday.repository import IntradayRepositoryError, insert_snapshot
from api.intraday.universe import IntradaySymbol, resolve_intraday_universe


@dataclass(frozen=True)
class CollectionWarning:
    symbol: str | None
    reason_code: str
    message: str


@dataclass(frozen=True)
class IntradayCollectionResult:
    started_at: str
    finished_at: str
    requested_symbols: int
    successful_symbols: int
    failed_symbols: int
    inserted_snapshots: int
    warnings: list[CollectionWarning] = field(default_factory=list)
    status: str = "completed"


def is_regular_session(now: datetime, config: IntradayMonitoringConfig) -> bool:
    local_now = ensure_aware(now).astimezone(ZoneInfo(config.timezone))
    start = _parse_hhmm(config.regular_session_start)
    end = _parse_hhmm(config.regular_session_end)
    return start <= local_now.time() <= end


def collect_intraday_once(
    db_session: sqlite3.Connection,
    config: IntradayMonitoringConfig | None = None,
    provider: IntradaySnapshotProvider | None = None,
    *,
    now: datetime | None = None,
    force: bool = False,
    universe: list[IntradaySymbol] | None = None,
) -> IntradayCollectionResult:
    config = config or load_intraday_config()
    started = ensure_aware(now or datetime.now(ZoneInfo(config.timezone)))
    warnings: list[CollectionWarning] = []
    if not config.enabled:
        return _result(started, started, 0, 0, 0, 0, [CollectionWarning(None, "DISABLED", "intraday monitoring is disabled")], "no_op")
    if not force and not is_regular_session(started, config):
        return _result(
            started,
            started,
            0,
            0,
            0,
            0,
            [CollectionWarning(None, "OUTSIDE_MARKET_SESSION", "outside configured regular market session")],
            "no_op",
        )

    symbols = universe if universe is not None else resolve_intraday_universe(config)
    provider = provider or get_intraday_provider(config)
    inserted = 0
    successes = 0
    failures = 0
    for batch in _batches(symbols, max(1, config.max_symbols_per_batch)):
        for symbol in batch:
            try:
                snapshot = provider.fetch_snapshot(symbol, captured_at=started, config=config)
                warning = _quality_warning(snapshot, config, collection_at=started)
                if warning is not None:
                    warnings.append(warning)
                if Decimal(str(snapshot.price)) <= 0:
                    failures += 1
                    warnings.append(CollectionWarning(symbol.symbol, "INVALID_PRICE", "provider returned non-positive price"))
                    continue
                insert_snapshot(snapshot, db_session)
                inserted += 1
                successes += 1
            except (IntradayRepositoryError, Exception) as exc:
                failures += 1
                warnings.append(CollectionWarning(symbol.symbol, "PROVIDER_ERROR", str(exc)))
    finished = ensure_aware(datetime.now(started.tzinfo))
    return _result(started, finished, len(symbols), successes, failures, inserted, warnings, "completed")


def _quality_warning(
    snapshot: IntradayPriceSnapshot,
    config: IntradayMonitoringConfig,
    *,
    collection_at: datetime,
) -> CollectionWarning | None:
    stale_seconds = abs((ensure_aware(collection_at) - ensure_aware(snapshot.captured_at)).total_seconds())
    if snapshot.is_stale or stale_seconds > config.stale_data_tolerance_seconds:
        return CollectionWarning(snapshot.symbol, "STALE_DATA", "provider data is stale or marked stale")
    if snapshot.quality_score < 0.8:
        return CollectionWarning(snapshot.symbol, "LOW_QUALITY", "provider data quality is below normal threshold")
    return None


def _batches(symbols: list[IntradaySymbol], size: int):
    for index in range(0, len(symbols), size):
        yield symbols[index:index + size]


def _result(
    started: datetime,
    finished: datetime,
    requested: int,
    successes: int,
    failures: int,
    inserted: int,
    warnings: list[CollectionWarning],
    status: str,
) -> IntradayCollectionResult:
    return IntradayCollectionResult(
        started_at=ensure_aware(started).isoformat(),
        finished_at=ensure_aware(finished).isoformat(),
        requested_symbols=requested,
        successful_symbols=successes,
        failed_symbols=failures,
        inserted_snapshots=inserted,
        warnings=warnings,
        status=status,
    )


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))
