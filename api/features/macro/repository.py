from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, List, Optional

from api.features.macro.models import MacroTelegramResult
from api.features.macro.schemas import MacroIndicator
from api.features.system.schemas import KPISummary
from api.features.dashboard.schemas import Insights


MACRO_KEY_MAP = {
    "cpi":          {"name": "CPI YoY",      "unit": "%"},
    "interest":     {"name": "기준금리",       "unit": "%"},
    "unemployment": {"name": "실업률",         "unit": "%"},
    "exchange_usd": {"name": "USD/KRW",       "unit": "원"},
    "vix":          {"name": "VIX",           "unit": "pt"},
    "pmi":          {"name": "PMI",           "unit": "pt"},
    "CPIAUCSL":     {"name": "CPI YoY",      "unit": "%"},
    "UNRATE":       {"name": "실업률",         "unit": "%"},
    "FEDFUNDS":     {"name": "기준금리",       "unit": "%"},
    "DGS10":        {"name": "미국 10년채",    "unit": "%"},
    "T10Y2Y":       {"name": "장단기 스프레드","unit": "%"},
    "VIXCLS":       {"name": "VIX",           "unit": "pt"},
    "ISM_PMI":      {"name": "ISM PMI",       "unit": "pt"},
    "USD_KRW":      {"name": "USD/KRW",       "unit": "원"},
    "WTI":          {"name": "WTI 유가",      "unit": "$"},
    "DXY":          {"name": "달러인덱스",     "unit": "pt"},
    "CAPEX_MSFT":   {"name": "Microsoft CapEx", "unit": "B USD"},
    "CAPEX_GOOGL":  {"name": "Alphabet CapEx", "unit": "B USD"},
    "CAPEX_META":   {"name": "Meta CapEx",      "unit": "B USD"},
    "CAPEX_AMZN":   {"name": "Amazon CapEx",    "unit": "B USD"},
    "CAPEX_NEE":    {"name": "NextEra CapEx",   "unit": "B USD"},
    "CAPEX_DUK":    {"name": "Duke Energy CapEx", "unit": "B USD"},
    "CAPEX_SO":     {"name": "Southern CapEx",  "unit": "B USD"},
}

PREFERRED_MACRO_KEYS = [
    "CPIAUCSL", "cpi", "FEDFUNDS", "interest",
    "UNRATE", "unemployment", "USD_KRW", "exchange_usd",
    "VIXCLS", "vix", "ISM_PMI", "pmi", "DGS10", "T10Y2Y", "WTI", "DXY",
    "CPI", "BASE_RATE", "UNEMPLOYMENT", "US_CPI", "FED_RATE", "US10Y",
    "PMI_SDT", "CAPEX_MSFT", "CAPEX_GOOGL", "CAPEX_META", "CAPEX_AMZN",
    "ERCOT_LOAD_MW", "ERCOT_RESERVE_MARGIN", "PJM_LOAD_MW",
    "CAPEX_NEE", "CAPEX_DUK", "CAPEX_SO",
]


class MacroRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_indicators(self) -> List[MacroIndicator]:
        rows = self._conn.execute("""
            WITH latest AS (
                SELECT indicator, MAX(date) AS max_date
                FROM indicators GROUP BY indicator
            )
            SELECT i.indicator, i.value, i.unit, i.date, i.source,
                   (
                       SELECT p.value
                       FROM indicators p
                       WHERE p.indicator = i.indicator AND p.date < i.date
                       ORDER BY p.date DESC
                       LIMIT 1
                   ) AS prev_value
            FROM indicators i
            INNER JOIN latest ON i.indicator = latest.indicator AND i.date = latest.max_date
            ORDER BY i.indicator
        """).fetchall()

        rows_dict = {r["indicator"]: r for r in rows}
        result = []

        ordered_keys = [key for key in PREFERRED_MACRO_KEYS if key in rows_dict]
        ordered_keys.extend(sorted(key for key in rows_dict if key not in set(PREFERRED_MACRO_KEYS)))

        for key in ordered_keys:
            r = rows_dict[key]
            meta = MACRO_KEY_MAP.get(key, {"name": key, "unit": r["unit"] or ""})
            val = r["value"]
            prev = r["prev_value"]
            change = round(val - prev, 4) if val is not None and prev is not None else None
            if change is None:
                status = "stable"
            elif change > 0:
                status = "rising"
            else:
                status = "falling"
            result.append(MacroIndicator(
                key=key,
                name=meta["name"],
                value=val,
                unit=r["unit"] or meta["unit"],
                change=change,
                status=status,
                date=r["date"],
                history=self._indicator_history_values(key, days=365 * 5),
            ))
        return result

    def get_indicator_history(self, indicator: str, days: int = 180) -> list:
        from api.macro_indicator_collector import collect_indicator_history, resolve_indicator_meta

        safe_days = max(1, min(int(days or 180), 365 * 5))
        end_date = date.today()
        start = end_date - timedelta(days=safe_days)

        meta = resolve_indicator_meta(self._conn, indicator) or {}
        collect_start = _expanded_history_start(start, safe_days, meta)
        latest_in_db = _latest_indicator_date(self._conn, indicator)

        if _needs_indicator_collection(self._conn, indicator, start, end_date, meta, latest_in_db):
            collect_indicator_history(self._conn, indicator, collect_start, end_date)

        rows = _query_indicator_history(self._conn, indicator, start, end_date)
        if rows:
            return rows

        latest = _query_latest_indicator_point(self._conn, indicator, end_date)
        if latest:
            return [latest]
        return []

    def compute_macro_score(self, indicators: List[MacroIndicator]) -> int:
        if not indicators:
            return 50
        stable = sum(1 for i in indicators if i.status == "stable")
        base_score = round(stable / len(indicators) * 100)
        vix = next(
            (i.value for i in indicators
             if i.value is not None and "VIX" in (i.key or "").upper()),
            None
        )
        if vix is not None:
            if vix > 30:
                base_score = max(0, base_score - 20)
            elif vix > 20:
                base_score = max(0, base_score - 10)
        return max(0, min(100, base_score))

    def get_kpi_summary(self, macro: Optional[List[MacroIndicator]] = None) -> KPISummary:
        macro_score = self.compute_macro_score(macro) if macro else None
        row = self._conn.execute("""
            SELECT
                COALESCE(SUM(market_value), 0) AS total_assets,
                COALESCE(SUM(profit), 0) AS total_profit
            FROM holdings
        """).fetchone()
        total_assets = float(row["total_assets"] or 0)
        total_profit = float(row["total_profit"] or 0)
        invested_principal = total_assets - total_profit
        profit_rate = round(total_profit / invested_principal * 100, 2) if invested_principal > 0 else 0.0

        return KPISummary(
            totalAssets=total_assets,
            cash=0,
            todayProfit=total_profit,
            todayProfitRate=profit_rate,
            riskLevel="보통",
            macroScore=macro_score,
        )

    def build_insights(self, macro: list, kpi: KPISummary) -> Insights:
        def _find(keys: list[str]) -> float | None:
            for k in keys:
                m = next((i for i in macro if i.key == k), None)
                if m is not None:
                    return m.value
            return None

        cpi      = _find(["CPIAUCSL", "cpi"])
        rate     = _find(["FEDFUNDS", "interest"])
        vix      = _find(["VIXCLS", "vix"])
        usd_krw  = _find(["USD_KRW", "exchange_usd"])
        dgs10    = _find(["DGS10"])
        t10y2y   = _find(["T10Y2Y"])

        macro_parts: list[str] = []
        if cpi is not None:
            if cpi >= 4.0:
                macro_parts.append(f"CPI {cpi:.1f}% — 물가 상승 압력 지속")
            elif cpi >= 2.5:
                macro_parts.append(f"CPI {cpi:.1f}% — 물가 둔화 중, 목표(2%) 상회")
            else:
                macro_parts.append(f"CPI {cpi:.1f}% — 물가 안정 수준")
        if rate is not None:
            if rate >= 5.0:
                macro_parts.append(f"기준금리 {rate:.2f}% — 긴축 기조 유지")
            elif rate >= 3.0:
                macro_parts.append(f"기준금리 {rate:.2f}% — 중립 수준")
            else:
                macro_parts.append(f"기준금리 {rate:.2f}% — 완화 기조")
        if usd_krw is not None:
            macro_parts.append(f"USD/KRW {usd_krw:,.0f}원")
        macro_summary = ". ".join(macro_parts) + "." if macro_parts else "매크로 데이터를 불러오는 중입니다."

        if vix is not None:
            if vix >= 30:
                risk = f"VIX {vix:.1f} — 시장 변동성 매우 높음 ⚠️"
            elif vix >= 20:
                risk = f"VIX {vix:.1f} — 시장 변동성 보통"
            else:
                risk = f"VIX {vix:.1f} — 시장 안정 구간"
        elif t10y2y is not None:
            if t10y2y < 0:
                risk = f"장단기 금리 역전({t10y2y:.2f}%) — 경기 침체 신호 주의"
            else:
                risk = f"장단기 스프레드 {t10y2y:.2f}% — 정상 구간"
        else:
            risk = "시장 위험 지표 데이터 없음"

        if kpi.totalAssets > 0:
            port_summary = f"총자산 {kpi.totalAssets:,.0f}원, 전일 대비 {kpi.todayProfitRate:+.2f}% 변동."
        else:
            port_summary = "포트폴리오 데이터가 없습니다. 계좌/보유종목을 등록해 주세요."

        recs: list[str] = []
        if vix is not None and vix >= 25:
            recs.append("변동성 확대 구간 — 현금 비중 유지 또는 확대 검토")
        if cpi is not None and cpi >= 3.5:
            recs.append("물가 상승 지속 — 실물자산(원자재·TIPS) 비중 확인")
        if usd_krw is not None and usd_krw >= 1380:
            recs.append("고환율 구간 — 해외주식 환헤지 여부 점검")
        if dgs10 is not None and dgs10 >= 4.5:
            recs.append("미국 장기금리 고수준 — 채권 비중 재검토")
        if not recs:
            recs.append("목표 비중 유지 여부를 점검하고 리밸런싱 신호를 확인하세요")
        recommendation = ". ".join(recs) + "."

        return Insights(
            macroSummary=macro_summary,
            portfolioSummary=port_summary,
            marketRisk=risk,
            recommendation=recommendation,
        )

    def send_telegram_report(self, force: bool, dry_run: bool) -> MacroTelegramResult:
        from api.macro_telegram_report import send_daily_macro_report
        result = send_daily_macro_report(self._conn, force=force, dry_run=dry_run)
        return MacroTelegramResult(
            ok=result.ok,
            sent=result.sent,
            skipped=result.skipped,
            indicator_count=result.indicator_count,
            message=result.message,
            message_id=result.message_id,
            text=result.text,
        )

    def _indicator_history_values(self, indicator: str, days: int) -> list[float]:
        end_date = date.today()
        start = end_date - timedelta(days=max(1, min(int(days or 180), 365 * 5)))
        return [
            point["value"]
            for point in _query_indicator_history(self._conn, indicator, start, end_date)
            if point["value"] is not None
        ]


def _query_indicator_history(
    conn: sqlite3.Connection,
    indicator: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT date, value FROM indicators
        WHERE indicator = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
        """,
        (indicator, start.isoformat(), end.isoformat()),
    ).fetchall()
    return [{"date": r["date"], "value": r["value"]} for r in rows]


def _latest_indicator_date(conn: sqlite3.Connection, indicator: str) -> date | None:
    latest = conn.execute(
        "SELECT MAX(date) AS max_date FROM indicators WHERE indicator = ?",
        (indicator,),
    ).fetchone()
    if not latest or not latest["max_date"]:
        return None
    try:
        return date.fromisoformat(str(latest["max_date"])[:10])
    except ValueError:
        return None


def _earliest_indicator_date(conn: sqlite3.Connection, indicator: str) -> date | None:
    earliest = conn.execute(
        "SELECT MIN(date) AS min_date FROM indicators WHERE indicator = ?",
        (indicator,),
    ).fetchone()
    if not earliest or not earliest["min_date"]:
        return None
    try:
        return date.fromisoformat(str(earliest["min_date"])[:10])
    except ValueError:
        return None


def _query_latest_indicator_point(
    conn: sqlite3.Connection,
    indicator: str,
    end: date,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT date, value FROM indicators
        WHERE indicator = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (indicator, end.isoformat()),
    ).fetchone()
    if not row:
        return None
    return {"date": row["date"], "value": row["value"]}


def _needs_indicator_collection(
    conn: sqlite3.Connection,
    indicator: str,
    start: date,
    end: date,
    meta: dict,
    latest_date: date | None,
) -> bool:
    if not meta:
        return False
    earliest_date = _earliest_indicator_date(conn, indicator)
    if earliest_date is None:
        return True
    if meta.get("source_type") == "fmp_capex":
        return False
    if _should_collect_indicator(latest_date, end, meta):
        return True
    tolerance = _coverage_tolerance(meta)
    return earliest_date > start + timedelta(days=tolerance)


def _should_collect_indicator(latest_date: date | None, end_date: date, meta: dict) -> bool:
    if not meta:
        return False
    if latest_date is None:
        return True
    stale_days = int(meta.get("stale_days") or 0)
    return stale_days > 0 and latest_date < end_date - timedelta(days=stale_days)


def _coverage_tolerance(meta: dict) -> int:
    frequency = (meta.get("frequency") or "").strip().lower()
    if frequency == "quarterly":
        return 120
    if frequency == "monthly":
        return 60
    if frequency == "weekly":
        return 14
    return 7


def _expanded_history_start(start: date, requested_days: int, meta: dict) -> date:
    frequency = (meta.get("frequency") or "").strip().lower()
    if frequency == "quarterly":
        return start - timedelta(days=max(365 * 5 - requested_days, 0))
    if frequency == "monthly":
        return start - timedelta(days=max(365 * 2 - requested_days, 0))
    if frequency == "weekly":
        return start - timedelta(days=max(365 - requested_days, 0))
    return start
