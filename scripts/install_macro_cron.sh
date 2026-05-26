#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3)"
fi

CRON_LINE="30 8 * * 1-5 cd $PROJECT_ROOT && $PYTHON_BIN scripts/send_daily_macro_report.py >> data/macro_telegram.log 2>&1"
TMP_FILE="$(mktemp /tmp/triplea_macro_cron.XXXXXX)"
trap 'rm -f "$TMP_FILE"' EXIT

crontab -l 2>/dev/null \
    | grep -v 'InputData/collect_daily_data.py' \
    | grep -v 'scripts/send_daily_macro_report.py' \
    > "$TMP_FILE" || true

echo "$CRON_LINE" >> "$TMP_FILE"
crontab "$TMP_FILE"

echo "Installed macro Telegram cron:"
echo "$CRON_LINE"
