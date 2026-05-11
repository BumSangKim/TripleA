# config.py
# 환경변수에서 API 키 로드 - .env 파일 또는 시스템 환경변수 사용
from dotenv import load_dotenv
import os

load_dotenv()

ECOS_KEY           = os.getenv("ECOS_API_KEY")
FRED_KEY           = os.getenv("FRED_API_KEY")
NAVER_ID           = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET       = os.getenv("NAVER_CLIENT_SECRET")
KIPRIS_KEY         = os.getenv("KIPRIS_API_KEY")
TG_TOKEN           = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID         = os.getenv("TELEGRAM_CHAT_ID")

# 필수 키 검증
def validate_config():
    required = {
        "ECOS_API_KEY": ECOS_KEY,
        "FRED_API_KEY": FRED_KEY,
        "TELEGRAM_BOT_TOKEN": TG_TOKEN,
        "TELEGRAM_CHAT_ID": TG_CHAT_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"필수 환경변수 누락: {', '.join(missing)}")
