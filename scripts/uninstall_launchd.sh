#!/bin/bash
# uninstall_launchd.sh - launchd 서비스 제거

PLIST_NAME="com.triplea.economic_pipeline"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

launchctl unload "$PLIST_PATH" 2>/dev/null
rm -f "$PLIST_PATH"

echo "✅ launchd 서비스 제거 완료"
