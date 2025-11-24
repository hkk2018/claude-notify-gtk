---
title: "Notification Card Focus Feature - Implementation Report"
description: "完整記錄通知卡片點擊 focus 功能的開發過程"
date: "2025-11-24"
time_start: "15:30"
time_end: "23:50"
status: "completed"
---

# Notification Card Focus Feature - Implementation Report

## 功能概述

實現點擊通知卡片後自動 focus 到對應應用程式視窗的功能，支援：
- 內建編輯器（VSCode, Cursor）
- 自訂視窗 class/title
- 自訂 focus 腳本
- **專案名稱匹配**（關鍵功能）

## 開發時間線

### Phase 1: 初始需求與設計（15:30-16:00）

**需求分析**：
- 支援任意視窗 focus（不只是編輯器）
- 使用 JSON 配置檔案（`focus-mapping.json`）
- 支援專案路徑 → focus 設定的映射
- 提供內建編輯器快捷設定（vscode, cursor）
- 支援自訂 focus 腳本（接收通知資料）

**架構設計**：
```python
class FocusManager:
    - load_focus_mapping()      # 載入配置
    - get_focus_config()         # 根據專案路徑取得設定
    - focus_window()             # 主要 focus 邏輯
    - focus_builtin_editor()     # 內建編輯器 focus
    - execute_custom_command()   # 執行自訂腳本
```

### Phase 2: 基本實作（16:00-18:00）

**實作內容**：
1. ✅ `FocusManager` 類別基本框架
2. ✅ 配置檔案載入邏輯
3. ✅ 使用 xdotool 搜尋視窗
4. ✅ EventBox 包裝卡片以接收點擊事件
5. ✅ 背景線程執行 focus（避免 UI 阻塞）
6. ✅ 即時 UI 回饋（成功/失敗訊息）

**配置檔案格式**：
```json
{
  "projects": {
    "/path/to/project": {
      "type": "vscode|cursor|custom",
      "window_class": "...",
      "custom_command": "..."
    }
  },
  "default": {
    "type": "vscode"
  }
}
```

### Phase 3: 問題發現與除錯（18:00-21:00）

#### 問題 1: EventBox 點擊無反應
**現象**：點擊卡片沒有任何反應

**原因**：
- 子元件（Label, Button）阻擋了事件
- EventBox 未正確設定為接收事件

**解決方案**：
```python
event_box.set_visible_window(True)   # 確保可以接收事件
event_box.set_above_child(True)      # EventBox 層在子元件之上
```

#### 問題 2: UI 凍結
**現象**：點擊卡片後整個 UI 凍結，無法使用任何按鈕

**原因**：
- xdotool/Xlib 指令在主線程執行，阻塞 GTK 事件循環

**解決方案**：
```python
def focus_thread():
    result = self.focus_manager.focus_window(self.notification_data)
    GLib.idle_add(self.show_focus_result, ...)  # 線程安全的 UI 更新

thread = threading.Thread(target=focus_thread, daemon=True)
thread.start()
```

#### 問題 3: xdotool timeout
**現象**：xdotool 指令超時

**嘗試的解決方案**（失敗）：
- ✗ 添加 `--limit 1` - 仍然 timeout
- ✗ 移除 `--sync` - 仍然 timeout
- ✗ 分離指令（search + activate + raise）- 仍然 timeout

**根本原因**：
- Cursor 有多個視窗（包括隱藏的輔助視窗）
- xdotool 處理多個視窗時效能問題

#### 問題 4: Electron 應用不 focus
**現象**：指令執行成功但視窗沒有 focus

**研究發現**：
- Electron/Chromium 應用會忽略合成的 X11 事件
- 單純的 `xdotool windowactivate` 不起作用
- 需要完整的 5 步驟 X11 focus 流程

**解決方案** - 使用 Python Xlib 實現完整 focus 流程：
```python
# Step 1: WM_CHANGE_STATE (取消最小化)
# Step 2: _NET_ACTIVE_WINDOW ClientMessage
# Step 3: 直接設定 _NET_ACTIVE_WINDOW 屬性
# Step 4: map 視窗
# Step 5: raise 視窗
```

### Phase 4: 專案匹配功能（21:00-23:00）

#### 問題 5: Focus 到錯誤的視窗
**現象**：
- 使用 `xdotool search --limit 1 --class Cursor`
- 找到的是第一個視窗（隱藏輔助視窗 ID: 60817409，名稱只有 "cursor"）
- 實際需要的是專案視窗（ID: 58720297，名稱包含 "claude-notify-gtk"）

**分析**：
```
發現的視窗列表：
60817409: "cursor"           ← 輔助視窗（DevTools）
60817411: "cursor"           ← 輔助視窗
60817419: "cursor"           ← 輔助視窗
58720273: "... - cc-web-projects-1 - Cursor"
58720297: "... - claude-notify-gtk - Cursor"  ← 目標視窗
58720279: "... - claude-code-workspace - Cursor"
...
```

**解決方案** - 智能視窗匹配：
```python
# 1. 取得所有符合 class 的視窗（不用 --limit）
all_window_ids = search_result.stdout.strip().split('\n')

# 2. 過濾掉輔助視窗（只有 class 名稱的視窗）
for wid in all_window_ids:
    window_name = get_window_name(wid)
    if window_name == "cursor" or window_name == "code":
        continue  # 跳過輔助視窗
    candidate_windows.append((wid, window_name))

# 3. 根據專案名稱匹配
if project_name:
    for wid, wname in candidate_windows:
        if project_name.lower() in wname.lower():
            window_id = wid  # ✓ 找到匹配的視窗
            break

# 4. 如果沒找到匹配，使用第一個候選視窗
if not window_id:
    window_id = candidate_windows[0][0]
```

**結果**：
✅ 成功 focus 到包含 "claude-notify-gtk" 的 Cursor 視窗

## 技術細節

### X11 Focus 流程（針對 Electron 應用）

```python
# 連接到 X11 display
d = display.Display(":1")
root = d.screen().root
target_window = d.create_resource_object('window', int(window_id))

# Step 1: WM_CHANGE_STATE - 取消最小化
wm_state = d.intern_atom("WM_CHANGE_STATE")
ev = event.ClientMessage(
    window=target_window,
    client_type=wm_state,
    data=(32, [1, 0, 0, 0, 0])  # NormalState
)
root.send_event(ev, event_mask=...)
d.flush()
time.sleep(0.1)

# Step 2: _NET_ACTIVE_WINDOW ClientMessage - 請求視窗管理器
current_time = int(time.time() * 1000) & 0xFFFFFFFF
ev = event.ClientMessage(
    window=target_window,
    client_type=active_window_atom,
    data=(32, [2, current_time, 0, 0, 0])
)
root.send_event(ev, event_mask=...)
d.flush()
time.sleep(0.1)

# Step 3: 直接設定 _NET_ACTIVE_WINDOW 屬性
root.change_property(
    active_window_atom,
    Xatom.WINDOW,
    32,
    [int(window_id)],
    X.PropModeReplace
)
d.sync()
time.sleep(0.1)

# Step 4: map 視窗 - 確保可見
target_window.map()
d.flush()
time.sleep(0.1)

# Step 5: raise 視窗 - 移到最上層
target_window.configure(stack_mode=X.Above)
d.flush()
```

### 視窗匹配邏輯

**挑戰**：
- Electron 應用（VSCode, Cursor）會創建多個視窗
- 部分是隱藏的輔助視窗（DevTools, 擴充套件）
- 視窗名稱只有 class 名稱（"cursor", "code"）

**解決策略**：
1. **過濾輔助視窗**：跳過名稱 = class 名稱的視窗
2. **專案名稱匹配**：優先選擇標題包含專案名稱的視窗
3. **降級策略**：如果沒找到匹配的，使用第一個有意義名稱的視窗

**程式碼流程**：
```
取得所有視窗 ID
  ↓
檢查每個視窗的名稱
  ↓
過濾掉輔助視窗（名稱 = class）
  ↓
收集候選視窗（有意義的名稱）
  ↓
根據 project_name 匹配 ← 關鍵！
  ↓
選擇匹配的視窗或第一個候選視窗
```

### 線程安全的 UI 更新

**問題**：
- Focus 操作在背景線程執行
- GTK UI 更新必須在主線程

**解決方案**：
```python
def focus_thread():
    result = self.focus_manager.focus_window(data)
    # 使用 GLib.idle_add 在主線程更新 UI
    GLib.idle_add(self.show_focus_result, "✓ Focus 成功！")

thread = threading.Thread(target=focus_thread, daemon=True)
thread.start()
```

## 最終實作

### 檔案結構

```
src/daemon.py
├── FocusManager (class)
│   ├── load_focus_mapping()
│   ├── get_focus_config()
│   ├── focus_window()
│   ├── focus_builtin_editor()  ← 核心實作
│   └── execute_custom_command()
│
└── NotificationCardV3 (class)
    ├── on_card_clicked()        ← 點擊處理
    ├── show_focus_result()      ← UI 回饋
    └── get_last_error()

docs/
├── focus-mapping.md             ← 配置說明
└── focus-feature-guide.md       ← 使用指南

examples/
├── test-focus.sh
├── custom-focus-example.sh
└── find-my-editor.sh            ← 視窗偵測工具

~/.config/claude-notify-gtk/
└── focus-mapping.json           ← 使用者配置
```

### 核心功能

**1. 視窗搜尋與過濾**：
- 使用 xdotool 搜尋所有符合 class 的視窗
- 過濾掉輔助視窗（名稱只有 class 名稱）
- 收集有意義名稱的候選視窗

**2. 專案名稱匹配**：
- 從通知資料取得 `project_name`
- 在候選視窗中查找包含專案名稱的視窗
- 優先 focus 到匹配的視窗

**3. X11 Focus 操作**：
- 5 步驟完整 focus 流程
- 支援 Electron 應用
- 包含延遲以確保每步生效

**4. UI 回饋**：
- 即時顯示 focus 狀態
- 成功：綠色訊息
- 失敗：紅色錯誤訊息
- 3 秒後自動隱藏

## 測試結果

### 測試環境
- OS: Ubuntu Linux
- Window Manager: GNOME
- 編輯器: Cursor (Electron-based)
- 測試專案: claude-notify-gtk

### 測試案例

**Case 1: 基本 focus 功能**
- ✅ 點擊卡片觸發 focus
- ✅ UI 不凍結
- ✅ 顯示即時回饋

**Case 2: 專案名稱匹配**
- ✅ 正確過濾輔助視窗（"cursor"）
- ✅ 匹配到包含 "claude-notify-gtk" 的視窗
- ✅ Focus 到正確的 Cursor 視窗

**Case 3: 多個 Cursor 視窗**
- ✅ 在 7 個專案視窗 + 3 個輔助視窗中找到正確視窗
- ✅ 根據專案名稱選擇正確的視窗

**Case 4: 錯誤處理**
- ✅ 視窗不存在時顯示錯誤
- ✅ xdotool 未安裝時提示安裝
- ✅ python3-xlib 未安裝時提示安裝

## 學到的經驗

### 技術層面

1. **Electron 應用的特殊性**
   - 忽略合成的 X11 事件
   - 需要完整的 EWMH 協議實作
   - 不能只用 `xdotool windowactivate`

2. **視窗管理的複雜性**
   - 現代編輯器會創建多個視窗
   - 輔助視窗（DevTools）會干擾搜尋
   - 需要智能過濾機制

3. **GTK 線程模型**
   - UI 更新必須在主線程
   - 使用 `GLib.idle_add()` 進行跨線程通訊
   - 背景線程避免 UI 阻塞

### 開發流程

1. **問題發現與診斷**
   - 添加詳細的 DEBUG 日誌
   - 使用 xdotool 命令行測試
   - 檢查視窗屬性（xprop）

2. **漸進式解決**
   - 先解決基本功能（點擊、不凍結）
   - 再解決正確性問題（對的視窗）
   - 最後優化體驗（即時回饋）

3. **文檔的重要性**
   - 配置指南（[focus-mapping.md](../focus-mapping.md)）
   - 使用指南（[focus-feature-guide.md](../focus-feature-guide.md)）
   - 測試腳本（`examples/test-focus.sh`）

## 後續改進

### 可能的擴展（未實作）

**Tab 級別 focus**：
- 需求：Focus 到編輯器中的特定檔案/tab
- 挑戰：X11 無法控制應用內部元素
- 可能方案：
  - 編輯器 CLI (`cursor --goto file:line`)
  - 編輯器擴充套件（WebSocket/HTTP API）
  - 鍵盤模擬（xdotool key，不可靠）

**視窗狀態記憶**：
- 記住每個專案最後使用的視窗
- 優先 focus 到最近使用的視窗

**多顯示器支援**：
- 檢測視窗在哪個顯示器
- 支援跨顯示器 focus

### 程式碼優化

**已完成**：
- ✅ 移除 DEBUG 日誌
- ✅ 清理錯誤處理
- ✅ 優化視窗搜尋邏輯

**可以改進**：
- 視窗搜尋結果快取（避免每次都搜尋）
- 配置檔案熱重載
- 更詳細的錯誤分類

## 總結

### 實作成果

✅ **功能完整**：
- 支援內建編輯器（VSCode, Cursor）
- 支援自訂視窗和腳本
- 專案名稱智能匹配

✅ **使用者體驗**：
- 點擊即 focus，無需等待
- UI 不凍結
- 即時回饋成功/失敗

✅ **穩定性**：
- 正確處理 Electron 應用
- 過濾輔助視窗
- 完整的錯誤處理

### 開發時間

- **設計與實作**：2.5 小時
- **除錯與優化**：5.5 小時
- **文檔與整理**：0.5 小時
- **總計**：8.5 小時

### 關鍵突破

**最重要的發現**：
- Electron 應用需要 5 步驟 X11 focus 流程
- 必須過濾輔助視窗並根據專案名稱匹配

**最困難的問題**：
- Focus 到錯誤的視窗（花了 3 小時調查）
- Electron 應用不響應 xdotool（花了 2 小時研究）

**成功的關鍵**：
- 詳細的調試日誌
- 逐步測試和驗證
- 研究 EWMH 協議和 X11 規範
