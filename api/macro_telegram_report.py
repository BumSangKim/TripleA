"""
Daily macro report builder and Telegram sender.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .features.macro.schemas import MacroIndicator
from .telegram_service import (
    TelegramConfigError,
    TelegramSendError,
    send_telegram_message,
)

KST = ZoneInfo("Asia/Seoul")
DAILY_MACRO_DEDUP_PREFIX = "telegram:macro-daily"

CORE_MACRO_KEYS = [
    "USD_KRW",
    "KOSPI",
    "KOSDAQ",
    "US10Y",
    "DXY",
    "WTI",
    "BRENT",
    "GOLD",
    "CPI",
    "BASE_RATE",
    "UNEMPLOYMENT",
    "US_CPI",
    "FED_RATE",
    "PMI_SDT",
    "CAPEX_MSFT",
    "CAPEX_GOOGL",
    "CAPEX_META",
    "CAPEX_AMZN",
    "ERCOT_LOAD_MW",
    "ERCOT_RESERVE_MARGIN",
    "PJM_LOAD_MW",
]


@dataclass(frozen=True)
class DailyMacroReportResult:
    ok: bool
    sent: int
    skipped: int
    indicator_count: int
    message: str
    message_id: int | None = None
    text: str | None = None


def build_daily_macro_report_text(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
) -> tuple[str, int]:
    from .features.macro.repository import MacroRepository
    macro_repo = MacroRepository(conn)
    indicators = macro_repo.get_indicators()
    kpi = macro_repo.get_kpi_summary(indicators)
    insights = macro_repo.build_insights(indicators, kpi)
    current = now or datetime.now(KST)

    by_key = {item.key: item for item in indicators}
    selected = [by_key[key] for key in CORE_MACRO_KEYS if key in by_key]
    remaining = [item for item in indicators if item.key not in CORE_MACRO_KEYS]

    lines = [
        "TripleA 금일 경제 현황 요약",
        f"기준: {current:%Y-%m-%d %H:%M} KST",
        f"매크로 스코어: {kpi.macroScore if kpi.macroScore is not None else 'N/A'}",
        f"요약: {insights.macroSummary}",
        "",
        "핵심 지표",
    ]
    lines.extend(_format_indicator_line(item) for item in selected)

    if remaining:
        lines.append("")
        lines.append(f"그 외 지표: {len(remaining)}개 DB 연동 완료")

    text = "\n".join(lines)
    if len(text) > 3900:
        text = _trim_for_telegram(lines)
    return text, len(indicators)


def send_daily_macro_report(
    conn: sqlite3.Connection,
    *,
    force: bool = False,
    dry_run: bool = False,
    now: datetime | None = None,
    requests_module: Any | None = None,
) -> DailyMacroReportResult:
    current = now or datetime.now(KST)
    send_date = current.date().isoformat()
    dedup_key = f"{DAILY_MACRO_DEDUP_PREFIX}:{send_date}"
    text, indicator_count = build_daily_macro_report_text(conn, now=current)

    if dry_run:
        return DailyMacroReportResult(
            ok=True,
            sent=0,
            skipped=0,
            indicator_count=indicator_count,
            message="dry run",
            text=text,
        )

    if not force and _already_sent(conn, dedup_key):
        return DailyMacroReportResult(
            ok=True,
            sent=0,
            skipped=1,
            indicator_count=indicator_count,
            message="오늘 이미 전송한 매크로 리포트입니다",
        )

    try:
        kwargs = {"requests_module": requests_module} if requests_module is not None else {}
        payload = send_telegram_message(text, **kwargs)
        message_id = payload.get("result", {}).get("message_id")
        _record_macro_report(conn, dedup_key, text, "SENT")
        return DailyMacroReportResult(
            ok=True,
            sent=1,
            skipped=0,
            indicator_count=indicator_count,
            message="매크로 리포트 전송 완료",
            message_id=message_id,
        )
    except TelegramConfigError:
        raise
    except TelegramSendError as exc:
        _record_macro_report(conn, dedup_key, text, "FAILED", str(exc))
        raise


def _already_sent(conn: sqlite3.Connection, dedup_key: str) -> bool:
    row = conn.execute(
        """
        SELECT id FROM notification_logs
        WHERE channel_type = 'TELEGRAM'
          AND dedup_key = ?
          AND status = 'SENT'
        LIMIT 1
        """,
        (dedup_key,),
    ).fetchone()
    return row is not None


def _record_macro_report(
    conn: sqlite3.Connection,
    dedup_key: str,
    text: str,
    status_value: str,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO notification_logs
        (channel_type, alert_type, message, dedup_key, status, sent_at, error_message)
        VALUES ('TELEGRAM', 'MACRO_DAILY', ?, ?, ?, datetime('now','localtime'), ?)
        """,
        (text, dedup_key, status_value, error_message),
    )
    conn.commit()


def _format_indicator_line(item: MacroIndicator) -> str:
    return (
        f"- {item.name}: {_format_value(item.value, item.unit)} "
        f"({_format_change(item.change)}, {_status_word(item.status)}) [{item.date or '-'}]"
    )


def _format_value(value: float | None, unit: str | None) -> str:
    number = _format_number(value)
    normalized_unit = (unit or "").strip()
    if not normalized_unit:
        return number
    if normalized_unit in {"%", "원"}:
        return f"{number}{normalized_unit}"
    return f"{number} {normalized_unit}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) >= 1000:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if abs(value) >= 100:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if abs(value) >= 10:
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _format_change(change: float | None) -> str:
    if change is None:
        return "변동 N/A"
    sign = "+" if change > 0 else ""
    return f"{sign}{_format_number(change)}"


def _status_word(status: str) -> str:
    return {"rising": "상승", "falling": "하락", "stable": "보합"}.get(status, status or "-")


def _trim_for_telegram(lines: list[str]) -> str:
    kept: list[str] = []
    length = 0
    for line in lines:
        next_length = length + len(line) + 1
        if next_length > 3800:
            break
        kept.append(line)
        length = next_length
    omitted = max(0, len(lines) - len(kept))
    if omitted:
        kept.extend(["", f"... {omitted}개 행 생략"])
    return "\n".join(kept)
