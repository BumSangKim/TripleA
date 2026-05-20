# telegram_sender.py
# 텔레그램 봇을 통해 경제지표 요약 및 차트 전송
import io
import logging
import sqlite3
from datetime import date

import pandas as pd
import requests

from config import TG_TOKEN, get_chat_id
from summarizer import build_summary, build_capex_summary, build_equity_summary
from chart_generator import create_multi_chart, create_capex_chart
from database import get_latest, is_report_sent_today, mark_report_sent, get_upcoming_events

logger = logging.getLogger(__name__)

CHART_INDICATORS = [
    ("KOSPI", "코스피"),
    ("USD_KRW", "원/달러 환율"),
    ("CPI", "소비자물가(CPI)"),
    ("DUBAI_OIL", "두바이유"),
    ("WTI", "WTI 국제유가"),
    ("PMI_SDT", "공급망압력(GSCPI·PMI)"),
]


def _tg_send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """텔레그램 메시지 전송."""
    chat_id = get_chat_id()
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID 없음 - 텔레그램 전송 건너뜀")
        logger.info(f"[미전송 메시지 미리보기]\n{text[:300]}")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
        logger.info(f"[Telegram] 메시지 전송 완료 (chat_id={chat_id})")
        return True
    except Exception as e:
        logger.error(f"텍스트 전송 실패: {e}")
        return False


def _tg_send_photo(photo_buf: io.BytesIO, caption: str = "") -> bool:
    """텔레그램 사진 전송."""
    chat_id = get_chat_id()
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID 없음 - 차트 전송 건너뜀")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    photo_buf.seek(0)
    try:
        res = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": ("chart.png", photo_buf, "image/png")},
            timeout=30,
        )
        res.raise_for_status()
        logger.info("[Telegram] 차트 전송 완료")
        return True
    except Exception as e:
        logger.error(f"차트 전송 실패: {e}")
        return False


def _tg_send_document(doc_buf: io.BytesIO, filename: str, caption: str = "") -> bool:
    """텔레그램 문서(파일) 전송."""
    chat_id = get_chat_id()
    if not chat_id:
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
    doc_buf.seek(0)
    try:
        res = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (filename, doc_buf, "text/csv")},
            timeout=30,
        )
        res.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"CSV 전송 실패: {e}")
        return False


def format_change(val) -> str:
    if val is None:
        return "N/A"
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "➡")
    return f"{arrow} {val:+.2f}%"


def _fmt_latest(info: dict, money: bool = False, digits: int = 2) -> str:
    if not info or "error" in info or info.get("latest") is None:
        return "N/A"
    prefix = "$" if money else ""
    unit = info.get("unit", "")
    return f"{prefix}{info['latest']:,.{digits}f} {unit}".strip()


def _capex_level(qoq_pct) -> str:
    if qoq_pct is None:
        return "L? (N/A)"
    if qoq_pct >= 0:
        return "L0 ✅"
    if qoq_pct >= -5:
        return "L1 ⚠️"
    if qoq_pct >= -15:
        return "L2 🔶"
    return "L3 🔴"


def _us10y_level(val) -> str:
    if val is None:
        return "L? (N/A)"
    if val <= 4.25:
        return "L0 ✅"
    if val <= 4.60:
        return "L1 ⚠️"
    if val <= 4.85:
        return "L2 🔶"
    return "L3 🔴"


def _pmi_sdt_level(val) -> str:
    if val is None:
        return "L? (N/A)"
    if val <= 1.0:
        return "L0 ✅"
    if val <= 2.0:
        return "L1 ⚠️"
    if val <= 3.0:
        return "L2 🔶"
    return "L3 🔴"


def _latest_ir_keywords(db_path: str, limit: int = 6) -> list[tuple[str, str, int]]:
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """
            SELECT ticker, keyword, mention_count
            FROM ir_keyword_mentions
            WHERE mention_count > 0
            ORDER BY created_at DESC, mention_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def _section_ai_bottleneck(capex_summary: dict, db_path: str) -> str:
    lines = ["*\\[AI 병목\\]*"]
    for key in ["CAPEX_MSFT", "CAPEX_GOOGL", "CAPEX_META", "CAPEX_AMZN"]:
        info = capex_summary.get(key, {})
        if "error" in info:
            lines.append(f"  • {info.get('label', key)}: ⚠️ {info['error']}")
            continue
        latest = info.get("latest")
        qoq = info.get("qoq_pct")
        yoy = info.get("yoy_pct")
        latest_s = f"${latest:.2f}B" if latest is not None else "N/A"
        qoq_s = f"{qoq:+.1f}%" if qoq is not None else "N/A"
        yoy_s = f"{yoy:+.1f}%" if yoy is not None else "N/A"
        lines.append(
            f"  • {info.get('label', key)}: `{latest_s}` QoQ {qoq_s} YoY {yoy_s} → {_capex_level(qoq)}"
        )
    keyword_rows = _latest_ir_keywords(db_path)
    if keyword_rows:
        packed = ", ".join([f"{ticker}:{keyword}({count})" for ticker, keyword, count in keyword_rows])
        lines.append(f"  • IR 병목 키워드: {packed}")
    return "\n".join(lines)


def _section_power_bottleneck(equity_summary: dict) -> str:
    lines = ["*\\[전력 병목\\]*"]
    for key in ["ERCOT_LOAD_MW", "ERCOT_RESERVE_MARGIN", "PJM_LOAD_MW"]:
        info = equity_summary.get(key)
        if info and "error" not in info:
            lines.append(f"  • {info.get('label', key)}: `{_fmt_latest(info)}` {format_change(info.get('change_pct'))}")
    for key in ["XLU", "RS_XLU_SPY", "CAPEX_NEE", "CAPEX_DUK", "CAPEX_SO"]:
        info = equity_summary.get(key)
        if not info or "error" in info:
            continue
        digits = 4 if key.startswith("RS_") else 2
        lines.append(f"  • {info.get('label', key)}: `{_fmt_latest(info, money=key == 'XLU', digits=digits)}`")
    if len(lines) == 1:
        lines.append("  • 데이터 없음")
    return "\n".join(lines)


def _section_capital_flow(equity_summary: dict) -> str:
    lines = ["*\\[자본 흐름\\]*"]
    for key in ["SMH", "SOXX", "QQQ", "SPY", "KOSPI", "KOSDAQ", "RS_SMH_SPY"]:
        info = equity_summary.get(key)
        if not info or "error" in info:
            continue
        digits = 4 if key.startswith("RS_") else 2
        money = key in ("SMH", "SOXX", "QQQ", "SPY")
        lines.append(f"  • {info.get('label', key)}: `{_fmt_latest(info, money=money, digits=digits)}` {format_change(info.get('change_pct'))}")
    if len(lines) == 1:
        lines.append("  • 데이터 없음")
    return "\n".join(lines)


def _section_macro_liquidity(summary: dict) -> str:
    lines = ["*\\[매크로 유동성\\]*"]
    for key in ["US10Y", "DXY", "USD_INDEX", "FED_RATE", "USD_KRW", "WTI", "GOLD", "CPI", "PPI"]:
        info = summary.get(key)
        if not info or "error" in info:
            continue
        lines.append(f"  • {info.get('label', key)}: `{_fmt_latest(info)}` {format_change(info.get('change_pct'))}")
    us10y = summary.get("US10Y", {})
    us10y_val = us10y.get("latest") if "error" not in us10y else None
    pmi = summary.get("PMI_SDT", {})
    pmi_val = pmi.get("latest") if "error" not in pmi else None
    lines.append(f"  • US10Y 레벨: {_us10y_level(us10y_val)}")
    lines.append(f"  • 공급망압력 레벨: {_pmi_sdt_level(pmi_val)}")
    return "\n".join(lines)


def _section_weekly_events(db_path: str) -> str:
    lines = ["*\\[이번주 이벤트\\]*"]
    try:
        events = get_upcoming_events(days_ahead=7, db_path=db_path)
    except Exception:
        events = []
    if not events:
        lines.append("  • 등록된 이벤트 없음")
        return "\n".join(lines)
    for ev in events:
        pieces = []
        for label, key in [("실제", "actual"), ("예상", "forecast"), ("이전", "previous"), ("수정", "revised")]:
            if ev.get(key) is not None:
                pieces.append(f"{label}:{ev[key]}")
        if ev.get("surprise") is not None:
            pieces.append(f"서프라이즈:{ev['surprise']:+.2f}")
        if ev.get("interpretation"):
            pieces.append(ev["interpretation"])
        detail = " / ".join(pieces)
        suffix = f" — {detail}" if detail else ""
        time_s = f" {ev['event_time']}" if ev.get("event_time") else ""
        lines.append(f"  • {ev['event_date']}{time_s} {ev['event_name']} [{ev['country']}]{suffix}")
    return "\n".join(lines)


def build_capex_message(capex_summary: dict) -> str:
    """Hyperscaler CapEx 분기 추이 메시지 (독립 전송용 호환 함수)."""
    return _section_ai_bottleneck(capex_summary, db_path="economic_data.db")


def build_message(summary: dict) -> str:
    """기존 호출부 호환용 매크로 메시지."""
    today = date.today().strftime("%Y년 %m월 %d일")
    return f"*오늘의 경제지표 요약* ({today})\n\n{_section_macro_liquidity(summary)}"


def _send_csv(summary: dict, db_path: str) -> None:
    rows = []
    for key in summary:
        df = get_latest(key, n=5, db_path=db_path)
        if not df.empty:
            df["indicator"] = key
            rows.append(df)
    if rows:
        combined_df = pd.concat(rows)
        csv_buf = io.BytesIO(combined_df.to_csv(index=False).encode("utf-8-sig"))
        _tg_send_document(csv_buf, "daily_indicators.csv", caption="원시 데이터 (CSV)")


def send_report(db_path: str = "economic_data.db", force: bool = False):
    """
    전체 리포트 전송. force=True이면 report_runs 중복 발송 방지를 무시한다.
    """
    if not force and is_report_sent_today(db_path=db_path):
        logger.info("[Telegram] 오늘 이미 리포트 발송 완료 — 중복 방지로 건너뜀")
        return

    logger.info("[Telegram] 리포트 전송 시작")
    summary = build_summary(db_path=db_path)
    equity_summary = build_equity_summary(db_path=db_path)
    equity_summary.update({k: v for k, v in summary.items() if k in ("KOSPI", "KOSDAQ")})

    try:
        capex_summary = build_capex_summary(db_path=db_path)
    except Exception as e:
        logger.error(f"CapEx 요약 생성 실패: {e}")
        capex_summary = {}

    sections = [
        _section_ai_bottleneck(capex_summary, db_path),
        _section_power_bottleneck(equity_summary),
        _section_capital_flow(equity_summary),
        _section_macro_liquidity(summary),
        _section_weekly_events(db_path),
    ]
    today = date.today().strftime("%Y년 %m월 %d일")
    message = f"*TripleA Daily Monitor* ({today})\n\n" + "\n\n".join(sections)
    if len(message) > 4000:
        message = message[:4000] + "\n...(이하 생략)"

    _tg_send_message(message)

    try:
        chart_buf = create_multi_chart(CHART_INDICATORS, db_path=db_path)
        _tg_send_photo(chart_buf, caption="주요 지표 추이 (최근 60일)")
    except Exception as e:
        logger.error(f"차트 생성 실패: {e}")

    if any("error" not in v for v in capex_summary.values()):
        try:
            capex_chart_buf = create_capex_chart(db_path=db_path)
            _tg_send_photo(capex_chart_buf, caption="Hyperscaler CapEx 분기 추이 (5분기)")
        except Exception as e:
            logger.error(f"CapEx 차트 전송 실패: {e}")

    try:
        _send_csv(summary, db_path)
    except Exception as e:
        logger.error(f"CSV 생성 실패: {e}")

    mark_report_sent(message_len=len(message), db_path=db_path)
    logger.info("[Telegram] 리포트 전송 완료")


def send_ir_summaries(filings_with_summaries: list[dict]):
    """신규 IR 파일링 요약을 개별 메시지로 텔레그램 전송."""
    if not filings_with_summaries:
        return

    logger.info(f"[Telegram] IR 요약 {len(filings_with_summaries)}건 전송 시작")
    for f in filings_with_summaries:
        ticker = f.get("ticker", "")
        company = f.get("company", ticker)
        date_str = f.get("date", "")
        form = f.get("form", "8-K")
        summary = f.get("summary", "요약 없음")
        summary_safe = summary.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
        text = (
            f"*{company} ({ticker}) IR 요약*\n"
            f"공시일: {date_str}  \\[{form}\\]\n"
            f"{'-' * 30}\n"
            f"{summary_safe}"
        )
        if len(text) > 4000:
            text = text[:4000] + "\n...(이하 생략)"
        _tg_send_message(text)
        logger.info(f"[Telegram] IR 요약 전송 완료: {ticker} {date_str}")


def send_api_alert(errors: dict[str, str]) -> bool:
    """API 인증/만료 오류를 텔레그램으로 즉시 알림."""
    if not errors:
        return False

    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"*API 인증 오류 감지* ({now})", ""]
    api_labels = {
        "ECOS": "한국은행 ECOS",
        "FRED": "FRED (St. Louis Fed)",
        "FMP": "Financial Modeling Prep",
        "NAVER": "Naver 뉴스 API",
        "KOSIS": "KOSIS 통계청",
    }
    for api_name, detail in errors.items():
        label = api_labels.get(api_name, api_name)
        lines.append(f"*{label}*")
        lines.append(f"   └ {detail}")
        lines.append("")
    lines.append("API 키 만료 여부를 확인하고 `.env` 파일을 업데이트하세요.")
    return _tg_send_message("\n".join(lines))
