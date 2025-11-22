# Contributing to claude-notify-gtk

Thank you for your interest in contributing to claude-notify-gtk! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:hkk2018/claude-notify-gtk.git
   cd claude-notify-gtk
   ```

2. **Install dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install python3-gi gir1.2-gtk-3.0

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
- First line should be concise (50 chars or less)
- Add detailed explanation in body if needed
- Reference issues with `#issue-number`

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

3. **Test hook integration**:
   - Install hooks with `setup.sh`
   - Test with actual Claude Code usage
   - Check logs for errors

4. **Test on clean system** (if possible):
   - Use a VM or container
   - Run `setup.sh` and verify installation

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
   git commit -m "Add: your feature description"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request**:
   - Describe what changes you made
   - Explain why the changes are needed
   - Reference any related issues
   - Include screenshots if UI changes

## Reporting Bugs

When reporting bugs, please include:

1. **System information**:
   - OS and version (e.g., Ubuntu 22.04)
   - Python version
   - GTK version

2. **Steps to reproduce**:
   - What you did
   - What you expected to happen
   - What actually happened

3. **Logs**:
   - Check `~/Projects/claude-notify-gtk/log/` for error messages
   - Include relevant log excerpts

4. **Screenshots** (if applicable):
   - Show the issue visually

## Feature Requests

When requesting features:

1. **Describe the use case**:
   - What problem does it solve?
   - Who would benefit?

2. **Suggest implementation** (optional):
   - How might it work?
   - Any technical considerations?

3. **Consider alternatives**:
   - Are there existing workarounds?
   - Could this be a plugin/extension?

## Code Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, maintainers will merge
4. Your contribution will be included in the next release

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue for any questions about contributing!
