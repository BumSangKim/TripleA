# monitor.py
# 데이터 수집 품질 모니터링 및 텔레그램 경보
import sqlite3
import logging
from datetime import date

from config import TG_TOKEN, get_chat_id
import requests

logger = logging.getLogger(__name__)

DB_PATH = "economic_data.db"
TOTAL_INDICATORS = 15  # summarizer.py INDICATORS 딕셔너리 항목 수


def check_data_quality(db_path: str = DB_PATH) -> dict:
    """
    데이터 품질 지표 산출
    - 완전성: 오늘 수집된 지표 수 / 전체 지표 수
    - 수집 성공률: 오늘 성공 / 전체 시도
    """
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)

    collected = conn.execute(
        "SELECT COUNT(DISTINCT indicator) FROM indicators WHERE date=?", (today,)
    ).fetchone()[0]

    logs = conn.execute(
        "SELECT status, COUNT(*) FROM collect_log WHERE run_date=? GROUP BY status",
        (today,),
    ).fetchall()
    conn.close()

    log_dict = dict(logs)
    success = log_dict.get("success", 0)
    fail    = log_dict.get("fail", 0)
    total   = success + fail

    return {
        "completeness": round(collected / TOTAL_INDICATORS * 100, 1) if TOTAL_INDICATORS else 0,
        "success_rate": round(success / total * 100, 1) if total else 0,
        "fail_count":   fail,
        "collected_count": collected,
    }


def alert_if_fail(db_path: str = DB_PATH):
    """수집 실패 또는 완전성 80% 미만 시 텔레그램 관리자 알림"""
    quality = check_data_quality(db_path)
    if quality["fail_count"] > 0 or quality["completeness"] < 80:
        chat_id = get_chat_id()
        if not chat_id:
            logger.warning(f"품질 경보 발생하였으나 TELEGRAM_CHAT_ID 미설정: {quality}")
            return
        msg = (
            f"⚠️ *데이터 수집 경보*\n"
            f"• 완전성: {quality['completeness']}%\n"
            f"• 수집 성공률: {quality['success_rate']}%\n"
            f"• 실패 건수: {quality['fail_count']}건"
        )
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        try:
            requests.post(
                url,
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"경보 전송 실패: {e}")
        logger.warning(f"품질 경보 발송: {quality}")
    else:
        logger.info(f"품질 정상: {quality}")
