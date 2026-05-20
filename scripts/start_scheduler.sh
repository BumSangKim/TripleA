#!/bin/bash
# start_scheduler.sh - 스케줄러 백그라운드 실행 (매일 08:00/08:20/08:30 자동 실행)
#
# ⚠️  절전 모드(덮개 닫힘) 주의사항
# - 맥북 덮개를 닫으면 이 스케줄러는 일시 정지(suspended)됩니다.
# - caffeinate 옵션으로 sleep을 방지하거나, install_launchd.sh로 launchd에 등록하세요.
#   옵션 A (간단):  덮개를 열어두거나 전원을 연결한 상태로 사용
#   옵션 B (권장):  ./install_launchd.sh  → macOS 서비스로 등록, 재부팅 후에도 자동 실행

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
PID_FILE="$PROJECT_ROOT/.scheduler.pid"
LOG_FILE="$PROJECT_ROOT/data/pipeline.log"

if [ ! -f ".venv/bin/activate" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 ./setup.sh 를 실행하세요."
    exit 1
fi

# 이미 실행 중인지 확인
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⚠️  스케줄러가 이미 실행 중입니다 (PID: $OLD_PID)"
        echo "   중지하려면: ./stop_scheduler.sh"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

source .venv/bin/activate
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

echo "🚀 스케줄러 백그라운드 시작..."
echo "   스케줄: 08:00 수집 → 08:20 요약 → 08:30 텔레그램 전송"
echo "   로그:   tail -f $LOG_FILE"

nohup python3 -m backend.scheduler >> "$LOG_FILE" 2>&1 &
SCHEDULER_PID=$!
echo "$SCHEDULER_PID" > "$PID_FILE"

sleep 1
if kill -0 "$SCHEDULER_PID" 2>/dev/null; then
    echo "✅ 스케줄러 시작 완료 (PID: $SCHEDULER_PID)"
    echo ""
    echo "   현재 시간: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "   중지:      ./stop_scheduler.sh"
    echo "   로그 확인: tail -f pipeline.log"
else
    echo "❌ 스케줄러 시작 실패. 로그 확인:"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
