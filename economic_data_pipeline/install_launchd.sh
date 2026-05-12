#!/bin/bash
# install_launchd.sh - macOS launchd 서비스로 등록
#
# launchd로 등록하면:
#   - 재부팅 후 자동 시작
#   - 08:30에 맥북이 sleep 상태면 자동으로 wake-up 후 실행
#   - 전원 연결 상태에서 덮개를 닫아도 동작
#
# 제거:  ./uninstall_launchd.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.triplea.economic_pipeline"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
LOG_FILE="$SCRIPT_DIR/pipeline.log"

# 가상환경 확인
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 ./setup.sh 를 실행하세요."
    exit 1
fi

# LaunchAgents 디렉토리 확인
mkdir -p "$HOME/Library/LaunchAgents"

# plist 생성
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PYTHON}</string>
        <string>${SCRIPT_DIR}/main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>

    <!-- 매일 08:30 실행 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <!-- sleep 중 예약 시각이 지나면 wake-up 후 즉시 실행 -->
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>

    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>

    <!-- 환경변수: .env 파일은 main.py에서 로드하므로 별도 설정 불필요 -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <!-- 로그인 후 자동 로드 -->
    <key>RunAtLoad</key>
    <false/>

    <!-- 크래시 시 재시작 (옵션) -->
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
PLIST

echo "✅ plist 생성 완료: $PLIST_PATH"

# 기존 서비스가 있으면 언로드
launchctl unload "$PLIST_PATH" 2>/dev/null

# 새 서비스 로드
launchctl load "$PLIST_PATH"
if [ $? -eq 0 ]; then
    echo "✅ launchd 서비스 등록 완료"
    echo ""
    echo "   실행 일정 : 매일 08:30 (Asia/Seoul 시스템 시간 기준)"
    echo "   절전 대응 : sleep 상태에서도 예약 시각에 wake-on 후 실행"
    echo "   로그 확인 : tail -f $LOG_FILE"
    echo "   상태 확인 : launchctl list | grep triplea"
    echo "   제거      : ./uninstall_launchd.sh"
    echo ""
    echo "⚠️  주의: 덮개 닫힌 상태(클램셸+전원 미연결)는 wake-up이 안 될 수 있습니다."
    echo "   → 전원 어댑터 연결 상태에서 덮개를 닫으면 wake-up이 동작합니다."
else
    echo "❌ launchd 등록 실패"
    exit 1
fi
