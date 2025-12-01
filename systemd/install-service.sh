#!/bin/bash
# 安裝 systemd user service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/claude-notify-gtk.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

echo "=== Installing claude-notify-gtk systemd service ==="

# 建立目錄
mkdir -p "$USER_SERVICE_DIR"

# 複製 service 檔案（更新路徑）
sed "s|/home/ubuntu/Projects/claude-notify-gtk|$(dirname "$SCRIPT_DIR")|g" \
    "$SERVICE_FILE" > "$USER_SERVICE_DIR/claude-notify-gtk.service"

# 重新載入 systemd
systemctl --user daemon-reload

# 啟用並啟動
systemctl --user enable claude-notify-gtk.service
systemctl --user start claude-notify-gtk.service

echo ""
echo "✅ Service installed and started!"
echo ""
echo "常用指令："
echo "  查看狀態：systemctl --user status claude-notify-gtk"
echo "  查看日誌：journalctl --user -u claude-notify-gtk -f"
echo "  重啟服務：systemctl --user restart claude-notify-gtk"
echo "  停止服務：systemctl --user stop claude-notify-gtk"
