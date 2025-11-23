---
title: "claude-notify-gtk"
description: "Independent GTK-based notification system for Claude Code on Linux"
last_modified: "2025-11-22 23:54"
---

# claude-notify-gtk

Independent GTK-based notification system for Claude Code on Linux, featuring a draggable, scrollable notification container with sound alerts and transparency control.

## Features

- **Independent Notification System**: Does NOT use D-Bus, avoiding conflicts with GNOME notifications
- **Scrollable Container**: All notifications displayed in a single, stacked container window
- **Draggable Window**: Click and drag the header to reposition the notification window
- **Auto-positioning**: Initially appears in the right corner, out of your work area
- **Adjustable Transparency**: Cycle through 95%, 85%, 75%, 65%, and 100% opacity
- **Sound Alerts**: Different sounds for different notification types (warnings, errors, completions)
- **Persistent Notifications**: Notifications remain in the queue until manually closed, allowing you to review history
- **Detailed Information**: Shows project name, session ID, timestamp, working directory, and message
- **Visual Urgency**: Critical notifications (permissions, errors) have distinct red styling

## Architecture

The system consists of two main components:

1. **Daemon** ([src/daemon.py](src/daemon.py)): A persistent GTK application that displays notifications
   - Runs in the background listening on a Unix socket (`/tmp/claude-notifier.sock`)
   - Manages the notification container window
   - Handles notification display, sound playback, and auto-cleanup

2. **Client** ([src/client.py](src/client.py)): Sends notification requests to the daemon
   - Accepts JSON data from stdin
   - Connects to the daemon via Unix socket
   - Used by Claude Code hook scripts

3. **Hook Scripts** ([hooks/](hooks/)): Integration with Claude Code
   - `notification-hook.sh`: Handles Claude Code Notification events
   - `stop-hook.sh`: Handles Claude Code Stop events

## Requirements

- Linux with GTK 3.0
- Python 3 with PyGObject (pre-installed on Ubuntu)
- Claude Code CLI or VSCode extension
- `paplay` or `aplay` for sound support (optional)
- `jq` for JSON logging (optional)

## Installation

1. **Clone the repository**:
   ```bash
   cd ~/Projects
   git clone git@github.com:hkk2018/claude-notify-gtk.git
   cd claude-notify-gtk
   ```

2. **Run the setup script**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

   This will:
   - Make scripts executable
   - Configure Claude Code hooks in `~/.claude/settings.json`
   - Create log directory
   - Set up the daemon to auto-start on login

3. **Start the daemon**:
   ```bash
   ~/Projects/claude-notify-gtk/src/daemon.py &
   ```

   Or log out and log back in for auto-start to take effect.

## Usage

### Basic Usage

Once installed, the notification system will automatically display notifications when:
- Claude Code requires permission approval
- Claude Code is waiting for your input
- Claude Code completes a task
- Claude Code encounters an error
- Claude Code authentication succeeds

### Window Controls

- **Drag**: Click and drag the header to reposition the window
- **Transparency**: Click the percentage button to cycle through opacity levels
- **Clear All**: Remove all notifications at once
- **Minimize**: Hide the window (will reappear when new notifications arrive)
- **Close Individual**: Click the × button on any notification card

### Manual Testing

Send a test notification:
```bash
echo '{"cwd": "/home/user/test", "message": "Test notification", "session_id": "test-123"}' | ~/Projects/claude-notify-gtk/src/client.py
```

### Notification Types

The system automatically detects notification types and applies appropriate styling and sounds:

- **🔐 Permission Required** (critical): Red border, warning sound
- **⏸️ Waiting for Input** (critical): Red border, question sound
- **✅ Auth Success** (normal): Blue border, completion sound
- **❌ Error** (critical): Red border, error sound
- **✅ Task Completed** (normal): Blue border, instant message sound

## Configuration

### Claude Code Settings

Hook configuration is stored in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Notification": [{
      "hooks": [{
        "type": "command",
        "command": "/home/ubuntu/Projects/claude-notify-gtk/hooks/notification-hook.sh"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "/home/ubuntu/Projects/claude-notify-gtk/hooks/stop-hook.sh"
      }]
    }]
  }
}
```

### Customization

Edit [src/daemon.py](src/daemon.py) to customize:

- **Window size**: Modify `set_default_size(400, 600)` in `setup_window()`
- **Opacity levels**: Change the `opacities` list in `toggle_opacity()`
- **Colors and styling**: Edit the CSS in `apply_styles()`
- **Socket path**: Change `SOCKET_PATH` constant
- **Notification persistence**: Notifications now persist until manually closed for better message history tracking

## Troubleshooting

### Daemon not running
```bash
# Check if daemon is running
ps aux | grep daemon.py

# Start manually
~/Projects/claude-notify-gtk/src/daemon.py &
```

### Notifications not appearing

1. Check daemon is running (see above)
2. Check logs:
   ```bash
   tail -f ~/Projects/claude-notify-gtk/log/notifications.log
   tail -f ~/Projects/claude-notify-gtk/log/notify-errors.log
   ```

3. Test the client directly:
   ```bash
   echo '{"message": "test"}' | ~/Projects/claude-notify-gtk/src/client.py
   ```

### No sound

Install sound players:
```bash
sudo apt-get install pulseaudio-utils alsa-utils
```

## Project Structure

```
claude-notify-gtk/
├── src/
│   ├── daemon.py          # GTK notification daemon
│   └── client.py          # Notification sender client
├── hooks/
│   ├── notification-hook.sh   # Claude Code Notification hook
│   └── stop-hook.sh           # Claude Code Stop hook
├── examples/
│   └── test-notification.sh   # Test script
├── docs/
│   └── screenshots/       # Documentation images
├── log/                   # Log files (created on first run)
├── README.md
├── LICENSE
└── setup.sh              # Installation script
```

## Why GTK?

GTK (GIMP Toolkit) is chosen because:

1. **Native Linux Support**: Pre-installed on most Linux distributions
2. **Python Bindings**: PyGObject provides easy Python integration
3. **No External Dependencies**: No need to install Node.js, Electron, or other frameworks
4. **Lightweight**: Minimal resource usage
5. **Full Control**: Complete customization of appearance and behavior

## Why Not D-Bus?

D-Bus notifications (`notify-send`) have limitations:

- Only one daemon can own the `org.freedesktop.Notifications` service name
- GNOME Shell already occupies this, causing conflicts
- Limited stacking and customization options
- Can't create a persistent, draggable container

Our Unix socket approach provides:
- Complete independence from system notification service
- Full control over notification display and behavior
- No conflicts with existing notification systems

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.

## Credits

Created for the Claude Code community to provide better notification handling on Linux systems.
