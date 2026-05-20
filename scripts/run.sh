#!/bin/bash
# run.sh - 파이프라인 즉시 1회 실행 (수집 → DB저장 → 요약 → 텔레그램 전송)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 가상환경 확인
if [ ! -f ".venv/bin/activate" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 scripts/setup.sh 를 실행하세요:"
    echo "   ./scripts/setup.sh"
    exit 1
fi

source .venv/bin/activate
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# 텔레그램 chat_id 자동 발견 시도 (봇에 /start 보낸 후 실행)
TG_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env 2>/dev/null | cut -d= -f2)
TG_CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" .env 2>/dev/null | cut -d= -f2-)

if [ -z "$TG_CHAT_ID" ] || [ "$TG_CHAT_ID" = "YOUR_TELEGRAM_CHAT_ID" ]; then
    echo ""
    echo "🔍 TELEGRAM_CHAT_ID 자동 발견 중..."
    DISCOVERED=$(python3 -c "
import requests, sys
token = '$TG_TOKEN'
if not token or token == 'YOUR_TELEGRAM_BOT_TOKEN':
    sys.exit(0)
r = requests.get(f'https://api.telegram.org/bot{token}/getUpdates?limit=5&offset=-5', timeout=10)
for u in r.json().get('result', []):
    msg = u.get('message', u.get('channel_post', {}))
    cid = msg.get('chat', {}).get('id')
    if cid:
        print(cid)
        break
" 2>/dev/null)

    if [ -n "$DISCOVERED" ]; then
        # .env에 chat_id 자동 저장
        if grep -q "^TELEGRAM_CHAT_ID=" .env; then
            sed -i.bak "s/^TELEGRAM_CHAT_ID=.*/TELEGRAM_CHAT_ID=$DISCOVERED/" .env && rm -f .env.bak
        else
            echo "TELEGRAM_CHAT_ID=$DISCOVERED" >> .env
        fi
        # 현재 프로세스 환경변수에도 반영 (재로드 없이 바로 사용)
        export TELEGRAM_CHAT_ID="$DISCOVERED"
        echo "  ✅ chat_id 자동 발견 및 저장: $DISCOVERED"
    else
        echo "  ⚠️  chat_id 미발견. 계속 진행합니다 (텔레그램 전송 건너뜀)"
        echo "     → 텔레그램 앱에서 @bum_triple_a_bot 에 /start 전송 후 재실행하세요"
    fi
fi

echo ""
echo "▶  파이프라인 실행: $(date '+%Y-%m-%d %H:%M:%S')"
echo "────────────────────────────────────────"
python3 -m backend.main
echo "────────────────────────────────────────"
echo "✅ 완료: $(date '+%Y-%m-%d %H:%M:%S')"
