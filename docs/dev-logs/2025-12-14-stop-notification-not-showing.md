---
title: "Stop 通知不顯示問題排查"
description: "NotificationCardV3 引用不存在的 self.config 導致 AttributeError"
last_modified: "2025-12-14 20:57"
---

# Stop 通知不顯示問題排查

## 問題現象

- Stop hook 有觸發（`stop.log` 有記錄）
- Daemon 有收到通知（`debug.log` 顯示「🔔 接收到新通知」）
- 但通知卡片沒有顯示在 UI 上
- Debug log 只記錄到「📄 Transcript 處理開始」就停了

## 排查過程

1. 檢查 `stop.log` → hook 有觸發 ✓
2. 檢查 `debug.log` → daemon 有收到 ✓
3. 注意到 log 在「Transcript 處理開始」後就沒了
4. 檢查 daemon stdout → 發現 `AttributeError`

## 根本原因

```python
# NotificationCardV3.__init__ 第 1226 行
head_lines = self.config["behavior"].get("transcript_head_lines", 5)
```

`NotificationCardV3` 類別沒有 `config` 屬性。這個屬性只存在於 `NotificationContainer`。

### 錯誤訊息（來自 daemon stdout）
```
AttributeError: 'NotificationCardV3' object has no attribute 'config'
```

### 呼叫流程
```
handle_notification()
  ├── debug_log("📋 解析欄位")
  ├── debug_log("📄 Transcript 處理開始")
  └── add_notification()
        └── NotificationCardV3.__init__()
              └── self.config["behavior"]...  ← 💥 AttributeError
```

Exception 在 `NotificationCardV3.__init__` 內拋出，後續的 debug_log 都沒機會執行。

## 為什麼之前沒發現？

這段程式碼只在 `transcript_path` 存在時才會執行：

```python
if transcript_path:
    head_lines = self.config["behavior"].get(...)  # 只有這條路徑會觸發
```

之前測試時可能：
1. 沒有提供 `transcript_path`
2. 或者用的是小檔案，走了不同的程式碼路徑

## 修復

直接使用預設值，不依賴不存在的屬性：

```python
# Before
head_lines = self.config["behavior"].get("transcript_head_lines", 5)
tail_lines = self.config["behavior"].get("transcript_tail_lines", 5)

# After
head_lines = 5
tail_lines = 5
```

## 同時修復的問題

發現 transcript 檔案可能很大（9MB），加入了 tail 讀取優化：
- 檔案 > 512KB 時，只讀取最後 512KB
- 避免大檔案阻塞 GTK 主線程

## 教訓

1. **daemon stdout 要看** - Exception 訊息印在那裡，不在 debug.log
2. **動態語言的屬性存取不會預先檢查** - 要靠測試覆蓋或 type hints
3. **條件分支內的程式碼容易漏測** - 這次是 `if transcript_path:` 內的程式碼
