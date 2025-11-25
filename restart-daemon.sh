#!/bin/bash
# 重啟 daemon 的簡單腳本

# 停止現有 daemon
killall -9 python3 2>/dev/null
sleep 1

# 啟動新 daemon
~/Projects/claude-notify-gtk/src/daemon.py &

sleep 2

# 檢查狀態
if pgrep -f daemon.py > /dev/null; then
    echo "✓ Daemon 已啟動，PID: $(pgrep -f daemon.py)"
else
    echo "✗ Daemon 啟動失敗"
    exit 1
fi
