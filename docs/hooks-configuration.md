---
title: "Claude Code Hook 配置指南"
description: "Claude Code hooks 的配置方式與觸發條件"
last_modified: "2025-11-27 14:30"
---

# Claude Code Hook 配置指南

## Hook 事件與 Matcher 支援

| 事件 | 支援 matcher | 說明 |
|------|-------------|------|
| PreToolUse | ✅ | 工具名稱（Bash, Write, Edit 等）|
| PostToolUse | ✅ | 同上 |
| PermissionRequest | ✅ | 同上 |
| Notification | ✅ | 通知類型（permission_prompt, idle_prompt 等）|
| Stop | ❌ | 不支援 |
| UserPromptSubmit | ❌ | 不支援 |
| SessionStart/End | ❌ | 不支援 |

## Notification Hook 配置

### 推薦配置

使用**空 matcher** 接收所有通知類型：

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/notification-hook.sh"
          }
        ]
      }
    ]
  }
}
```

### 觸發條件

Notification hook **僅在以下情況觸發**：

1. Claude 需要權限使用工具時（如 Write、Edit）
2. 閒置超過 60 秒等待輸入時

### 不會觸發的情況

- 初始 "Ask before edit / Edit automatically" 權限模式選擇
- 已在 `permissions.allow` 列表中的操作（這些操作不需要請求權限）

## PermissionRequest Hook 配置

PermissionRequest hook 在 Claude Code v2.0.45+ 可用，用於自動處理權限請求：

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/permission-hook.sh"
          }
        ]
      }
    ]
  }
}
```

如果不返回決定（allow/deny），會讓用戶自己決定，同時可以用來發送通知。

## 完整配置範例

本專案使用的完整 hooks 配置：

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/home/ubuntu/Projects/claude-notify-gtk/hooks/notification-hook.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/home/ubuntu/Projects/claude-notify-gtk/hooks/stop-hook.sh"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/home/ubuntu/Projects/claude-notify-gtk/hooks/permission-hook.sh"
          }
        ]
      }
    ]
  }
}
```

## 參考資料

- 原始調查記錄：`~/Workspaces/claude-code-assistant/claude-hook-test/INVESTIGATION.md`
- 官方文檔：https://code.claude.com/docs/en/hooks
