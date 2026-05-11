#!/bin/bash
# start_scheduler.sh - 스케줄러 백그라운드 실행 (매일 08:00/08:20/08:30 자동 실행)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PID_FILE="$SCRIPT_DIR/.scheduler.pid"
LOG_FILE="$SCRIPT_DIR/pipeline.log"

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

echo "🚀 스케줄러 백그라운드 시작..."
echo "   스케줄: 08:00 수집 → 08:20 요약 → 08:30 텔레그램 전송"
echo "   로그:   tail -f $LOG_FILE"

nohup python3 scheduler.py >> "$LOG_FILE" 2>&1 &
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
