#!/bin/bash
# scripts/start_dashboard.sh
# TripleA 대시보드 서버 시작 스크립트 (FastAPI + Next.js)

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT_ROOT/.venv"

echo "=== TripleA Dashboard 시작 ==="
echo "프로젝트 루트: $PROJECT_ROOT"

# 가상환경 활성화
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    echo "✓ Python 가상환경 활성화"
else
    echo "❌ 가상환경을 찾을 수 없습니다. python -m venv .venv 를 실행하세요."
    exit 1
fi

# FastAPI 백엔드 시작 (백그라운드)
echo ""
echo "▶ FastAPI 서버 시작 (포트 8000)..."
cd "$PROJECT_ROOT"
uvicorn api.main:app --reload --port 8000 --host 0.0.0.0 &
FASTAPI_PID=$!
echo "  PID: $FASTAPI_PID"

# Next.js 프론트엔드 시작
echo ""
echo "▶ Next.js 개발 서버 시작 (포트 3000)..."
cd "$PROJECT_ROOT/web"
npm run dev &
NEXTJS_PID=$!
echo "  PID: $NEXTJS_PID"

echo ""
echo "==================================="
echo "✅ 서버 시작 완료"
echo "  - API:       http://localhost:8000"
echo "  - Swagger:   http://localhost:8000/docs"
echo "  - Dashboard: http://localhost:3000"
echo "==================================="
echo ""
echo "종료하려면 Ctrl+C 를 누르세요."

# 종료 시 자식 프로세스 정리
cleanup() {
    echo ""
    echo "서버 종료 중..."
    kill $FASTAPI_PID $NEXTJS_PID 2>/dev/null
    wait $FASTAPI_PID $NEXTJS_PID 2>/dev/null
    echo "✓ 종료 완료"
}
trap cleanup EXIT INT TERM

wait
