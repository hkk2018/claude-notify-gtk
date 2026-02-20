---
title: "修復 Xlib Display 連線 fd 洩漏導致 Focus 功能失效"
description: "FocusManager 每次操作都開新的 X11 Display 連線但從未關閉，導致 fd 累積超過 select() 限制後完全失效"
last_modified: "2026-02-21 00:07"
---

# 問題描述

使用者回報：daemon 運行一段時間後，點擊快捷列的 repo 按鈕無法切換視窗（完全沒反應）。

# 根因分析

## 錯誤訊息

```
focus_window_by_id failed: filedescriptor out of range in select()
Xlib focus failed: filedescriptor out of range in select()
```

## 問題根源

`FocusManager` 的 `focus_builtin_editor()` 和 `focus_window_by_id()` 每次呼叫時都會開啟新的 Xlib `Display` 連線：

```python
# ❌ 每次都新開連線
d = display.Display(env.get("DISPLAY", ":1"))
# ... 執行 focus 操作 ...
# 沒有 d.close()！
```

每個 `Display()` 連線會佔用一個 file descriptor。由於從未關閉，fd 數量持續累積。
當 fd 編號超過 `select()` 的 `FD_SETSIZE` 限制（1024）時，所有 Xlib 操作都會拋出
`filedescriptor out of range in select()` 錯誤，導致 focus 功能完全失效。

## 影響範圍

- `src/daemon.py` L470 (舊) - `focus_builtin_editor()` 中 `display.Display()` 沒 close
- `src/daemon.py` L808 (舊) - `focus_window_by_id()` 中 `display.Display()` 沒 close

## 觸發條件

一般使用下，每次通知到達 + 每次點擊快捷列按鈕都會 +1 fd。
假設每天收到 100+ 通知 + 數十次手動點擊，幾天內就會達到 1024 上限。

# 修復方案

在 `FocusManager` 中維護單一可重用的 `Display` 連線：

1. **`__init__`** 加入 `self._display = None`
2. **新增 `_get_display()` 方法**：lazy init + 自動偵測連線失效並重建
3. **`focus_builtin_editor()` / `focus_window_by_id()`**：改用 `self._get_display()` 取代 `display.Display()`
4. **異常處理**：Xlib 操作失敗時設 `self._display = None`，下次自動重建

## 核心改動

```python
def _get_display(self):
    """取得可重用的 Xlib Display 連線"""
    from Xlib import display as xlib_display
    env_display = os.environ.get("DISPLAY", ":1")

    if self._display is not None:
        try:
            self._display.get_display_name()  # 測試連線有效性
            return self._display
        except Exception:
            try:
                self._display.close()
            except Exception:
                pass
            self._display = None

    self._display = xlib_display.Display(env_display)
    return self._display
```

# 驗證結果

| 指標 | 修復前 | 修復後 |
|------|--------|--------|
| 15 次通知後 fd 增量 | +15 (每次 +1) | +1 (僅首次建立連線) |
| 長時間運行 fd 趨勢 | 持續增長至 1024 後崩潰 | 穩定（僅 1 個 Display fd） |
| focus-errors.log | 大量 `filedescriptor out of range` | 無新錯誤 |

# 教訓

- Xlib `Display()` 是需要管理生命週期的資源，類似 DB connection
- 在 daemon 這種長期運行的程式中，任何未關閉的資源都會隨時間累積成問題
- `select()` 的 FD_SETSIZE=1024 限制是 Linux 上 Xlib 的已知限制
