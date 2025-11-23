# Claude Code Development Guide for claude-notify-gtk

## Project Overview

This is a GTK-based notification system for Claude Code on Linux. The project consists of:

- **Python + GTK**: Main notification daemon using PyGObject
- **Bash scripts**: Hook scripts for Claude Code integration
- **Unix socket**: IPC mechanism for daemon-client communication

## Development Principles

### Code Style
- **Python**: Follow PEP 8, use type hints where beneficial
- **Bash**: Use shellcheck-compliant code
- **Comments**: Use Chinese for implementation details, English for API documentation

### Testing Requirements
After implementing new features, test the Happy Flow:

1. **Daemon startup**: Verify it starts without errors
2. **Socket connection**: Test client can connect to daemon
3. **Notification display**: Send test notifications of different types
4. **Window controls**: Test drag, opacity, close functionality
5. **Hook integration**: Test with actual Claude Code hooks

Use `examples/test-notification.sh` for basic testing.

### File Structure
- `src/daemon.py`: GTK notification daemon (main UI and socket server)
- `src/client.py`: Simple client to send notifications via socket
- `hooks/*.sh`: Claude Code hook scripts (should be generic, use SCRIPT_DIR)
- `examples/`: Test scripts and usage examples
- `docs/`: Documentation and screenshots

### Important Notes

1. **GTK Deprecation**: Avoid deprecated Gdk.Screen APIs, use Gdk.Display instead
2. **CSS Limitations**: GTK CSS doesn't support all standard CSS properties (e.g., cursor)
3. **Path Handling**: Always use `SCRIPT_DIR` in hook scripts for portability
4. **Socket Path**: Currently hardcoded to `/tmp/claude-notifier.sock`

### UI Design Lessons (V3 Card Development)

**Layout Principles:**
- Keep secondary info (time, session) in footer, not header - reduces visual clutter
- Use "at" instead of ":" for event-time separator (e.g., "Notification at 15:08") - clearer reading
- Footer text alpha should be ≥70% for readability (40-50% is too faint)
- Icon placement matters: header icon (event type) provides quick visual context

**GTK Widget Gotchas:**
- `set_ellipsize(3)` alone won't work - must set `set_max_width_chars()` too
- `pack_start` with `hexpand=True` vs `pack_end` affects alignment significantly
- Text alpha in Pango markup: use `<span alpha="70%">` not CSS opacity

**Development Workflow:**
- Config file values override DEFAULT_CONFIG - must delete/update config when changing defaults
- Always kill old daemon before testing new code: `pkill -f daemon.py`
- Keep multiple card versions (V0, V1, V2, V3) during iteration - easier to A/B compare

**Key Mistake to Avoid:**
- Don't put too much info in one line - split header/footer clearly for better visual hierarchy

## Common Tasks

### Adding New Notification Types

1. Update `handle_notification()` in `src/daemon.py`
2. Add new type detection logic
3. Define title, urgency level, and sound
4. Test with `examples/test-notification.sh`

### Changing Window Appearance

1. Edit CSS in `apply_styles()` method (line 207-269)
2. Catppuccin Mocha color scheme is used by default
3. Test with different opacity levels

### Adding New Sound Alerts

1. Check available sounds in `/usr/share/sounds/freedesktop/stereo/`
2. Add to `play_sound()` method
3. Update notification type handling to use new sound

## Debugging

### Daemon Issues
```bash
# Run daemon in foreground to see errors
~/Projects/claude-notify-gtk/src/daemon.py

# Check if socket exists
ls -la /tmp/claude-notifier.sock
```

### Hook Issues
```bash
# Check logs
tail -f ~/Projects/claude-notify-gtk/log/notifications.log
tail -f ~/Projects/claude-notify-gtk/log/notify-errors.log

# Test hook manually
echo '{"message": "test"}' | ~/Projects/claude-notify-gtk/hooks/notification-hook.sh
```

### Client Issues
```bash
# Test client directly
echo '{"message": "test"}' | ~/Projects/claude-notify-gtk/src/client.py
```

## Release Checklist

Before creating a new release:

1. Update version number in README.md
2. Test all notification types with `examples/test-notification.sh`
3. Test installation with `setup.sh` on clean system
4. Verify hook scripts work with actual Claude Code
5. Update CHANGELOG.md (if exists)
6. Create git tag with version number

## Architecture Decisions

### Why GTK?
- Native on Linux, pre-installed on Ubuntu
- Python bindings (PyGObject) readily available
- Lightweight, no need for Electron or Node.js
- Full control over UI

### Why Unix Socket?
- No D-Bus conflicts with GNOME notifications
- Simple, lightweight IPC mechanism
- Easy to debug (can use `socat` to test)
- No need for additional dependencies

### Why Separate Daemon and Client?
- Daemon runs persistently, avoiding startup delay
- Client is simple and fast, suitable for hook scripts
- Clear separation of concerns
- Allows future extensions (multiple clients, different UIs)
