---
title: "Focus Feature - User Guide"
description: "如何使用通知卡片點擊 focus 功能"
last_modified: "2025-11-24 15:44"
---

# Focus Feature - User Guide

## 功能概述

點擊通知卡片後，自動 focus 到對應的應用程式視窗（例如 VSCode、Cursor 或自訂視窗）。

## 快速開始

### 1. 確保 xdotool 已安裝

```bash
# Ubuntu/Debian
sudo apt install xdotool

# 檢查安裝
which xdotool
```

### 2. 配置 focus mapping

編輯 `~/.config/claude-notify-gtk/focus-mapping.json`：

```json
{
  "projects": {
    "/home/ubuntu/Projects/my-project": {
      "type": "vscode"
    }
  },
  "default": {
    "type": "vscode"
  }
}
```

### 3. 測試功能

```bash
# 啟動 daemon
~/Projects/claude-notify-gtk/src/daemon.py &

# 開啟 VSCode 並打開專案
code ~/Projects/my-project

# 發送測試通知
~/Projects/claude-notify-gtk/examples/test-focus.sh

# 點擊通知卡片，應該會 focus 到 VSCode
```

## 配置選項

### 內建編輯器

支援的編輯器類型：
- `vscode`: Visual Studio Code
- `cursor`: Cursor Editor

範例：
```json
{
  "projects": {
    "/home/ubuntu/Projects/vscode-project": {
      "type": "vscode"
    },
    "/home/ubuntu/Projects/cursor-project": {
      "type": "cursor"
    }
  }
}
```

### 自訂 window class 或 title

如果內建設定無法正確 focus，可以自訂：

```json
{
  "projects": {
    "/home/ubuntu/Projects/my-project": {
      "type": "vscode",
      "window_class": "Code",
      "window_title": "my-project - Visual Studio Code"
    }
  }
}
```

**如何找到正確的 window class：**

```bash
# 列出所有視窗的 class
xdotool search --name "Visual Studio Code" getwindowclassname

# 或使用 xprop 工具（點擊視窗查看）
xprop | grep WM_CLASS
```

### 自訂指令

執行自己的腳本來實現複雜的 focus 邏輯：

```json
{
  "projects": {
    "/home/ubuntu/Projects/special-project": {
      "type": "custom",
      "custom_command": "/home/ubuntu/scripts/my-focus.sh",
      "pass_data": true
    }
  }
}
```

自訂腳本會接收完整的通知資料（JSON 格式）：

```bash
#!/bin/bash
# my-focus.sh

# 讀取通知資料
notification_data=$(cat)

# 解析資料
cwd=$(echo "$notification_data" | jq -r '.cwd')
project=$(echo "$notification_data" | jq -r '.project_name')

# 實現自己的 focus 邏輯
xdotool search --name "$project" windowactivate
```

參考範例：`examples/custom-focus-example.sh`

## 故障排除

### 點擊卡片沒有反應

1. 檢查 xdotool 是否安裝：
   ```bash
   which xdotool
   ```

2. 檢查視窗是否可以被找到：
   ```bash
   xdotool search --class "Code"
   xdotool search --name "Visual Studio Code"
   ```

3. 檢查錯誤日誌：
   ```bash
   tail -f ~/.config/claude-notify-gtk/focus-errors.log
   ```

### 找不到視窗

- 確認編輯器確實在運行
- 嘗試使用 `window_class` 而非 `window_title`
- 使用 `xprop` 工具手動檢查視窗屬性

### 自訂指令不執行

1. 確認腳本可執行：
   ```bash
   chmod +x /path/to/script.sh
   ```

2. 手動測試腳本：
   ```bash
   echo '{"cwd":"/test","project_name":"test"}' | /path/to/script.sh
   ```

3. 檢查日誌：
   ```bash
   tail -f ~/.config/claude-notify-gtk/focus-errors.log
   ```

## 進階使用

### 多專案配置

```json
{
  "projects": {
    "/home/ubuntu/Projects/frontend": {
      "type": "vscode",
      "window_title": "frontend - Visual Studio Code"
    },
    "/home/ubuntu/Projects/backend": {
      "type": "cursor"
    },
    "/home/ubuntu/Projects/devops": {
      "type": "custom",
      "custom_command": "/home/ubuntu/scripts/focus-terminal.sh"
    }
  },
  "default": {
    "type": "vscode"
  }
}
```

### 與 tmux 整合

```bash
#!/bin/bash
# focus-tmux.sh

notification_data=$(cat)
project=$(echo "$notification_data" | jq -r '.project_name')

# Focus tmux session
tmux select-window -t "$project"
# Focus 終端視窗
xdotool search --class "Gnome-terminal" windowactivate
```

### 與 i3wm 整合

```bash
#!/bin/bash
# focus-i3.sh

notification_data=$(cat)
cwd=$(echo "$notification_data" | jq -r '.cwd')

# 切換到特定 workspace
case "$cwd" in
  */work/*)
    i3-msg workspace 2
    ;;
  */personal/*)
    i3-msg workspace 3
    ;;
esac

# Focus 編輯器
i3-msg '[class="Code"] focus'
```

## 相關檔案

- 配置文件：`~/.config/claude-notify-gtk/focus-mapping.json`
- 錯誤日誌：`~/.config/claude-notify-gtk/focus-errors.log`
- 範例配置：`examples/focus-mapping.example.json`
- 測試腳本：`examples/test-focus.sh`
- 自訂腳本範例：`examples/custom-focus-example.sh`
- 詳細配置說明：`docs/focus-mapping.md`
