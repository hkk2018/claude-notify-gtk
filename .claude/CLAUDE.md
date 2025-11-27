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

**Color Coding for Priority:**
- Time-based color coding helps users identify fresh vs. stale notifications at a glance
- Color scheme (Catppuccin Mocha): Green (≤5min) → Yellow (5-10min) → Orange (10-20min) → Gray (20+min)
- Use `foreground` attribute in Pango markup for color, not `alpha` (which affects transparency)
- Calculate time difference from notification timestamp, not card creation time

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

## Settings Dialog - 即時預覽機制

**重要原則**：所有設定項目必須即時反映到 UI，讓使用者可以立即看到效果。

### 新增設定項目的完整步驟

1. **DEFAULT_CONFIG 加入預設值**
   ```python
   DEFAULT_CONFIG = {
       "behavior": {
           "new_setting": 10  # 加入預設值
       }
   }
   ```

2. **SettingsDialog.create_*_page() 加入 UI 控件**
   ```python
   # 在對應的頁面方法中加入
   label = Gtk.Label(label="New Setting:", xalign=0)
   grid.attach(label, 0, row, 1, 1)

   new_spin = Gtk.SpinButton()
   new_spin.set_range(1, 100)
   new_spin.set_value(self.config["behavior"].get("new_setting", 10))
   grid.attach(new_spin, 1, row, 1, 1)
   self.new_spin = new_spin  # 保存引用
   row += 1
   ```

3. **connect_preview_signals() 連接即時預覽信號**
   ```python
   # 如果影響外觀/尺寸：
   self.new_spin.connect("value-changed", self.on_preview_change)

   # 如果需要特殊處理（如快捷列）：
   self.new_spin.connect("value-changed", self.on_new_setting_change)
   ```

4. **加入對應的處理方法**（如需特殊處理）
   ```python
   def on_new_setting_change(self, widget):
       value = int(self.new_spin.get_value())
       self.parent.config["behavior"]["new_setting"] = value
       self.parent.some_refresh_method()  # 呼叫對應的更新方法
   ```

5. **get_updated_config() 加入設定讀取**
   ```python
   config["behavior"]["new_setting"] = int(self.new_spin.get_value())
   ```

6. **on_reset_to_default() 加入重置邏輯**
   ```python
   self.new_spin.set_value(DEFAULT_CONFIG["behavior"]["new_setting"])
   ```

### 即時預覽類型

| 設定類型 | 處理方式 | 範例 |
|---------|---------|------|
| 外觀（透明度、字體、圓角） | `on_preview_change` + `apply_styles()` | opacity, font_size |
| 視窗尺寸 | `on_preview_change` + `resize()` | width, height |
| 快捷列相關 | 專屬方法 + `refresh_shortcut_bar()` | shortcut_max_chars |
| 行為設定（不需即時） | 僅儲存，下次生效 | sound_enabled |

### 常見錯誤

❌ 忘記在 `connect_preview_signals()` 連接信號 → 設定改變無反應
❌ 忘記在 `get_updated_config()` 讀取值 → 設定不會儲存
❌ 忘記在 `on_reset_to_default()` 重置 → Reset 按鈕無效

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

## Claude Code Hook 配置

詳細的 Hook 配置說明請參考 [docs/hooks-configuration.md](../docs/hooks-configuration.md)。

**快速參考**：
- Notification hook 使用空 matcher `"matcher": ""`
- 只有需要權限的操作才會觸發 Notification hook
- 初始權限模式選擇不會觸發任何 hook
