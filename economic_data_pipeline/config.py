# config.py
# 환경변수에서 API 키 로드 - .env 파일 또는 시스템 환경변수 사용
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

ECOS_KEY           = os.getenv("ECOS_API_KEY")
FRED_KEY           = os.getenv("FRED_API_KEY")
FMP_KEY            = os.getenv("FMP_API_KEY")   # Financial Modeling Prep
GEMINI_KEY         = os.getenv("GEMINI_API_KEY")  # Google Gemini AI
NAVER_ID           = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET       = os.getenv("NAVER_CLIENT_SECRET")
KIPRIS_KEY         = os.getenv("KIPRIS_API_KEY")
TG_TOKEN           = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID         = os.getenv("TELEGRAM_CHAT_ID")
KIS_APP_KEY        = os.getenv("KIS_APP_KEY")    # 한국투자증권 앱 키
KIS_APP_SECRET     = os.getenv("KIS_APP_SECRET")  # 한국투자증권 시크릿
KIS_ISDEMO         = os.getenv("KIS_ISDEMO", "false").lower() == "true"  # 모의투자 여부


def discover_chat_id() -> str | None:
    """
    TELEGRAM_CHAT_ID 미설정 시 getUpdates로 첫 번째 chat_id를 자동 발견
    사용자가 봇(@bum_triple_a_bot)에 /start 메시지를 보낸 후 동작함
    """
    if not TG_TOKEN:
        return None
    try:
        import requests
        r = requests.get(
            f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
            params={"limit": 10, "offset": -10},
            timeout=10,
        )
        updates = r.json().get("result", [])
        for u in updates:
            msg = u.get("message", u.get("channel_post", {}))
            chat_id = msg.get("chat", {}).get("id")
            if chat_id:
                logger.info(f"[Telegram] chat_id 자동 발견: {chat_id}")
                return str(chat_id)
    except Exception as e:
        logger.warning(f"[Telegram] chat_id 발견 실패: {e}")
    return None


def get_chat_id() -> str | None:
    """TELEGRAM_CHAT_ID 반환 - 우선순위: 환경변수 > .env > getUpdates 자동발견"""
    # 1. 실행 중 환경변수 (run.sh에서 export한 경우 포함)
    live = os.environ.get("TELEGRAM_CHAT_ID", "")
    if live and live not in ("YOUR_TELEGRAM_CHAT_ID", "TEST", ""):
        return live

    # 2. .env 재로드 후 확인
    load_dotenv(override=True)
    from_env = os.environ.get("TELEGRAM_CHAT_ID", "")
    if from_env and from_env not in ("YOUR_TELEGRAM_CHAT_ID", "TEST", ""):
        return from_env

    # 3. getUpdates로 자동 발견
    discovered = discover_chat_id()
    if discovered:
        os.environ["TELEGRAM_CHAT_ID"] = discovered
        return discovered
    return None


def validate_config():
    required = {
        "ECOS_API_KEY": ECOS_KEY,
        "FRED_API_KEY": FRED_KEY,
        "TELEGRAM_BOT_TOKEN": TG_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"필수 환경변수 누락: {', '.join(missing)}")

    # Telegram Chat ID 경고
    chat_id = get_chat_id()
    if not chat_id:
        logger.warning(
            "TELEGRAM_CHAT_ID 미설정. "
            "텔레그램에서 @bum_triple_a_bot 에 /start 메시지를 보내면 자동 설정됩니다."
        )

