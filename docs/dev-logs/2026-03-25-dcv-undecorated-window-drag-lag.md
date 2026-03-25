---
title: "DCV 環境下無邊框視窗拖動卡頓問題排查與修復"
description: "在 NICE DCV Virtual Session 環境中，GTK3 無邊框視窗使用手動 move() 拖動時嚴重卡頓，改用 begin_move_drag 委託 WM 處理後解決"
last_modified: "2026-03-25 21:03"
---

# DCV 環境下無邊框視窗拖動卡頓問題排查與修復

## 問題描述

重開機後，claude-notify-gtk 的通知視窗拖動變得非常卡頓：滑鼠移動很大距離，視窗只移動一小段。其他應用程式（Chrome、Cursor 等 Electron 應用）拖動都正常。

## 環境

| 項目 | 內容 |
|------|------|
| OS | Ubuntu 22.04 LTS |
| DCV | 2023.1 Virtual Session |
| GPU | NVIDIA Tesla T4（但桌面合成走 llvmpipe 軟體渲染） |
| 桌面 | GNOME 42 (Mutter) |
| 顯示 | Xdcv (:1)，2560x1328 |

## 排查過程

### 1. 初步懷疑：CPU 過載

gnome-shell 吃 200%+ CPU（llvmpipe 軟體渲染），懷疑是效能問題。

- 重啟 gnome-shell → CPU 降到正常，但拖動仍卡 ❌
- 關閉動畫 (`enable-animations false`) → 無效 ❌
- 設定 opacity 為 1.0 → 無效 ❌
- 加 NVIDIA GLX 環境變數 → 無效 ❌

**結論**：不是效能問題。

### 2. 確認問題範圍

- Chrome 拖動 → 順 ✅
- Cursor 拖動 → 順 ✅
- daemon.py (GTK3) 拖動 → 卡 ❌

Electron 應用有自己的 GPU compositing pipeline，不受影響。

### 3. 建立最小重現

寫了一系列測試視窗，逐步加入 daemon.py 的視窗屬性：

| 測試 | 屬性 | 結果 |
|------|------|------|
| Test1 | 純 Gtk.Window（有邊框） | 順 ✅ |
| Test2 | 全部屬性（模擬 daemon.py） | 卡 ❌ |
| Test3 | 去掉 `accept_focus(False)` | 卡 ❌ |
| Test4 | 去掉 RGBA visual | 卡 ❌ |
| Test5 | 去掉 UTILITY type hint | 卡 ❌ |
| Test6 | **只加 `set_decorated(False)`** | **卡 ❌** |
| Test7 | 只加 `set_keep_above(True)` | 順 ✅ |

**結論**：`set_decorated(False)`（無邊框視窗）是問題根源。

### 4. 找到解法

| 測試 | 拖動方式 | 結果 |
|------|----------|------|
| Test8 | 無邊框 + `begin_move_drag` | 順 ✅ |
| Test9 | 有邊框 + 自訂 HeaderBar | 順 ✅ |

## 根本原因

在 DCV Virtual Session 環境下，無邊框視窗（`set_decorated(False)`）使用手動 `motion-notify-event` + `self.move()` 拖動時，**event 座標與視窗位置的映射出現不匹配**。

推測原因：DCV 的 Xdcv 虛擬 X server 對無邊框視窗的 motion event 座標傳遞方式與原生 X server 不同，導致每次 `get_position()` + `move()` 的 delta 計算不準確。

而 `begin_move_drag()` 是委託給 Window Manager（Mutter）處理的，WM 內部直接操作視窗位置，不依賴 motion event 的座標回傳，因此不受影響。

## 修復方式

將 `on_drag_start` 中的手動拖動改為 `begin_move_drag`：

```python
# 修復前：手動追蹤座標
def on_drag_start(self, widget, event):
    if event.button == 1:
        self.is_dragging = True
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root

def on_drag_motion(self, widget, event):
    if self.is_dragging:
        delta_x = event.x_root - self.drag_start_x
        delta_y = event.y_root - self.drag_start_y
        win_x, win_y = self.get_position()
        self.move(int(win_x + delta_x), int(win_y + delta_y))  # 座標不匹配！
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root

# 修復後：委託 WM 處理
def on_drag_start(self, widget, event):
    if event.button == 1:
        self.begin_move_drag(
            event.button,
            int(event.x_root),
            int(event.y_root),
            event.time
        )
```

## 經驗教訓

1. **GTK3 無邊框視窗拖動**：在遠端桌面環境（DCV、VNC 等）中，避免使用 `motion-notify-event` + `self.move()` 手動實作拖動，改用 `begin_move_drag()` 委託 WM 處理
2. **問題定位方法**：用最小重現 + 逐一排除屬性的方式，比猜測效能問題更有效率
3. **Electron vs GTK3**：Electron 應用有獨立的 compositing pipeline，不受 WM 軟體渲染影響；GTK3 原生應用則完全依賴 WM
4. **重開機後變慢**：不一定是硬體或驅動問題，也可能是系統負載變化讓原本就存在的邊界問題（座標不匹配）變得明顯
