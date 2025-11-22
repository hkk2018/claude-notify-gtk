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

# 2. Create log directory
echo "[2/5] Creating log directory..."
mkdir -p "$SCRIPT_DIR/log"

# 3. Check Claude Code settings
echo "[3/5] Configuring Claude Code hooks..."

if [ ! -f "$CLAUDE_CONFIG" ]; then
    echo "  Creating new Claude Code settings file..."
    mkdir -p "$(dirname "$CLAUDE_CONFIG")"
    cat > "$CLAUDE_CONFIG" <<EOF
{
  "hooks": {
    "Notification": [{
      "hooks": [{
        "type": "command",
        "command": "$SCRIPT_DIR/hooks/notification-hook.sh"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "$SCRIPT_DIR/hooks/stop-hook.sh"
      }]
    }]
  }
}
EOF
    echo "  ✓ Created $CLAUDE_CONFIG"
else
    echo "  ⚠ Claude Code settings already exist at $CLAUDE_CONFIG"
    echo "  Please manually add the following hooks configuration:"
    echo ""
    echo "  \"hooks\": {"
    echo "    \"Notification\": [{"
    echo "      \"hooks\": [{"
    echo "        \"type\": \"command\","
    echo "        \"command\": \"$SCRIPT_DIR/hooks/notification-hook.sh\""
    echo "      }]"
    echo "    }],"
    echo "    \"Stop\": [{"
    echo "      \"hooks\": [{"
    echo "        \"type\": \"command\","
    echo "        \"command\": \"$SCRIPT_DIR/hooks/stop-hook.sh\""
    echo "      }]"
    echo "    }]"
    echo "  }"
    echo ""
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
