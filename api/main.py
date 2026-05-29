"""
api/main.py
FastAPI 대시보드 API 서버
실행: cd /Users/bumsangkim/Dev/TripleA && uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

from .core.app import create_app

app = create_app()
