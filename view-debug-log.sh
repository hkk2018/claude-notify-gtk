#!/bin/bash
# 查看 debug log 的腳本

LOG_FILE="$HOME/Projects/claude-notify-gtk/log/debug.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Debug log 不存在: $LOG_FILE"
    exit 1
fi

# 檢查參數
case "$1" in
    "tail"|"t")
        # 實時監控最新的 log
        tail -f "$LOG_FILE"
        ;;
    "last"|"l")
        # 顯示最後 50 行
        tail -50 "$LOG_FILE"
        ;;
    "clear"|"c")
        # 清空 log
        echo "清空 debug log..."
        > "$LOG_FILE"
        echo "✓ Debug log 已清空"
        ;;
    "size"|"s")
        # 顯示 log 檔案大小
        ls -lh "$LOG_FILE" | awk '{print "Debug log 大小:", $5}'
        wc -l "$LOG_FILE" | awk '{print "總行數:", $1}'
        ;;
    *)
        # 預設：使用 less 查看完整 log
        less +G "$LOG_FILE"
        ;;
esac
