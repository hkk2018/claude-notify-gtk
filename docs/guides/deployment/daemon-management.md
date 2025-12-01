---
title: "Daemon 管理與維運"
description: "通知服務的啟動方式、健康檢查機制與故障恢復"
last_modified: "2025-12-02 01:29"
---

# Daemon 管理與維運

## 啟動方式

### 手動啟動

```bash
~/Projects/claude-notify-gtk/src/daemon.py &
```

適合開發測試，但需要手動管理進程。

### Systemd 管理（推薦）

```bash
# 安裝服務
./systemd/install-service.sh

# 常用指令
systemctl --user status claude-notify-gtk   # 查看狀態
systemctl --user restart claude-notify-gtk  # 重啟服務
systemctl --user stop claude-notify-gtk     # 停止服務
journalctl --user -u claude-notify-gtk -f   # 查看日誌
```

優點：
- 開機自動啟動
- 進程崩潰後 3 秒自動重啟
- 統一的日誌管理

# 健康檢查機制

## 兩層保護架構

```
┌─────────────────────────────────────────────────┐
│                   Systemd                        │
│         監控：daemon.py 進程是否存活              │
│         動作：進程死亡 → 3 秒後重啟               │
├─────────────────────────────────────────────────┤
│              內建 Watchdog                       │
│         監控：Socket 連線是否正常                 │
│         動作：連線失敗 → 自動重建 socket          │
└─────────────────────────────────────────────────┘
```

| 層級 | 監控對象 | 檢查頻率 | 故障處理 |
|------|----------|----------|----------|
| Systemd | daemon.py 進程 | 持續監控 | 3 秒後重啟整個進程 |
| 內建 Watchdog | Unix socket 連線 | 每 30 秒 | 重建 socket server |

## 常見故障情境

### 情境 1：進程崩潰
- **現象**：daemon.py 完全退出
- **處理**：Systemd 自動重啟（需安裝 systemd service）

### 情境 2：Socket 異常
- **現象**：進程還在但 client 無法連線
- **處理**：內建 watchdog 自動重建 socket

### 情境 3：手動啟動時 socket 異常
- **現象**：`Error: Notification daemon is not running`
- **處理**：重啟 daemon
  ```bash
  pkill -f daemon.py
  ~/Projects/claude-notify-gtk/src/daemon.py &
  ```

# 日誌位置

| 日誌 | 路徑 | 用途 |
|------|------|------|
| Debug log | `log/debug.log` | 詳細運行資訊、health check 結果 |
| Notification log | `log/notifications.log` | Hook 觸發記錄 |
| Systemd journal | `journalctl --user -u claude-notify-gtk` | 進程層級日誌 |

# 故障排查

```bash
# 1. 檢查進程是否運行
pgrep -fa daemon.py

# 2. 檢查 socket 是否存在
ls -la /tmp/claude-notifier.sock

# 3. 測試通知是否正常
echo '{"message": "test"}' | ~/Projects/claude-notify-gtk/src/client.py

# 4. 查看 debug log
tail -50 ~/Projects/claude-notify-gtk/log/debug.log | grep -E "health|Health|error|Error"
```
