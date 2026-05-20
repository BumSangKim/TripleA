# scheduler.py
# APScheduler 기반 자동 실행 스케줄러
# 실행: python -m backend.scheduler
import logging
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from config import validate_config
from storage.database import init_db, DB_PATH as _DEFAULT_DB
from backend.main import collect_all_indicators, DB_PATH
from backend.summarizer import build_summary
from backend.chart_generator import create_multi_chart
from backend.telegram_sender import send_report, send_valuation_report, CHART_INDICATORS
from backend.monitor import alert_if_fail

logging.basicConfig(
    handlers=[
        logging.FileHandler(str(Path(__file__).resolve().parents[1] / "data" / "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = BlockingScheduler(timezone="Asia/Seoul")


def job_collect():
    """08:00 - 데이터 수집 및 DB 저장"""
    logger.info("===== [08:00] 데이터 수집 시작 =====")
    try:
        collect_all_indicators()
        logger.info("===== 데이터 수집 완료 =====")
    except Exception as e:
        logger.error(f"수집 작업 오류: {e}", exc_info=True)


def job_summarize():
    """08:20 - 요약 지표 산출 및 차트 생성 (사전 검증)"""
    logger.info("===== [08:20] 요약 연산 시작 =====")
    try:
        summary = build_summary(db_path=DB_PATH)
        logger.info(f"요약 완료: {len(summary)}개 지표")
        chart_buf = create_multi_chart(CHART_INDICATORS, db_path=DB_PATH)
        logger.info("차트 생성 완료")
    except Exception as e:
        logger.error(f"요약 작업 오류: {e}", exc_info=True)


def job_send():
    """08:30 - 텔레그램 전송"""
    logger.info("===== [08:30] 텔레그램 전송 시작 =====")
    try:
        send_report(db_path=DB_PATH)
        alert_if_fail(db_path=DB_PATH)
        logger.info("===== 전송 완료 =====")
    except Exception as e:
        logger.error(f"전송 작업 오류: {e}", exc_info=True)


def on_job_error(event):
    logger.error(f"스케줄 작업 오류 발생: {event.job_id} - {event.exception}")


# 스케줄 등록
scheduler.add_job(job_collect,   "cron", hour=8,  minute=0,  id="collect",   misfire_grace_time=300)
scheduler.add_job(job_summarize, "cron", hour=8,  minute=20, id="summarize", misfire_grace_time=300)
scheduler.add_job(job_send,      "cron", hour=8,  minute=30, id="send",      misfire_grace_time=300)


def job_valuation():
    """월요일 09:00 — 밸류에이션 스크리닝"""
    logger.info("===== [월 09:00] 밸류에이션 스크리닝 시작 =====")
    try:
        from backend.valuation_pipeline import run_valuation_pipeline
        results = run_valuation_pipeline(db_path=DB_PATH)
        send_valuation_report(results, db_path=DB_PATH)
        logger.info("===== 밸류에이션 스크리닝 완료 =====")
    except Exception as e:
        logger.error(f"밸류에이션 작업 오류: {e}", exc_info=True)


scheduler.add_job(job_valuation, "cron", day_of_week="mon", hour=9, minute=0, id="valuation", misfire_grace_time=600)

scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)


if __name__ == "__main__":
    validate_config()
    init_db(DB_PATH)
    logger.info("스케줄러 시작 (Asia/Seoul 기준)")
    logger.info("  - 08:00 데이터 수집")
    logger.info("  - 08:20 요약 연산")
    logger.info("  - 08:30 텔레그램 전송")
    logger.info("  - 월 09:00 밸류에이션 스크리닝")
    scheduler.start()
