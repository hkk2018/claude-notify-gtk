# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in claude-notify-gtk, please report it responsibly.

### How to Report

1. **Do NOT create a public GitHub issue** for security vulnerabilities
2. Send an email to the maintainer with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- Acknowledgment within 48 hours
- Regular updates on the fix progress
- Credit in the security advisory (unless you prefer anonymity)

### Scope

This security policy covers:
- The daemon (`src/daemon.py`)
- The client (`src/client.py`)
- Hook scripts (`hooks/*.sh`)
- Installation script (`setup.sh`)

### Out of Scope

- Issues in dependencies (GTK, Python, etc.) - report to respective projects
- Issues in Claude Code itself - report to Anthropic

## Security Best Practices

When using claude-notify-gtk:

1. **Socket Security**: The Unix socket at `/tmp/claude-notifier.sock` is only accessible by the current user
2. **Hook Scripts**: Review hook scripts before installation
3. **Log Files**: Log files may contain sensitive information; secure accordingly
4. **Auto-start**: The auto-start entry runs with user privileges only
