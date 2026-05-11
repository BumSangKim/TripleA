#!/bin/bash
# stop_scheduler.sh - 백그라운드 스케줄러 중지

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.scheduler.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  실행 중인 스케줄러가 없습니다."
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "✅ 스케줄러 중지 완료 (PID: $PID)"
else
    echo "⚠️  PID $PID 프로세스가 이미 종료되어 있습니다."
    rm -f "$PID_FILE"
fi
