---
title: "Debug Logging 使用指南"
description: "claude-notify-gtk 的 debug logging 系統說明"
last_modified: "2025-11-26 00:39"
---

# Debug Logging 系統

## 概述

為了追蹤和分析 Claude Code 傳送的通知資料，以及 daemon 的處理流程，我們實作了完整的 debug logging 系統。

## 功能特性

### 自動記錄以下資訊：

1. **接收到的原始 JSON 資料**（完整的 Claude Code 通知資料）
2. **欄位解析結果**（message、notification_type、session_id 等）
3. **Transcript 搜尋流程**
   - 是否提供 transcript_path
   - 自動搜尋的路徑列表
   - 每個路徑的檢查結果（存在/不存在）
   - 最終找到的檔案路徑
4. **Transcript 內容讀取**
   - JSON 結構分析
   - 訊息數量和類型
   - 提取結果

## 開關控制

### 啟用 Debug Mode

編輯 `src/daemon.py`，修改第 25 行：

```python
# Local 開發時
DEBUG_MODE = True

# 上線部署時
DEBUG_MODE = False
```

### 設定檔位置

- Debug log: `~/Projects/claude-notify-gtk/log/debug.log`

## 使用方式

### 1. 查看即時 log（實時監控）

```bash
~/Projects/claude-notify-gtk/view-debug-log.sh tail
# 或簡寫
~/Projects/claude-notify-gtk/view-debug-log.sh t
```

### 2. 查看最後 50 行

```bash
~/Projects/claude-notify-gtk/view-debug-log.sh last
# 或簡寫
~/Projects/claude-notify-gtk/view-debug-log.sh l
```

### 3. 完整瀏覽 log

```bash
~/Projects/claude-notify-gtk/view-debug-log.sh
# 使用 less 查看，按 q 離開
```

### 4. 清空 log

```bash
~/Projects/claude-notify-gtk/view-debug-log.sh clear
# 或簡寫
~/Projects/claude-notify-gtk/view-debug-log.sh c
```

### 5. 查看 log 檔案大小和行數

```bash
~/Projects/claude-notify-gtk/view-debug-log.sh size
# 或簡寫
~/Projects/claude-notify-gtk/view-debug-log.sh s
```

## Log 格式範例

### 接收通知

```
================================================================================
[2025-11-26 00:38:47.334] 🔔 接收到新通知
{
  "cwd": "/home/ubuntu/Projects/claude-notify-gtk",
  "session_id": "test-debug-logging-123",
  "hook_event_name": "notification",
  "message": "測試 debug logging 功能"
}
================================================================================
```

### 欄位解析

```
================================================================================
[2025-11-26 00:38:47.334] 📋 解析欄位
{
  "message": "測試 debug logging 功能",
  "message_length": 19,
  "notification_type": "",
  "session_id": "test-debug-logging-123",
  "hook_event_name": "notification",
  "transcript_path": "",
  "cwd": "/home/ubuntu/Projects/claude-notify-gtk"
}
================================================================================
```

### Transcript 搜尋

```
================================================================================
[2025-11-26 00:38:47.335] 🔍 開始搜尋 transcript 檔案
{
  "session_id": "test-debug-logging-123",
  "預設搜尋路徑": [
    "/home/ubuntu/Projects/claude-notify-gtk/transcripts/test-debug-logging-123.jsonl",
    "/home/ubuntu/.claude/transcripts/test-debug-logging-123.jsonl"
  ]
}
================================================================================
```

## 分析 Claude Code 通知類型

透過收集 debug log，我們可以：

1. **識別所有通知類型**
   - 哪些 `notification_type` 值會出現
   - 哪些 `hook_event_name` 會被使用

2. **了解欄位使用模式**
   - 哪些欄位一定會有值
   - 哪些欄位可能為空
   - `message` 欄位的實際使用情況

3. **Transcript 路徑規則**
   - Claude Code 是否提供 `transcript_path`
   - 實際的 transcript 檔案存放位置

## 常見問題

### Q: Debug log 會影響效能嗎？

A: 影響很小。Debug logging 使用檔案 I/O，不會阻塞主執行緒。如果擔心效能，可以設定 `DEBUG_MODE = False`。

### Q: Log 檔案會無限增長嗎？

A: 目前沒有自動清理機制。建議定期手動清空或實作 log rotation。

### Q: 可以只記錄特定類型的 log 嗎？

A: 目前是全記錄。如果需要過濾，可以修改 `debug_log()` 函數加入 level 參數。

## 最佳實踐

1. **開發時保持開啟**：`DEBUG_MODE = True`
2. **定期檢查 log**：了解 Claude Code 的行為模式
3. **上線前關閉**：避免不必要的磁碟 I/O
4. **定期清理**：避免 log 檔案過大

## 未來改進方向

- [ ] Log rotation（自動清理舊 log）
- [ ] Log level 支援（ERROR, WARNING, INFO, DEBUG）
- [ ] 統計分析功能（不同通知類型的數量統計）
- [ ] Web UI 查看 log（可選）
