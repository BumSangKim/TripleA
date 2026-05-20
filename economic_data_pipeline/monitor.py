# monitor.py
# 데이터 수집 품질 모니터링 및 텔레그램 경보
# 완전성 계산: date=today 기준이 아니라 indicator별 stale_days 기준 사용
import sqlite3
import logging
import calendar
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


def _tracked_indicators(conn: sqlite3.Connection, meta: dict) -> list[str]:
    """관측 최신성을 볼 지표 목록."""
    tracked = [
        k for k, v in meta.items()
        if v.get("layer") not in ("ai_bottleneck",) and not k.startswith("CAPEX_")
    ]
    if tracked:
        return tracked
    rows = conn.execute("SELECT DISTINCT indicator FROM indicators").fetchall()
    return [r[0] for r in rows]


def _period_end(date_str: str, frequency: str) -> str:
    """월간/분기 관측치가 기간 첫날로 들어와도 기간 말일 기준으로 stale 판정."""
    if not date_str:
        return date_str
    try:
        d = date.fromisoformat(date_str[:10])
    except ValueError:
        return date_str
    if frequency == "monthly":
        last_day = calendar.monthrange(d.year, d.month)[1]
        return d.replace(day=last_day).isoformat()
    if frequency == "quarterly":
        quarter_end_month = ((d.month - 1) // 3 + 1) * 3
        last_day = calendar.monthrange(d.year, quarter_end_month)[1]
        return d.replace(month=quarter_end_month, day=last_day).isoformat()
    return d.isoformat()


def observation_quality(db_path: str = DB_PATH) -> dict:
    """
    지표 관측 최신성 산출.
    observed_date가 있으면 우선 사용하고, 없으면 date를 사용한다. collected_at은
    수집 시점이라 월간/분기 관측치의 최신성 판단에는 쓰지 않는다.
    """
    meta = _load_indicator_meta()
    today = date.today()
    conn = sqlite3.connect(db_path)

    tracked = _tracked_indicators(conn, meta)
    fresh_count = 0
    stale_indicators = []
    for indicator in tracked:
        stale_days = get_stale_days(indicator, meta)
        frequency = meta.get(indicator, {}).get("frequency", "daily")
        cutoff = (today - timedelta(days=stale_days)).isoformat()
        row = conn.execute(
            """SELECT MAX(COALESCE(date(observed_date), date))
               FROM indicators
               WHERE indicator=?
                 AND COALESCE(is_stale, 0)=0""",
            (indicator,),
        ).fetchone()
        latest_period_end = _period_end(row[0], frequency) if row and row[0] else None
        if latest_period_end and latest_period_end >= cutoff:
            fresh_count += 1
        else:
            stale_indicators.append(indicator)

    total_tracked = len(tracked)
    conn.close()

    return {
        "completeness":     round(fresh_count / total_tracked * 100, 1) if total_tracked else 0,
        "fresh_count":      fresh_count,
        "total_tracked":    total_tracked,
        "stale_indicators": stale_indicators,
    }


def collection_quality(db_path: str = DB_PATH) -> dict:
    """
    오늘 수집 실행 성공률 산출.
    collector_runs가 있으면 source 단위 실행 결과를 우선 사용하고, 없으면 기존
    collect_log를 fallback으로 사용한다.
    """
    today = date.today()
    conn = sqlite3.connect(db_path)
    today_str = today.isoformat()

    runs = conn.execute(
        """
        SELECT cr.status, COUNT(*)
        FROM collector_runs cr
        JOIN (
            SELECT collector, MAX(run_at) AS latest_run_at
            FROM collector_runs
            WHERE date(run_at)=?
            GROUP BY collector
        ) latest
          ON latest.collector = cr.collector
         AND latest.latest_run_at = cr.run_at
        GROUP BY cr.status
        """,
        (today_str,),
    ).fetchall()
    if runs:
        conn.close()
        counts = {status: count for status, count in runs}
        success = counts.get("success", 0) + counts.get("ok", 0)
        fail = counts.get("fail", 0) + counts.get("error", 0)
        partial = counts.get("partial", 0)
        total = success + fail + partial
        return {
            "success_rate": round(success / total * 100, 1) if total else 0,
            "success_count": success,
            "fail_count": fail + partial,
            "partial_count": partial,
            "total_runs": total,
            "source": "collector_runs",
        }

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
        "success_rate":    round(success / total * 100, 1) if total else 0,
        "success_count":   success,
        "fail_count":      fail,
        "partial_count":   0,
        "total_runs":      total,
        "source":          "collect_log",
    }


def check_data_quality(db_path: str = DB_PATH) -> dict:
    """수집 성공률과 관측 최신성을 합친 하위 호환 품질 지표."""
    quality = observation_quality(db_path=db_path)
    quality.update(collection_quality(db_path=db_path))
    return quality


def alert_if_fail(db_path: str = DB_PATH):
    """수집 실패 또는 완전성 80% 미만 시 텔레그램 관리자 알림"""
    quality = check_data_quality(db_path)
    if quality["fail_count"] > 0 or quality["completeness"] < 80:
        chat_id = get_chat_id()
        if not chat_id:
            logger.warning(f"품질 경보 발생하였으나 TELEGRAM_CHAT_ID 미설정: {quality}")
            return
        def _md_escape(text: str) -> str:
            return str(text).replace("_", "\\_")

        stale_list = ", ".join(_md_escape(x) for x in quality["stale_indicators"][:5]) or "없음"
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
