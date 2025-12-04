# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-04

### Added
- **Transcript Preview**: Display last assistant response from Claude Code conversation
  - Shows first 5 lines + "... (X lines omitted) ..." + last 5 lines
  - Parses JSONL format transcript files correctly
  - Auto-detects transcript path from session ID
- **Detail Dialog**: Click ⋮ button on notification card to view full data
  - Shows complete notification JSON
  - Copy Session ID button
- **Debug Logging System**: Toggle DEBUG_MODE for troubleshooting
  - Logs all incoming notification data
  - Tracks transcript search and parsing
  - Helper scripts: `view-debug-log.sh`, `restart-daemon.sh`
- **Time-based Color Coding**: Notification timestamps change color based on age
  - Green (≤5 min), Yellow (5-10 min), Orange (10-20 min), Gray (20+ min)
- **Click to Focus**: Click notification cards to focus corresponding editor window
  - Supports VSCode, Cursor, and custom scripts
  - Configurable via `focus-mapping.json`
- **CI/CD Pipeline**: GitHub Actions for automated testing
  - Python lint (flake8)
  - Shell lint (shellcheck)
  - Syntax validation
  - Copilot code review integration
- **GitHub Templates**: Issue and PR templates for better collaboration
- **Security Policy**: SECURITY.md for vulnerability reporting

### Changed
- **Message Display**: Moved message to footer (left side, gray text)
- **UI Simplification**: Removed role icons from transcript display
- **README**: Complete rewrite with architecture diagram, badges, and concise format
- **CONTRIBUTING**: Added AI-assisted development workflow documentation

### Fixed
- **JSONL Parsing**: Fixed transcript reading for Claude Code's JSON Lines format
- **Status Messages**: More informative messages when transcript not found

## [0.1.0] - 2025-11-22

### Added
- Initial implementation of claude-notify-gtk
- GTK-based notification daemon with scrollable container
- Draggable window for repositioning notifications
- Adjustable transparency (95%, 85%, 75%, 65%, 100%)
- Sound alerts for different notification types
- Detailed information display (Project, Session, Time, Message)
- Visual urgency levels (critical vs normal)
- Unix socket-based IPC (no D-Bus conflicts)
- Claude Code hook scripts (Notification and Stop events)
- Automatic installation script (`setup.sh`)
- Auto-start on login via XDG autostart
- Test scripts for development
- System tray icon support

### Architecture
- Python 3 + PyGObject for GTK integration
- Unix domain socket at `/tmp/claude-notifier.sock`
- Separate daemon and client design
- Hook-based integration with Claude Code

[1.0.0]: https://github.com/hkk2018/claude-notify-gtk/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/hkk2018/claude-notify-gtk/releases/tag/v0.1.0
