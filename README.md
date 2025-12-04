---
title: "claude-notify-gtk"
description: "Independent GTK-based notification system for Claude Code on Linux"
last_modified: "2025-12-04 15:21"
---

# claude-notify-gtk

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/hkk2018/claude-notify-gtk/actions/workflows/ci.yml/badge.svg)](https://github.com/hkk2018/claude-notify-gtk/actions/workflows/ci.yml)

Independent GTK-based notification system for Claude Code on Linux, featuring a draggable, scrollable notification container with sound alerts and transparency control.

## Features

- **Independent Notification System**: Does NOT use D-Bus, avoiding conflicts with GNOME notifications
- **Scrollable Container**: All notifications displayed in a single, stacked container window
- **Draggable Window**: Click and drag the header to reposition the notification window
- **Auto-positioning**: Initially appears in the right corner, out of your work area
- **Adjustable Transparency**: Cycle through 95%, 85%, 75%, 65%, and 100% opacity
- **Sound Alerts**: Different sounds for different notification types (warnings, errors, completions)
- **Persistent Notifications**: Notifications remain in the queue until manually closed
- **Transcript Preview**: Shows last assistant response from Claude Code conversation (first 5 + last 5 lines)
- **Detail Dialog**: Click ⋮ button to view full notification data (JSON) and copy Session ID
- **Time-based Color Coding**: Notification timestamps change color based on age
  - **Green** (≤5 min): Fresh notifications
  - **Yellow** (5-10 min): Recent notifications
  - **Orange** (10-20 min): Older notifications
  - **Gray** (20+ min): Archive notifications
- **Click to Focus**: Click on notification cards to focus the corresponding editor window
- **System Tray Icon**: Minimize to system tray, right-click for quick access
- **Debug Logging**: Toggle debug mode for troubleshooting (see [DEBUG-LOGGING.md](docs/DEBUG-LOGGING.md))

## Requirements

- Linux with GTK 3.0
- Python 3 with PyGObject (pre-installed on Ubuntu)
- Claude Code CLI or VSCode extension
- `xdotool` for focus feature: `sudo apt install xdotool`
- `paplay` or `aplay` for sound support (optional)
- `jq` for JSON logging (optional)

## Quick Start

```bash
# Clone
git clone https://github.com/hkk2018/claude-notify-gtk.git
cd claude-notify-gtk

# Install
chmod +x setup.sh && ./setup.sh

# Start daemon
./src/daemon.py &
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code                              │
│                         │                                    │
│                    Hook Events                               │
│                         │                                    │
│    ┌────────────────────┴────────────────────┐              │
│    ↓                                         ↓              │
│ notification-hook.sh                    stop-hook.sh        │
│    │                                         │              │
│    └────────────────────┬────────────────────┘              │
│                         │                                    │
│                         ↓                                    │
│                    client.py                                 │
│                         │                                    │
│              Unix Socket (/tmp/claude-notifier.sock)        │
│                         │                                    │
│                         ↓                                    │
│                    daemon.py                                 │
│                    (GTK Window)                              │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Window Controls

| Action | Description |
|--------|-------------|
| **Drag** | Click and drag header to reposition |
| **Opacity** | Click percentage button to cycle opacity |
| **Clear All** | Remove all notifications |
| **⋮ Detail** | View full notification data |
| **→ Focus** | Click card to focus editor window |

### Focus Feature

Click on any notification card to automatically focus the corresponding editor window.

Configure in `~/.config/claude-notify-gtk/focus-mapping.json`:

```json
{
  "projects": {
    "/home/user/my-project": { "type": "vscode" }
  },
  "default": { "type": "cursor" }
}
```

Supported: `vscode`, `cursor`, `custom`

See [Focus Feature Guide](docs/focus-feature-guide.md) for details.

### Debug Mode

Enable debug logging in `src/daemon.py`:

```python
DEBUG_MODE = True
```

View logs:
```bash
./view-debug-log.sh tail  # Real-time monitoring
./view-debug-log.sh last  # Last 50 lines
```

See [DEBUG-LOGGING.md](docs/DEBUG-LOGGING.md) for details.

## Configuration

### Claude Code Hooks

Configured automatically by `setup.sh` in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Notification": [{ "hooks": [{ "type": "command", "command": ".../notification-hook.sh" }] }],
    "Stop": [{ "hooks": [{ "type": "command", "command": ".../stop-hook.sh" }] }]
  }
}
```

### Customization

Edit `src/daemon.py` to customize:
- Window size: `set_default_size(400, 600)`
- Opacity levels: `opacities` list
- Colors: CSS in `apply_styles()`

## Troubleshooting

### Daemon not running
```bash
ps aux | grep daemon.py
./src/daemon.py &
```

### Check logs
```bash
tail -f log/notifications.log
tail -f log/notify-errors.log
./view-debug-log.sh tail  # Debug mode
```

### Test manually
```bash
echo '{"message": "test"}' | ./src/client.py
```

## Project Structure

```
claude-notify-gtk/
├── src/
│   ├── daemon.py          # GTK notification daemon
│   └── client.py          # Socket client
├── hooks/
│   ├── notification-hook.sh
│   └── stop-hook.sh
├── examples/              # Test scripts
├── docs/                  # Documentation
├── .github/
│   ├── workflows/ci.yml   # CI pipeline
│   ├── ISSUE_TEMPLATE/    # Issue templates
│   └── PULL_REQUEST_TEMPLATE.md
└── setup.sh               # Installation script
```

## Contributing

We embrace AI-assisted development! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines
- PR process (CI + Copilot review + maintainer approval)
- How to use AI tools effectively

## Why GTK? Why Not D-Bus?

**GTK**: Native Linux, pre-installed, lightweight, no extra dependencies.

**Not D-Bus**: Avoids conflicts with GNOME notifications, provides full customization control.

## License

MIT License - See [LICENSE](LICENSE)

## Credits

Created for the Claude Code community. AI-assisted development with Claude Code and GitHub Copilot.
