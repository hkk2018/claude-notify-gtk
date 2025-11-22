# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial implementation of claude-notify-gtk
- GTK-based notification daemon with scrollable container
- Draggable window for repositioning notifications
- Adjustable transparency (95%, 85%, 75%, 65%, 100%)
- Sound alerts for different notification types
- Auto-close notifications after 30 seconds
- Detailed information display (Project, Session, Time, Message)
- Visual urgency levels (critical vs normal)
- Unix socket-based IPC (no D-Bus conflicts)
- Claude Code hook scripts (Notification and Stop events)
- Automatic installation script (`setup.sh`)
- Auto-start on login via XDG autostart
- Test script with 6 example notification types
- Comprehensive documentation (README, CONTRIBUTING)
- Development guide for Claude Code (`.claude/CLAUDE.md`)

### Architecture
- Python 3 + PyGObject for GTK integration
- Unix domain socket at `/tmp/claude-notifier.sock`
- Separate daemon and client design
- Hook-based integration with Claude Code

### Status
- 🚧 **In Development**: Core features implemented but not fully tested
- Pending comprehensive testing and bug fixes before v1.0.0 release

[Unreleased]: https://github.com/hkk2018/claude-notify-gtk/compare/75a456d...HEAD
