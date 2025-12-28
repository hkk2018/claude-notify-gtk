#!/bin/bash
# 重啟 daemon 的簡單腳本

# 設定 DISPLAY/XAUTHORITY 環境變數
# 優先使用現有環境變數，否則用標準預設值
# 詳見: docs/dev-logs/2025-12-26-display-env-detection.md
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
if [ -z "$XAUTHORITY" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi

# 停止現有 daemon (只停 daemon.py，不要 killall python3)
pkill -f "daemon.py" 2>/dev/null
sleep 1

# 啟動新 daemon
~/Projects/ken/claude-notify-gtk/src/daemon.py &

sleep 2

# 檢查狀態
if pgrep -f daemon.py > /dev/null; then
    echo "✓ Daemon 已啟動，PID: $(pgrep -f daemon.py)"
else
    echo "✗ Daemon 啟動失敗"
    exit 1
fi
