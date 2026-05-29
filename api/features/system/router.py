from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.brokers.kis.errors import KISAPIError, KISConfigError, KISNetworkError
from api.features.system.dependencies import get_system_service
from api.features.system.schemas import (
    HealthResponse,
    ModeInfo,
    ProviderSyncResult,
    SystemStatusResponse,
)
from api.features.system.service import SystemService
from api.providers.modes import TradingMode, normalize_mode

router = APIRouter(tags=["system"])


def _parse_mode(mode: str) -> TradingMode:
    try:
        return normalize_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _provider_error_detail(code: str, message: str, user_action: str) -> dict:
    return {"code": code, "message": message, "userAction": user_action}


@router.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", timestamp=datetime.now().isoformat())


@router.get("/api/modes", response_model=List[ModeInfo])
def list_modes(service: SystemService = Depends(get_system_service)):
    return service.list_modes()


@router.get("/api/modes/{mode}", response_model=ModeInfo)
def get_mode(mode: str, service: SystemService = Depends(get_system_service)):
    return service.get_mode_info(_parse_mode(mode))


@router.post("/api/providers/{mode}/sync-accounts", response_model=ProviderSyncResult)
def sync_provider_accounts(mode: str, service: SystemService = Depends(get_system_service)):
    import logging
    logger = logging.getLogger("uvicorn.error")
    try:
        return service.sync_accounts(_parse_mode(mode))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except KISConfigError as e:
        logger.info("KIS provider sync config error: %s", e)
        raise HTTPException(
            status_code=503,
            detail=_provider_error_detail(
                "KIS_CONFIG_MISSING",
                "KIS 계좌 동기화 설정이 누락되었습니다.",
                ".env의 KIS 앱키, 시크릿, 계좌번호 설정을 확인하세요.",
            ),
        ) from e
    except KISNetworkError as e:
        logger.warning("KIS provider sync network error: %s", e)
        raise HTTPException(
            status_code=504,
            detail=_provider_error_detail(
                "KIS_NETWORK_ERROR",
                "KIS 서버와 통신하지 못했습니다.",
                "네트워크 상태와 KIS 모의투자 서버 접속 가능 여부를 확인한 뒤 다시 시도하세요.",
            ),
        ) from e
    except KISAPIError as e:
        logger.warning("KIS provider sync API error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=_provider_error_detail(
                "KIS_API_ERROR",
                "KIS API 응답을 처리하지 못했습니다.",
                "KIS OpenAPI 신청 상태, 모의투자 계좌 상태, TR 권한을 확인하세요.",
            ),
        ) from e


@router.get("/api/system/status", response_model=SystemStatusResponse)
def system_status(service: SystemService = Depends(get_system_service)):
    data = service.get_status()
    return SystemStatusResponse(
        macro_last_update=data.macro_last_update,
        holdings_last_update=data.holdings_last_update,
        total_indicators=data.total_indicators,
        recent_7d_rows=data.recent_7d_rows,
        success_rate=data.success_rate,
        unread_alerts=data.unread_alerts,
        pipeline_status=data.pipeline_status,
        timestamp=data.timestamp,
    )


_API_KEY_DIR = Path(__file__).resolve().parent.parent.parent.parent / "API_KEY"

_API_KEY_CONFIGS = [
    {"label": "FRED API",       "env": "FRED_API_KEY"},
    {"label": "ECOS API (BOK)", "env": "ECOS_API_KEY"},
    {"label": "KOSIS API",      "env": "KOSIS_API_KEY"},
    {"label": "Telegram Bot",   "env": "TELEGRAM_KEY"},
    {"label": "Naver API",      "env": "NAVER_API_KEY"},
    {"label": "KIS 증권사 API", "env": "KIS_API_KEY"},
    {"label": "FMP API",        "env": "FMP_API_KEY"},
]


@router.get("/api/settings/api-keys", tags=["settings"])
def get_api_keys_status():
    result = []
    for k in _API_KEY_CONFIGS:
        file_path = _API_KEY_DIR / k["env"]
        try:
            is_set = file_path.exists() and bool(file_path.read_text(encoding="utf-8").strip())
        except OSError:
            is_set = False
        result.append({"label": k["label"], "env": k["env"], "status": is_set})
    return result
