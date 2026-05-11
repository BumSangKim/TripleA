# telegram_sender.py
# 텔레그램 봇을 통해 경제지표 요약 및 차트 전송
import logging
import io

import pandas as pd
import requests

from config import TG_TOKEN, get_chat_id
from summarizer import build_summary
from chart_generator import create_multi_chart
from database import get_latest

logger = logging.getLogger(__name__)

# 차트에 포함할 지표 목록
CHART_INDICATORS = [
    ("KOSPI",    "코스피"),
    ("USD_KRW",  "원/달러 환율"),
    ("CPI",      "소비자물가(CPI)"),
    ("DUBAI_OIL","두바이유"),
    ("WTI",      "WTI 국제유가"),
    ("GOLD",     "금 가격"),
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


def build_message(summary: dict) -> str:
    from datetime import date
    today = date.today().strftime("%Y년 %m월 %d일")
    lines = [f"📊 *오늘의 경제지표 요약* ({today})\n"]
    for key, info in summary.items():
        if "error" in info:
            lines.append(f"• {info['label']}: ⚠️ {info['error']}")
        else:
            latest = (
                f"{info['latest']:,.2f} {info['unit']}" if info.get("latest") is not None else "N/A"
            )
            change = format_change(info.get("change_pct"))
            lines.append(f"• {info['label']}: `{latest}` {change}")
    return "\n".join(lines)


def send_report(db_path: str = "economic_data.db"):
    """전체 리포트 전송: 텍스트 요약 + 차트 + CSV"""
    summary = build_summary(db_path=db_path)

    # 1. 요약 텍스트 전송
    message = build_message(summary)
    _tg_send_message(message)

    # 2. 차트 이미지 전송
    try:
        chart_buf = create_multi_chart(CHART_INDICATORS, db_path=db_path)
        _tg_send_photo(chart_buf, caption="📈 주요 지표 추이 (최근 60일)")
    except Exception as e:
        logger.error(f"차트 생성 실패: {e}")

    # 3. CSV 로우데이터 전송
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
