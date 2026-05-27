from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from api.data.models import DataQualityCheck


CONSERVATIVE_FALLBACKS = {
    "reduce_signal_weight",
    "hold",
    "review_required",
    "use_conservative_fallback",
    "risk_reduce_only",
}


def evaluate_price_quality(
    rows: list[Any],
    *,
    dataset_key: str,
    source: str,
    as_of_date: date,
    expected_points: int,
    stale_after_days: int,
    fallback_policy: str = "use_conservative_fallback",
    extreme_jump_threshold: Decimal = Decimal("0.3"),
) -> DataQualityCheck:
    warnings: list[str] = []
    expected = max(expected_points, 1)
    missing_ratio = max(0.0, 1.0 - (len(rows) / expected))
    if missing_ratio > 0:
        warnings.append("missing_data")
    if _has_non_positive_price(rows):
        warnings.append("non_positive_price")
    if _has_duplicate_dates(rows):
        warnings.append("duplicate_date")
    if _has_extreme_jump(rows, threshold=extreme_jump_threshold):
        warnings.append("extreme_jump")
    latest_date = max((_row_date(row) for row in rows), default=None)
    is_stale = latest_date is None or (as_of_date - latest_date).days > stale_after_days
    if is_stale:
        warnings.append("stale_data")
    quality_score = _quality_score(missing_ratio, warnings, is_stale)
    return DataQualityCheck(
        dataset_key=dataset_key,
        source=source,
        as_of_date=as_of_date,
        quality_score=quality_score,
        missing_ratio=round(missing_ratio, 4),
        is_stale=is_stale,
        warnings=warnings,
        fallback_policy=_normalize_fallback(fallback_policy, quality_score),
        updated_at=datetime.now(UTC),
    )


def evaluate_macro_quality(
    rows: list[Any],
    *,
    dataset_key: str,
    source: str,
    as_of_date: date,
    stale_after_days: int,
    fallback_policy: str = "reduce_signal_weight",
) -> DataQualityCheck:
    missing_ratio = 0.0 if rows else 1.0
    latest_date = max((_row_date(row) for row in rows), default=None)
    is_stale = latest_date is None or (as_of_date - latest_date).days > stale_after_days
    warnings = []
    if missing_ratio:
        warnings.append("missing_data")
    if is_stale:
        warnings.append("stale_data")
    quality_score = _quality_score(missing_ratio, warnings, is_stale)
    return DataQualityCheck(
        dataset_key=dataset_key,
        source=source,
        as_of_date=as_of_date,
        quality_score=quality_score,
        missing_ratio=missing_ratio,
        is_stale=is_stale,
        warnings=warnings,
        fallback_policy=_normalize_fallback(fallback_policy, quality_score),
        updated_at=datetime.now(UTC),
    )


def _row_date(row: Any) -> date:
    value = getattr(row, "date", None) if not isinstance(row, dict) else row.get("date")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _row_close(row: Any) -> Decimal:
    value = getattr(row, "close", None) if not isinstance(row, dict) else row.get("close")
    return Decimal(str(value))


def _has_non_positive_price(rows: list[Any]) -> bool:
    return any(_row_close(row) <= 0 for row in rows)


def _has_duplicate_dates(rows: list[Any]) -> bool:
    dates = [_row_date(row) for row in rows]
    return len(dates) != len(set(dates))


def _has_extreme_jump(rows: list[Any], *, threshold: Decimal) -> bool:
    ordered = sorted(rows, key=_row_date)
    for prev, current in zip(ordered, ordered[1:], strict=False):
        prev_close = _row_close(prev)
        if prev_close <= 0:
            continue
        change = abs((_row_close(current) - prev_close) / prev_close)
        if change > threshold:
            return True
    return False


def _quality_score(missing_ratio: float, warnings: list[str], is_stale: bool) -> float:
    score = 1.0 - min(max(missing_ratio, 0.0), 1.0)
    score -= 0.2 * len(set(warnings) - {"missing_data", "stale_data"})
    if is_stale:
        score -= 0.2
    return round(max(0.0, min(1.0, score)), 4)


def _normalize_fallback(policy: str, quality_score: float) -> str:
    if policy not in CONSERVATIVE_FALLBACKS:
        return "review_required"
    if quality_score < 0.5 and policy == "reduce_signal_weight":
        return "use_conservative_fallback"
    return policy
