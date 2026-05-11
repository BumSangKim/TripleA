# telegram_sender.py
# 텔레그램 봇을 통해 경제지표 요약 및 차트 전송
import logging
import io

import pandas as pd
import requests

from config import TG_TOKEN, get_chat_id
from summarizer import build_summary, build_capex_summary
from chart_generator import create_multi_chart, create_capex_chart
from database import get_latest

logger = logging.getLogger(__name__)

# 차트에 포함할 지표 목록
CHART_INDICATORS = [
    ("KOSPI",    "코스피"),
    ("USD_KRW",  "원/달러 환율"),
    ("CPI",      "소비자물가(CPI)"),
    ("DUBAI_OIL","두바이유"),
    ("WTI",      "WTI 국제유가"),
    ("PMI_SDT",  "공급망압력(GSCPI·PMI)"),
]


def _tg_send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """텔레그램 메시지 전송 (requests 직접 사용 - 동기 방식)"""
    chat_id = get_chat_id()
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID 없음 - 텔레그램 전송 건너뜀")
        logger.info(f"[미전송 메시지 미리보기]\n{text[:300]}")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
        logger.info(f"[Telegram] 메시지 전송 완료 (chat_id={chat_id})")
        return True
    except Exception as e:
        logger.error(f"텍스트 전송 실패: {e}")
        return False


def _tg_send_photo(photo_buf: io.BytesIO, caption: str = "") -> bool:
    """텔레그램 사진 전송"""
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
        logger.info(f"[Telegram] 차트 전송 완료")
        return True
    except Exception as e:
        logger.error(f"차트 전송 실패: {e}")
        return False


def _tg_send_document(doc_buf: io.BytesIO, filename: str, caption: str = "") -> bool:
    """텔레그램 문서(파일) 전송"""
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


def _capex_level(qoq_pct) -> str:
    """CapEx QoQ 변화율 → Deep Research S1 Level"""
    if qoq_pct is None:
        return "L? (N/A)"
    if qoq_pct >= 0:
        return "L0 ✅"
    elif qoq_pct >= -5:
        return "L1 ⚠️"
    elif qoq_pct >= -15:
        return "L2 🔶"
    else:
        return "L3 🔴"


def build_capex_message(capex_summary: dict) -> str:
    """Hyperscaler CapEx 분기 추이 메시지"""
    from datetime import date
    today = date.today().strftime("%Y년 %m월 %d일")
    lines = [f"🏗️ *Hyperscaler AI CapEx 분기 추이* ({today})\n"]
    lines.append("_(Deep Research S1 신호 — 5분기 추이, 단위: 십억달러(B))_\n")

    for key in ["CAPEX_MSFT", "CAPEX_GOOGL", "CAPEX_META", "CAPEX_AMZN"]:
        info = capex_summary.get(key, {})
        if "error" in info:
            lines.append(f"• {info['label']}: ⚠️ {info['error']}")
            continue
        label = info["label"]
        latest = info.get("latest")
        latest_date = info.get("latest_date", "?")
        qoq = info.get("qoq_pct")
        yoy = info.get("yoy_pct")
        quarters = info.get("quarters", [])

        qoq_str = f"{qoq:+.1f}%" if qoq is not None else "N/A"
        yoy_str = f"{yoy:+.1f}%" if yoy is not None else "N/A"
        lv = _capex_level(qoq)

        lines.append(f"*{label}* → {lv}")
        lines.append(f"  최신({latest_date}): `${latest:.2f}B`  QoQ:{qoq_str}  YoY:{yoy_str}")
        if quarters:
            trend = "  추이: " + " → ".join([f"${q['capex_b']:.1f}B" for q in reversed(quarters)])
            lines.append(trend)
        lines.append("")

    return "\n".join(lines)


def _us10y_level(val) -> str:
    """Deep Research 매크로 패널: US 10Y 금리 → Level 0-3"""
    if val is None:
        return "L? (N/A)"
    if val <= 4.25:
        return "L0 ✅"
    elif val <= 4.60:
        return "L1 ⚠️"
    elif val <= 4.85:
        return "L2 🔶"
    else:
        return "L3 🔴"


def _pmi_sdt_level(val) -> str:
    """공급망 압력지수(GSCPI·PMI) → Level 평가 (표준편차 기준)"""
    if val is None:
        return "L? (N/A)"
    if val <= 1.0:
        return "L0 ✅"
    elif val <= 2.0:
        return "L1 ⚠️"
    elif val <= 3.0:
        return "L2 🔶"
    else:
        return "L3 🔴"


def build_message(summary: dict) -> str:
    from datetime import date
    today = date.today().strftime("%Y년 %m월 %d일")
    lines = [f"📊 *오늘의 경제지표 요약* ({today})\n"]

    # ── 한국 지표 ──────────────────────────────────────────
    kr_keys = ["KOSPI", "KOSDAQ", "USD_KRW", "BASE_RATE", "BOND_3Y",
               "CPI", "PPI", "UNEMPLOYMENT", "GDP_GROWTH"]
    lines.append("🇰🇷 *한국 지표*")
    for key in kr_keys:
        info = summary.get(key)
        if not info:
            continue
        if "error" in info:
            lines.append(f"  • {info['label']}: ⚠️ {info['error']}")
        else:
            latest = f"{info['latest']:,.2f} {info['unit']}" if info.get("latest") is not None else "N/A"
            change = format_change(info.get("change_pct"))
            lines.append(f"  • {info['label']}: `{latest}` {change}")

    # ── 국제 원자재 ────────────────────────────────────────
    lines.append("\n🛢️ *국제 원자재*")
    for key in ["DUBAI_OIL", "WTI", "GOLD"]:
        info = summary.get(key)
        if not info:
            continue
        if "error" in info:
            lines.append(f"  • {info['label']}: ⚠️ {info['error']}")
        else:
            latest = f"{info['latest']:,.2f} {info['unit']}" if info.get("latest") is not None else "N/A"
            change = format_change(info.get("change_pct"))
            lines.append(f"  • {info['label']}: `{latest}` {change}")

    # ── 미국 지표 ──────────────────────────────────────────
    lines.append("\n🇺🇸 *미국 지표*")
    for key in ["US_CPI", "FED_RATE", "US10Y", "DXY", "USD_INDEX"]:
        info = summary.get(key)
        if not info:
            continue
        if "error" in info:
            lines.append(f"  • {info['label']}: ⚠️ {info['error']}")
        else:
            latest = f"{info['latest']:,.2f} {info['unit']}" if info.get("latest") is not None else "N/A"
            change = format_change(info.get("change_pct"))
            lines.append(f"  • {info['label']}: `{latest}` {change}")

    # ── 공급망 ─────────────────────────────────────────────
    pmi_info = summary.get("PMI_SDT")
    lines.append("\n🔗 *공급망 압력 (GSCPI · PMI Supplier Delivery Times 기반)*")
    if pmi_info and "error" not in pmi_info:
        pmi_val = pmi_info.get("latest")
        pmi_level = _pmi_sdt_level(pmi_val)
        latest_str = f"{pmi_val:+.4f}σ" if pmi_val is not None else "N/A"
        change = format_change(pmi_info.get("change_pct"))
        lines.append(f"  • 공급망압력지수: `{latest_str}` {change} → {pmi_level}")
        lines.append("  _(값 > 0: 평균 대비 압력 높음, 양수일수록 공급 병목 심화)_")
    else:
        lines.append("  • 공급망압력지수: ⚠️ 데이터 없음")

    # ── Deep Research 08:30 모니터링 신호 ─────────────────
    lines.append("\n📡 *08:30 모니터링 신호 (Deep Research 프레임워크)*")

    # 매크로 자동 레벨 판정
    us10y_info = summary.get("US10Y")
    us10y_val = us10y_info.get("latest") if us10y_info and "error" not in us10y_info else None
    us10y_lv = _us10y_level(us10y_val)
    us10y_str = f"{us10y_val:.2f}%" if us10y_val else "N/A"

    dxy_info = summary.get("DXY")
    dxy_val = dxy_info.get("latest") if dxy_info and "error" not in dxy_info else None
    dxy_str = f"{dxy_val:.2f}" if dxy_val else "N/A"

    usd_info = summary.get("USD_INDEX")
    usd_val = usd_info.get("latest") if usd_info and "error" not in usd_info else None
    usd_str = f"{usd_val:.1f}" if usd_val else "N/A"

    pmi_lv = _pmi_sdt_level(pmi_info.get("latest") if pmi_info and "error" not in pmi_info else None)
    pmi_str = f"{pmi_info.get('latest'):+.2f}σ" if pmi_info and "error" not in pmi_info and pmi_info.get("latest") is not None else "N/A"

    lines.append(f"  🔹 *매크로 패널*")
    lines.append(f"    • US 10Y: `{us10y_str}` → {us10y_lv}")
    lines.append(f"    • DXY(ICE): `{dxy_str}` / 무역가중지수(DTWEXBGS): `{usd_str}`")
    lines.append(f"  🔹 *공급망 신호 (S4)*")
    lines.append(f"    • GSCPI·PMI SDT: `{pmi_str}` → {pmi_lv}")
    lines.append(f"  🔹 *수동 확인 필요 신호*")
    lines.append(f"    • S1 Hyperscaler CapEx: 별도 메시지 참조 ↓")
    lines.append(f"    • S2 NVIDIA GPU 수요: DC Revenue / 가이던스 확인")
    lines.append(f"    • S3 HBM 수급/가격: TrendForce/SK하이닉스/Micron 확인")
    lines.append(f"    • S5 AI 수익화: MSFT/GOOGL/PLTR 런레이트 확인")

    return "\n".join(lines)


def send_report(db_path: str = "economic_data.db"):
    """전체 리포트 전송: 텍스트 요약 + 차트 + CapEx 리포트 + CSV"""
    logger.info("[Telegram] 리포트 전송 시작")
    summary = build_summary(db_path=db_path)

    # 1. 요약 텍스트 전송
    message = build_message(summary)
    _tg_send_message(message)

    # 2. 주요 지표 차트 전송
    try:
        chart_buf = create_multi_chart(CHART_INDICATORS, db_path=db_path)
        _tg_send_photo(chart_buf, caption="📈 주요 지표 추이 (최근 60일)")
    except Exception as e:
        logger.error(f"차트 생성 실패: {e}")

    # 3. Hyperscaler CapEx 리포트 전송 (S1 신호)
    try:
        capex_summary = build_capex_summary(db_path=db_path)
        has_data = any("error" not in v for v in capex_summary.values())
        if has_data:
            capex_msg = build_capex_message(capex_summary)
            _tg_send_message(capex_msg)
            # CapEx 분기 추이 차트 전송
            capex_chart_buf = create_capex_chart(db_path=db_path)
            _tg_send_photo(capex_chart_buf, caption="🏗️ Hyperscaler CapEx 분기 추이 (5분기)")
        else:
            logger.info("[Telegram] CapEx 데이터 없음 - 건너뜀")
    except Exception as e:
        logger.error(f"CapEx 리포트 전송 실패: {e}")

    # 4. CSV 로우데이터 전송
    try:
        rows = []
        for key in summary:
            df = get_latest(key, n=5, db_path=db_path)
            if not df.empty:
                df["indicator"] = key
                rows.append(df)
        if rows:
            combined = pd.concat(rows)
            csv_buf = io.BytesIO(combined.to_csv(index=False).encode("utf-8-sig"))
            _tg_send_document(csv_buf, "daily_indicators.csv", caption="📋 원시 데이터 (CSV)")
    except Exception as e:
        logger.error(f"CSV 생성 실패: {e}")
