import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# config/ lives directly under the project root
CONFIG_DIR   = Path(__file__).resolve().parent        # TripleA/config/
PROJECT_ROOT = CONFIG_DIR.parent                      # TripleA/
INDICATORS_YAML        = CONFIG_DIR / "indicators.yaml"
ECONOMIC_EVENTS_YAML   = CONFIG_DIR / "economic_events.yaml"
INVESTMENT_UNIVERSE_YAML = CONFIG_DIR / "investment_universe.yaml"
STRATEGY_PROFILES_YAML = CONFIG_DIR / "strategy_profiles.yaml"
SECTOR_TAXONOMY_YAML = CONFIG_DIR / "sector_taxonomy.yaml"
ROOT_CONFIG_YAML       = PROJECT_ROOT / "config.yaml"

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

ECOS_KEY           = os.getenv("ECOS_API_KEY")
FRED_KEY           = os.getenv("FRED_API_KEY")
FMP_KEY            = os.getenv("FMP_API_KEY")   # Financial Modeling Prep
GEMINI_KEY         = os.getenv("GEMINI_API_KEY")  # Google Gemini AI
NAVER_ID           = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET       = os.getenv("NAVER_CLIENT_SECRET")
KIPRIS_KEY         = os.getenv("KIPRIS_API_KEY")


def load_pipeline_config(path: str | os.PathLike = ROOT_CONFIG_YAML) -> dict:
    """Load non-secret pipeline settings from config.yaml."""
    config_path = Path(path)
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data
    except Exception as e:
        logger.warning(f"config.yaml 로드 실패: {e}")
        return {}


def validate_config():
    required = {
        "ECOS_API_KEY": ECOS_KEY,
        "FRED_API_KEY": FRED_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"필수 환경변수 누락: {', '.join(missing)}")
