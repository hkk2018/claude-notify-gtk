#!/bin/bash
# 測試不同時間的顏色顯示

CLIENT="$HOME/Projects/claude-notify-gtk/src/client.py"
PROJECT_PATH="/home/ubuntu/Projects/claude-notify-gtk"

# 獲取當前時間並計算不同時間點
NOW=$(date "+%Y-%m-%d %H:%M:%S")
TIME_3MIN=$(date -d "3 minutes ago" "+%Y-%m-%d %H:%M:%S")
TIME_7MIN=$(date -d "7 minutes ago" "+%Y-%m-%d %H:%M:%S")
TIME_15MIN=$(date -d "15 minutes ago" "+%Y-%m-%d %H:%M:%S")
TIME_25MIN=$(date -d "25 minutes ago" "+%Y-%m-%d %H:%M:%S")

# DEBUG 模式（用於快速測試，使用 1 分鐘單位）：
# TIME_30SEC=$(date -d "30 seconds ago" "+%Y-%m-%d %H:%M:%S")
# TIME_90SEC=$(date -d "90 seconds ago" "+%Y-%m-%d %H:%M:%S")
# TIME_3MIN=$(date -d "3 minutes ago" "+%Y-%m-%d %H:%M:%S")
# TIME_5MIN=$(date -d "5 minutes ago" "+%Y-%m-%d %H:%M:%S")

echo "發送測試通知（顏色測試）..."

# 1. 綠色 - 3分鐘前（應該顯示綠色）
cat <<EOF | $CLIENT
{
  "message": "3分鐘前的通知 - 應該是綠色",
  "notification_type": "general",
  "cwd": "$PROJECT_PATH",
  "session_id": "test-3min",
  "hook_event_name": "notification",
  "timestamp": "$TIME_3MIN"
}
EOF
sleep 1

# 2. 黃色 - 7分鐘前（應該顯示黃色）
cat <<EOF | $CLIENT
{
  "message": "7分鐘前的通知 - 應該是黃色",
  "notification_type": "general",
  "cwd": "$PROJECT_PATH",
  "session_id": "test-7min",
  "hook_event_name": "notification",
  "timestamp": "$TIME_7MIN"
}
EOF
sleep 1

# 3. 橙色 - 15分鐘前（應該顯示橙色）
cat <<EOF | $CLIENT
{
  "message": "15分鐘前的通知 - 應該是橙色",
  "notification_type": "general",
  "cwd": "$PROJECT_PATH",
  "session_id": "test-15min",
  "hook_event_name": "notification",
  "timestamp": "$TIME_15MIN"
}
EOF
sleep 1

# 4. 灰色 - 25分鐘前（應該顯示灰色）
cat <<EOF | $CLIENT
{
  "message": "25分鐘前的通知 - 應該是灰色",
  "notification_type": "general",
  "cwd": "$PROJECT_PATH",
  "session_id": "test-25min",
  "hook_event_name": "notification",
  "timestamp": "$TIME_25MIN"
}
EOF

echo "測試完成！請查看通知視窗的時間顏色。"
