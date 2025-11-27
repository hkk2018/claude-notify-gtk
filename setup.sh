#!/bin/bash
# claude-notify-gtk Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_CONFIG="$HOME/.claude/settings.json"

echo "==================================="
echo "claude-notify-gtk Setup"
echo "==================================="
echo ""

# 1. Make scripts executable
echo "[1/5] Making scripts executable..."
chmod +x "$SCRIPT_DIR/src/daemon.py"
chmod +x "$SCRIPT_DIR/src/client.py"
chmod +x "$SCRIPT_DIR/hooks/notification-hook.sh"
chmod +x "$SCRIPT_DIR/hooks/stop-hook.sh"
chmod +x "$SCRIPT_DIR/hooks/permission-hook.sh"

# 2. Create log directory
echo "[2/5] Creating log directory..."
mkdir -p "$SCRIPT_DIR/log"

# 3. Check Claude Code settings
echo "[3/5] Configuring Claude Code hooks..."

# 定義我們的 hooks
NOTIFICATION_HOOK="$SCRIPT_DIR/hooks/notification-hook.sh"
STOP_HOOK="$SCRIPT_DIR/hooks/stop-hook.sh"
PERMISSION_HOOK="$SCRIPT_DIR/hooks/permission-hook.sh"

# 要加入的 hooks 配置（JSON 格式）
# 注意：Notification 使用空 matcher 接收所有通知類型
# 參考：~/Workspaces/claude-code-assistant/claude-hook-test/INVESTIGATION.md
OUR_HOOKS=$(cat <<EOF
{
  "Notification": [
    {
      "matcher": "",
      "hooks": [{"type": "command", "command": "$NOTIFICATION_HOOK"}]
    }
  ],
  "Stop": [
    {
      "hooks": [{"type": "command", "command": "$STOP_HOOK"}]
    }
  ],
  "PermissionRequest": [
    {
      "hooks": [{"type": "command", "command": "$PERMISSION_HOOK"}]
    }
  ]
}
EOF
)

# 函數：合併 hooks 到 settings.json
merge_hooks() {
    local config_file="$1"
    local our_hooks="$2"
    local backup_file="${config_file}.backup.$(date +%Y%m%d_%H%M%S)"

    # 備份原始檔案
    cp "$config_file" "$backup_file"
    echo "  📦 Backup created: $backup_file"

    # 讀取現有配置
    local existing_config
    existing_config=$(cat "$config_file")

    # 檢查是否有 hooks 欄位
    local has_hooks
    has_hooks=$(echo "$existing_config" | jq 'has("hooks")')

    local new_config
    if [ "$has_hooks" = "true" ]; then
        # 合併 hooks：對每個 hook 類型，將我們的 hooks 追加到現有的陣列
        new_config=$(echo "$existing_config" | jq --argjson our_hooks "$our_hooks" '
            .hooks as $existing_hooks |
            # 對每個我們要加入的 hook 類型進行處理
            reduce ($our_hooks | keys[]) as $hook_type (
                .;
                # 檢查這個 hook command 是否已存在
                if .hooks[$hook_type] then
                    # 檢查是否已經有我們的 hook（透過 command 路徑判斷）
                    .hooks[$hook_type] as $existing |
                    $our_hooks[$hook_type] as $new_hooks |
                    # 過濾掉已存在的 hooks（避免重複）
                    ($new_hooks | map(
                        . as $new_hook |
                        if ($existing | any(
                            .hooks[]?.command == $new_hook.hooks[0].command
                        )) then empty else . end
                    )) as $filtered_new |
                    # 追加新的 hooks
                    .hooks[$hook_type] += $filtered_new
                else
                    # 直接加入新的 hook 類型
                    .hooks[$hook_type] = $our_hooks[$hook_type]
                end
            )
        ')
    else
        # 沒有 hooks 欄位，直接加入
        new_config=$(echo "$existing_config" | jq --argjson our_hooks "$our_hooks" '.hooks = $our_hooks')
    fi

    # 驗證新配置是否有效
    if ! echo "$new_config" | jq . > /dev/null 2>&1; then
        echo "  ✗ Error: Generated invalid JSON. Restoring backup..."
        cp "$backup_file" "$config_file"
        return 1
    fi

    # 寫入新配置
    echo "$new_config" | jq '.' > "$config_file"
    return 0
}

# 檢查 jq 是否安裝（必需用於合併配置）
if ! command -v jq &> /dev/null; then
    echo "  ⚠ jq is required for smart hooks merging but not found."
    echo "  Installing jq..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y jq
    elif command -v yum &> /dev/null; then
        sudo yum install -y jq
    elif command -v brew &> /dev/null; then
        brew install jq
    else
        echo "  ✗ Could not install jq automatically. Please install it manually."
        echo "  After installing jq, run this script again."
        exit 1
    fi
fi

if [ ! -f "$CLAUDE_CONFIG" ]; then
    # 建立新的 settings.json
    echo "  Creating new Claude Code settings file..."
    mkdir -p "$(dirname "$CLAUDE_CONFIG")"
    echo "{\"hooks\": $OUR_HOOKS}" | jq '.' > "$CLAUDE_CONFIG"
    if [ $? -eq 0 ]; then
        echo "  ✓ Created $CLAUDE_CONFIG"
    else
        echo "  ✗ Failed to create $CLAUDE_CONFIG"
        exit 1
    fi
else
    # 合併到現有的 settings.json
    echo "  Found existing $CLAUDE_CONFIG"
    echo "  Merging hooks configuration..."

    # 驗證現有檔案是有效的 JSON
    if ! jq . "$CLAUDE_CONFIG" > /dev/null 2>&1; then
        echo "  ✗ Error: Existing $CLAUDE_CONFIG is not valid JSON."
        echo "  Please fix it manually or delete it to create a fresh one."
        exit 1
    fi

    if merge_hooks "$CLAUDE_CONFIG" "$OUR_HOOKS"; then
        echo "  ✓ Hooks merged successfully"

        # 顯示加入的 hooks
        echo ""
        echo "  Added/Updated hooks:"
        echo "    - Notification (all types): $NOTIFICATION_HOOK"
        echo "    - Stop: $STOP_HOOK"
        echo "    - PermissionRequest: $PERMISSION_HOOK"
    else
        echo "  ✗ Failed to merge hooks. Please check the backup file."
        exit 1
    fi
fi

# 4. Set up autostart
echo "[4/5] Setting up daemon auto-start..."

AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/claude-notify-gtk.desktop"

mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Notify GTK
Comment=GTK notification daemon for Claude Code
Exec=$SCRIPT_DIR/src/daemon.py
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
EOF

echo "  ✓ Created autostart entry: $AUTOSTART_FILE"

# 5. Check dependencies
echo "[5/5] Checking dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found. Please install Python 3."
    exit 1
fi
echo "  ✓ Python 3 found"

# Check PyGObject
if ! python3 -c "import gi" 2>/dev/null; then
    echo "  ✗ PyGObject not found. Installing..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3-gi
    else
        echo "  Please install python3-gi manually for your distribution"
        exit 1
    fi
fi
echo "  ✓ PyGObject found"

# Check GTK
if ! python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk" 2>/dev/null; then
    echo "  ✗ GTK 3.0 not found. Please install GTK 3."
    exit 1
fi
echo "  ✓ GTK 3.0 found"

# Check sound players (optional)
if command -v paplay &> /dev/null || command -v aplay &> /dev/null; then
    echo "  ✓ Sound support available"
else
    echo "  ⚠ Sound players not found (optional). Install pulseaudio-utils or alsa-utils for sound support."
fi

# Check jq (optional)
if command -v jq &> /dev/null; then
    echo "  ✓ jq found (for pretty JSON logging)"
else
    echo "  ⚠ jq not found (optional). Install jq for prettier logs."
fi

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "To start the daemon now:"
echo "  $SCRIPT_DIR/src/daemon.py &"
echo ""
echo "Or log out and log back in for auto-start."
echo ""
echo "Test with:"
echo "  echo '{\"message\": \"Test notification\"}' | $SCRIPT_DIR/src/client.py"
echo ""
