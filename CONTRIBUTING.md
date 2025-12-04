# Contributing to claude-notify-gtk

Thank you for your interest in contributing to claude-notify-gtk! This document provides guidelines for contributing to the project.

## AI-Assisted Development

This project embraces AI-assisted development. We use:

- **Claude Code**: For implementing features, analyzing issues, and code review
- **GitHub Copilot**: For automated PR code review
- **Human oversight**: Maintainer approval required for all merges

### Contribution Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                     PR Review Process                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Submit PR ──→ CI Automated Checks                          │
│      │              │                                       │
│      │              ├─→ Lint (Python + Shell)               │
│      │              └─→ Syntax validation                   │
│      │                    │                                 │
│      │                    ↓                                 │
│      │         Copilot Code Review (suggestions)            │
│      │                    │                                 │
│      │                    ↓                                 │
│      └────→ Maintainer Review (required) ←──────────────────┘
│                    │                                        │
│                    ↓                                        │
│            Approve & Merge (maintainer only)                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Using AI to Contribute

You're encouraged to use AI tools when contributing:

1. **Claude Code** - Great for understanding the codebase and implementing changes
2. **GitHub Copilot** - Helpful for code completion
3. **ChatGPT/Claude** - Good for brainstorming solutions

**Please disclose AI usage** in your PR using the provided template checkbox.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:hkk2018/claude-notify-gtk.git
   cd claude-notify-gtk
   ```

2. **Install dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-gi gir1.2-gtk-3.0 xdotool

   # Optional: for sound support
   sudo apt-get install pulseaudio-utils alsa-utils

   # Optional: for pretty logs
   sudo apt-get install jq
   ```

3. **Run the daemon**:
   ```bash
   ./src/daemon.py
   ```

4. **Test with example script**:
   ```bash
   ./examples/test-notification.sh
   ```

## Code Style

### Python
- Follow PEP 8 style guide
- Max line length: 120 characters
- Use meaningful variable names
- Add docstrings for classes and public methods
- Use type hints where beneficial

### Bash
- Use shellcheck to verify scripts
- Quote variables properly
- Use `set -e` for error handling
- Add comments for complex logic

### Git Commit Messages
- Use present tense ("Add feature" not "Added feature")
- Prefix with type: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`
- First line should be concise (50 chars or less)
- Add detailed explanation in body if needed
- Reference issues with `#issue-number`

Examples:
```
feat: Add notification sound customization
fix: Resolve window position on multi-monitor setup
docs: Update installation instructions for Wayland
refactor: Simplify transcript parsing logic
```

## Testing

Before submitting a pull request:

1. **Test all notification types**:
   ```bash
   ./examples/test-notification.sh
   ```

2. **Test window controls**:
   - Drag window to different positions
   - Test opacity adjustment
   - Test minimize and close
   - Test individual notification close
   - Test detail dialog (⋮ button)

3. **Test hook integration**:
   - Install hooks with `setup.sh`
   - Test with actual Claude Code usage
   - Check logs for errors

4. **Enable debug logging** (for development):
   ```python
   # In src/daemon.py, set:
   DEBUG_MODE = True
   ```
   Then check `log/debug.log` for detailed information.

## Submitting Changes

1. **Fork the repository**

2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**:
   - Write clear, concise code
   - Add comments where necessary
   - Update documentation if needed

4. **Test thoroughly**:
   - Run all tests
   - Verify no errors in logs
   - Test edge cases

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**:
   - Use the PR template
   - Describe what changes you made
   - Explain why the changes are needed
   - Reference any related issues
   - Include screenshots if UI changes
   - Declare AI tool usage

## CI/CD Pipeline

Every PR automatically triggers:

| Check | Description | Required |
|-------|-------------|----------|
| Python Lint | flake8 with max-line-length=120 | Yes |
| Shell Lint | shellcheck on hook scripts | Yes |
| Syntax Check | Python compile check | Yes |
| Copilot Review | AI code review suggestions | No (advisory) |

## Reporting Bugs

Please use the **Bug Report** issue template. Include:

1. **System information** (OS, Python version, GTK version)
2. **Steps to reproduce**
3. **Expected vs actual behavior**
4. **Logs** from `log/debug.log` or `log/notify-errors.log`
5. **Screenshots** if applicable

## Feature Requests

Please use the **Feature Request** issue template. Include:

1. **Use case description**
2. **Proposed solution**
3. **Alternatives considered**
4. **Implementation ideas** (optional)

## Code Review Process

1. **Automated checks** must pass
2. **Copilot** provides code review suggestions (advisory)
3. **Maintainer** reviews and may request changes
4. **Maintainer approval** required before merge
5. **Only maintainer** can merge to main branch

### Branch Protection

The `main` branch has protection rules:
- Pull request required
- At least 1 review approval required
- Status checks must pass
- Only maintainers can push directly

## Project Structure

```
claude-notify-gtk/
├── src/
│   ├── daemon.py          # Main GTK notification daemon
│   └── client.py          # Socket client for sending notifications
├── hooks/
│   ├── notification-hook.sh  # Claude Code notification hook
│   └── stop-hook.sh          # Claude Code stop hook
├── examples/              # Test and example scripts
├── docs/                  # Documentation
├── .claude/
│   └── CLAUDE.md          # AI development guide
└── .github/
    ├── workflows/         # CI/CD workflows
    ├── ISSUE_TEMPLATE/    # Issue templates
    └── PULL_REQUEST_TEMPLATE.md
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue for any questions about contributing!
