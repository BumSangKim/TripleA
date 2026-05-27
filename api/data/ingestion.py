from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from api.data.models import DataQualityCheck, IngestionRun
from api.data.providers import DataProviderError, MockMacroDataProvider, MockMarketDataProvider
from api.data.quality import evaluate_macro_quality, evaluate_price_quality
from api.data.repository import (
    record_ingestion_run,
    upsert_current_quote,
    upsert_macro_rows,
    upsert_price_rows,
    upsert_quality_check,
)
from api.data.source_registry import DataSource


@dataclass(frozen=True)
class IngestionResult:
    source_id: str
    status: str
    row_count: int
    warnings: list[str]
    error_message: str | None = None


def collect_price_history(
    *,
    source: DataSource,
    start_date: date,
    end_date: date,
    provider=None,
    db_session=None,
) -> IngestionResult:
    provider = provider or MockMarketDataProvider()
    started = datetime.now(UTC)
    run_id = f"{source.source_id}:prices:{start_date.isoformat()}:{end_date.isoformat()}"
    try:
        rows = provider.get_price_history(source.symbols_or_indicators, start_date, end_date)
        upsert_price_rows(rows, db_session=db_session)
        quality = evaluate_price_quality(
            rows,
            dataset_key=f"market_price:{source.source_id}",
            source=source.provider,
            as_of_date=end_date,
            expected_points=max(1, (end_date - start_date).days + 1) * len(source.symbols_or_indicators),
            stale_after_days=source.stale_after_days,
            fallback_policy=source.fallback_policy,
        )
        upsert_quality_check(quality, db_session=db_session)
        status = "success" if rows else "empty"
        _record_run(db_session, run_id, source.source_id, status, started, len(rows), None)
        return IngestionResult(source.source_id, status, len(rows), quality.warnings)
    except DataProviderError as exc:
        quality = _failed_quality(source, f"market_price:{source.source_id}", end_date, str(exc))
        upsert_quality_check(quality, db_session=db_session)
        _record_run(db_session, run_id, source.source_id, "failed", started, 0, str(exc))
        return IngestionResult(source.source_id, "failed", 0, quality.warnings, str(exc))


def collect_macro_data(
    *,
    source: DataSource,
    start_date: date,
    end_date: date,
    provider=None,
    db_session=None,
) -> IngestionResult:
    if not source.enabled:
        return IngestionResult(source.source_id, "skipped", 0, ["source_disabled"])
    provider = provider or MockMacroDataProvider()
    started = datetime.now(UTC)
    run_id = f"{source.source_id}:macro:{start_date.isoformat()}:{end_date.isoformat()}"
    try:
        rows = provider.get_macro_indicators(source.symbols_or_indicators, start_date, end_date)
        upsert_macro_rows(rows, db_session=db_session)
        quality = evaluate_macro_quality(
            rows,
            dataset_key=f"macro:{source.source_id}",
            source=source.provider,
            as_of_date=end_date,
            stale_after_days=source.stale_after_days,
            fallback_policy=source.fallback_policy,
        )
        upsert_quality_check(quality, db_session=db_session)
        status = "success" if rows else "empty"
        _record_run(db_session, run_id, source.source_id, status, started, len(rows), None)
        return IngestionResult(source.source_id, status, len(rows), quality.warnings)
    except DataProviderError as exc:
        quality = _failed_quality(source, f"macro:{source.source_id}", end_date, str(exc))
        upsert_quality_check(quality, db_session=db_session)
        _record_run(db_session, run_id, source.source_id, "failed", started, 0, str(exc))
        return IngestionResult(source.source_id, "failed", 0, quality.warnings, str(exc))


def check_current_quotes(
    *,
    source: DataSource,
    provider=None,
    db_session=None,
) -> IngestionResult:
    provider = provider or MockMarketDataProvider()
    started = datetime.now(UTC)
    run_id = f"{source.source_id}:quotes:{started.date().isoformat()}"
    warnings: list[str] = []
    row_count = 0
    try:
        quotes = provider.get_current_quotes(source.symbols_or_indicators)
        for quote in quotes:
            upsert_current_quote(quote, db_session=db_session)
            row_count += 1
        if not quotes:
            warnings.append("empty_quote_result")
        status = "success" if quotes else "empty"
        _record_run(db_session, run_id, source.source_id, status, started, row_count, None)
        return IngestionResult(source.source_id, status, row_count, warnings)
    except DataProviderError as exc:
        _record_run(db_session, run_id, source.source_id, "failed", started, row_count, str(exc))
        return IngestionResult(source.source_id, "failed", row_count, ["provider_error"], str(exc))


def _failed_quality(source: DataSource, dataset_key: str, as_of_date: date, reason: str) -> DataQualityCheck:
    return DataQualityCheck(
        dataset_key=dataset_key,
        source=source.provider,
        as_of_date=as_of_date,
        quality_score=0.0,
        missing_ratio=1.0,
        is_stale=True,
        warnings=["provider_error", reason],
        fallback_policy=source.fallback_policy,
        updated_at=datetime.now(UTC),
    )


def _record_run(db_session, run_id: str, source_id: str, status: str, started: datetime, row_count: int, error: str | None):
    record_ingestion_run(
        IngestionRun(
            run_id=run_id,
            source_id=source_id,
            status=status,
            started_at=started,
            finished_at=datetime.now(UTC),
            row_count=row_count,
            error_message=error,
        ),
        db_session=db_session,
    )
