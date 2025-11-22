#!/bin/bash
# Claude Code Stop Hook for Linux
# 當 Claude 停止時的處理

# 設定 DISPLAY 環境變數（VSCode Extension 環境可能缺少）
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

# 讀取從 stdin 傳入的 JSON 資料
HOOK_DATA=$(cat)

# 獲取腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 設定日誌目錄
LOG_DIR="$SCRIPT_DIR/log"
mkdir -p "$LOG_DIR"

# 設定通知發送客戶端路徑
NOTIFIER_CLIENT="$SCRIPT_DIR/src/client.py"

# 寫入日誌
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="$LOG_DIR/stop.log"

echo "[$TIMESTAMP] Claude Code stopped" >> "$LOG_FILE"
echo "$HOOK_DATA" | jq '.' >> "$LOG_FILE" 2>/dev/null || echo "$HOOK_DATA" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"

# 發送通知到守護程式
if [ -f "$NOTIFIER_CLIENT" ]; then
    echo "$HOOK_DATA" | "$NOTIFIER_CLIENT"
else
    echo "[$TIMESTAMP] ERROR: Notifier client not found at $NOTIFIER_CLIENT" >> "$LOG_DIR/notify-errors.log"
fi

exit 0
