---
title: "修復 Xlib Display thread safety 及 GTK main thread 阻塞"
description: "共用的 Xlib Display 連線缺乏 thread lock 導致 corruption；scan_open_ide_windows 在 main thread 阻塞 GTK loop"
last_modified: "2026-03-01 03:21"
---

# 問題描述

修復 fd 洩漏（2026-02-21）後，daemon 仍會在使用一段時間後出現「程式沒有回應」的 hang 症狀。
系統跳出「等待/關閉」的對話框。

# 根因分析

## 問題 1：Xlib Display 連線缺乏 thread safety

### 背景

上次修復 fd 洩漏時，將 `display.Display()` 改為重用 `self._display`，但 **python-xlib 的 Display 物件不是 thread-safe 的**。

### 觸發路徑

多個背景 thread 會同時存取 `self._display`：
- `focus_builtin_editor()` — 通知卡片的 focus icon 點擊（背景 thread）
- `focus_window_by_id()` — 快捷列按鈕點擊（背景 thread）

當使用者快速點擊多個按鈕，或通知密集到達時，兩個 thread 可能同時操作同一個 Display connection，導致 Xlib internal state corruption → deadlock 或 crash。

### 修復

加入 `threading.Lock()`：

```python
self._display_lock = threading.Lock()

# 所有 Xlib 操作都用 with self._display_lock 包住
with self._display_lock:
    d = self._get_display()
    # ... Xlib 操作 ...
```

## 問題 2：scan_open_ide_windows 阻塞 GTK main loop

### 觸發路徑

`refresh_shortcut_bar()` 直接在 GTK main thread 呼叫 `scan_open_ide_windows()`，這個方法會：
1. 對每個編輯器類型跑 `xdotool search` subprocess（2 秒 timeout）
2. 對每個找到的視窗跑 `xdotool getwindowname` subprocess（1 秒 timeout）

以 11 個視窗為例，需要約 0.36 秒。如果 xdotool 或 X server 卡住，最壞情況下會阻塞 main thread 數十秒，導致 GTK 視窗完全無回應。

### 呼叫場景

- `GLib.idle_add(self.refresh_shortcut_bar)` — 初始化時
- `on_refresh_shortcut_bar()` — 手動點 refresh 按鈕
- `on_shortcut_chars_change()` — 設定頁面修改字數限制

### 修復

將掃描操作移到背景 thread，完成後用 `GLib.idle_add` 回到 main thread 更新 UI：

```python
def refresh_shortcut_bar(self):
    def scan_thread():
        ide_windows = self.focus_manager.scan_open_ide_windows()
        GLib.idle_add(self._update_shortcut_buttons, ide_windows)

    thread = threading.Thread(target=scan_thread, daemon=True)
    thread.start()

def _update_shortcut_buttons(self, ide_windows):
    # GTK UI 更新（main thread）
    ...
```

# 驗證結果

| 測試 | 結果 |
|------|------|
| 5 個並行通知 | fd 穩定 13，0 個 focus 錯誤 |
| 快捷列掃描 | 不再阻塞 GTK main loop |

# 教訓

- 將資源從「每次新建」改為「共用」時，必須同時考慮 thread safety
- GTK main thread 不能放任何可能阻塞的操作（subprocess、network、sleep）
- daemon 類程式的 hang 問題比 crash 更難排查，因為 process 還活著但功能失效
