from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.features.system.dependencies import get_system_service
from api.features.system.schemas import (
    HealthResponse,
    ModeInfo,
    SystemStatusResponse,
)
from api.features.system.service import SystemService

router = APIRouter(tags=["system"])


def _parse_mode(mode: str) -> str:
    normalized = (mode or "local").strip().lower()
    if normalized not in {"local", "backtest"}:
        raise HTTPException(status_code=422, detail="Allowed simplified modes: local, backtest")
    return normalized


@router.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", timestamp=datetime.now().isoformat())


@router.get("/api/modes", response_model=List[ModeInfo])
def list_modes(service: SystemService = Depends(get_system_service)):
    return service.list_modes()


@router.get("/api/modes/{mode}", response_model=ModeInfo)
def get_mode(mode: str, service: SystemService = Depends(get_system_service)):
    return service.get_mode_info(_parse_mode(mode))


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
    {"label": "Naver API",      "env": "NAVER_API_KEY"},
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
