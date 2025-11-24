#!/bin/bash
# 自訂 focus 腳本範例
# 這個腳本接收通知資料（JSON 格式）並實現自訂的 focus 邏輯

# 讀取通知資料（從 stdin）
notification_data=$(cat)

# 解析 JSON 資料
cwd=$(echo "$notification_data" | jq -r '.cwd')
project_name=$(echo "$notification_data" | jq -r '.project_name')
session_id=$(echo "$notification_data" | jq -r '.session_id')

# 記錄日誌
log_file="$HOME/.config/claude-notify-gtk/custom-focus.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Custom focus called" >> "$log_file"
echo "  CWD: $cwd" >> "$log_file"
echo "  Project: $project_name" >> "$log_file"
echo "  Session: $session_id" >> "$log_file"

# === 自訂 focus 邏輯範例 ===

# 範例 1: Focus 到包含專案名稱的視窗
# xdotool search --name "$project_name" windowactivate

# 範例 2: Focus 到特定 terminal (例如 tmux)
# tmux select-window -t "$project_name"

# 範例 3: Focus 到特定 workspace (GNOME)
# wmctrl -s 2  # 切換到 workspace 2

# 範例 4: 根據專案路徑決定要 focus 哪個視窗
case "$cwd" in
  */claude-notify-gtk*)
    # 這個專案用 VSCode
    xdotool search --class "Code" windowactivate
    ;;
  */my-other-project*)
    # 其他專案用 Cursor
    xdotool search --class "Cursor" windowactivate
    ;;
  *)
    # 預設使用 VSCode
    xdotool search --class "Code" windowactivate
    ;;
esac

echo "Custom focus completed" >> "$log_file"
