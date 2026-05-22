#!/bin/bash
# setup.sh - 최초 1회 실행: 가상환경 생성 + 패키지 설치 + .env 설정
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "  TripleA 대시보드 초기 설정"
echo "========================================"

# 1. Python 버전 확인
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo ""
echo "[1/4] Python 버전: $PYTHON_VERSION"
python3 -c "import sys; assert sys.version_info >= (3,9), '❌ Python 3.9 이상 필요'" || exit 1
echo "  ✅ Python 버전 OK"

# 2. 가상환경 생성
echo ""
echo "[2/4] 가상환경 생성 중..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  ✅ .venv 생성 완료"
else
    echo "  ✅ .venv 이미 존재"
fi

# 3. 패키지 설치
echo ""
echo "[3/4] 패키지 설치 중..."
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "  ✅ 패키지 설치 완료"

# 4. .env 파일 설정
echo ""
echo "[4/4] .env 파일 확인..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ⚠️  .env 파일이 없어 .env.example 에서 복사했습니다."
    echo "  ✏️  .env 파일을 열어 필요한 키를 입력하세요:"
    echo ""
    echo "     ECOS_API_KEY=발급받은키"
    echo "     FRED_API_KEY=발급받은키"
    echo "     TELEGRAM_BOT_TOKEN=봇토큰"
    echo "     TELEGRAM_CHAT_ID=채팅ID"
    echo ""
    echo "  📱 텔레그램 알림을 쓰려면 봇 토큰과 채팅 ID를 직접 설정하세요."
else
    echo "  ✅ .env 파일 존재"
fi

echo ""
echo "========================================"
echo "  초기 설정 완료!"
echo ""
echo "  다음 명령으로 대시보드를 실행하세요:"
echo "    bash scripts/start_dashboard.sh"
echo "========================================"
