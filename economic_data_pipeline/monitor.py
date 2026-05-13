# monitor.py
# 데이터 수집 품질 모니터링 및 텔레그램 경보
# 완전성 계산: date=today 기준이 아니라 indicator별 stale_days 기준 사용
import sqlite3
import logging
from datetime import date, timedelta
from pathlib import Path

import yaml

from config import TG_TOKEN, get_chat_id
import requests

logger = logging.getLogger(__name__)

DB_PATH = "economic_data.db"

# ── indicators.yaml 로드 ─────────────────────────────────────────────────────
_YAML_PATH = Path(__file__).parent / "config" / "indicators.yaml"

def _load_indicator_meta() -> dict:
    """config/indicators.yaml에서 stale_days 설정 로드"""
    try:
        with open(_YAML_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("indicators", {})
    except Exception as e:
        logger.warning(f"[monitor] indicators.yaml 로드 실패: {e} — 기본값 사용")
        return {}


# 기본 stale_days 매핑 (yaml 로드 실패 시 fallback)
_DEFAULT_STALE_DAYS: dict[str, int] = {
    "daily":     3,
    "weekly":    10,
    "monthly":   40,
    "quarterly": 100,
}


def get_stale_days(indicator: str, meta: dict) -> int:
    """지표별 stale_days 반환. YAML 정의 우선, 없으면 frequency → 기본값."""
    ind_meta = meta.get(indicator, {})
    if "stale_days" in ind_meta:
        return int(ind_meta["stale_days"])
    freq = ind_meta.get("frequency", "daily")
    return _DEFAULT_STALE_DAYS.get(freq, 3)


def check_data_quality(db_path: str = DB_PATH) -> dict:
    """
    데이터 품질 지표 산출 (P0 fix: stale_days 기준)
    - 완전성: indicator별 stale_days 이내에 데이터가 있으면 fresh로 간주
    - 수집 성공률: 오늘 수집 로그 기준
    """
    meta = _load_indicator_meta()
    today = date.today()
    conn = sqlite3.connect(db_path)

    # 추적할 지표 목록: CapEx·파생 제외한 핵심 경제지표
    tracked = [k for k, v in meta.items()
               if v.get("layer") not in ("ai_bottleneck",) and not k.startswith("CAPEX_")]
    if not tracked:
        # YAML 로드 실패 fallback
        tracked = conn.execute(
            "SELECT DISTINCT indicator FROM indicators"
        ).fetchall()
        tracked = [r[0] for r in tracked]

    fresh_count = 0
    stale_indicators = []
    for indicator in tracked:
        stale_days = get_stale_days(indicator, meta)
        cutoff = (today - timedelta(days=stale_days)).isoformat()
        # collected_at 우선 체크: FRED 월별 지표는 date가 관측기간 1일(예: 2026-04-01)이라
        # stale_days를 초과할 수 있음. 실제로 최근 수집했으면 fresh로 간주.
        row = conn.execute(
            """SELECT MAX(COALESCE(date(collected_at), date))
               FROM indicators
               WHERE indicator=?
                 AND COALESCE(date(collected_at), date) >= ?""",
            (indicator, cutoff),
        ).fetchone()
        if row and row[0]:
            fresh_count += 1
        else:
            stale_indicators.append(indicator)

    total_tracked = len(tracked)

    # 오늘 수집 로그
    today_str = today.isoformat()
    logs = conn.execute(
        "SELECT status, COUNT(*) FROM collect_log WHERE run_date=? GROUP BY status",
        (today_str,),
    ).fetchall()
    conn.close()

    log_dict = dict(logs)
    success = log_dict.get("success", 0)
    fail    = log_dict.get("fail", 0)
    total   = success + fail

    return {
        "completeness":    round(fresh_count / total_tracked * 100, 1) if total_tracked else 0,
        "fresh_count":     fresh_count,
        "total_tracked":   total_tracked,
        "stale_indicators": stale_indicators,
        "success_rate":    round(success / total * 100, 1) if total else 0,
        "fail_count":      fail,
    }


def alert_if_fail(db_path: str = DB_PATH):
    """수집 실패 또는 완전성 80% 미만 시 텔레그램 관리자 알림"""
    quality = check_data_quality(db_path)
    if quality["fail_count"] > 0 or quality["completeness"] < 80:
        chat_id = get_chat_id()
        if not chat_id:
            logger.warning(f"품질 경보 발생하였으나 TELEGRAM_CHAT_ID 미설정: {quality}")
            return
        stale_list = ", ".join(quality["stale_indicators"][:5]) or "없음"
        msg = (
            f"⚠️ *데이터 수집 경보*\n"
            f"• 완전성: {quality['completeness']}% ({quality['fresh_count']}/{quality['total_tracked']})\n"
            f"• 수집 성공률: {quality['success_rate']}%\n"
            f"• 실패 건수: {quality['fail_count']}건\n"
            f"• stale 지표: {stale_list}"
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
        logger.info(f"품질 정상: 완전성={quality['completeness']}% ({quality['fresh_count']}/{quality['total_tracked']})")

