---
title: "DISPLAY 環境變數動態偵測"
description: "修復因 DISPLAY 環境變數錯誤導致通知不顯示的問題"
last_modified: "2025-12-26 23:30"
---

# 問題描述

2025-12-26 發現 Stop hook 通知突然無法顯示。經調查發現：

1. Daemon 進程在運行（PID 2960），socket 也存在
2. Hook 腳本正常觸發（log 有記錄）
3. Client 發送資料成功
4. 但通知視窗不顯示

# 根本原因

舊的 daemon 使用 `DISPLAY=:0` 啟動，但實際的 DCV session 是 `DISPLAY=:1`。

```bash
# 實際環境
DISPLAY=:1
XAUTHORITY=/run/user/1000/dcv/ubuntu-session.xauth
```

當 DISPLAY 不匹配時，GTK 無法在正確的顯示器上建立視窗。

# 不同 Linux 桌面環境的 DISPLAY 設定

| 環境 | DISPLAY | XAUTHORITY | 備註 |
|------|---------|------------|------|
| **DCV (Virtual)** | `:1`, `:2`... | `/run/user/UID/dcv/session.xauth` | AWS DCV virtual session |
| **DCV (Console)** | `:0` | 同上 | 連到實體顯示器 |
| **標準 X11** | `:0` | `~/.Xauthority` | 最常見的本地桌面 |
| **Wayland (GNOME)** | 不適用 | 不適用 | 使用 `WAYLAND_DISPLAY` |
| **X11 on Wayland** | `:0` 或 `:1` | 由 XWayland 管理 | 混合模式 |
| **VNC** | `:1`, `:2`... | `~/.Xauthority` 或指定 | 類似 DCV |
| **SSH X forwarding** | `:10`, `:11`... | 自動處理 | 遠端轉發 |

# 解決方案

採用「優先使用現有環境變數，否則用預設值」的策略：

## 修改前（寫死值）

```bash
# hooks/*.sh
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
```

```ini
# systemd service
Environment=DISPLAY=:1
```

## 修改後（動態偵測）

```bash
# hooks/*.sh - 保持現有環境變數優先
# 如果已有 DISPLAY 就不覆蓋，沒有才用預設 :0
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi
# XAUTHORITY 同理
if [ -z "$XAUTHORITY" ]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi
```

```ini
# systemd service - 不寫死 DISPLAY，讓它繼承 session 環境
# 移除 Environment=DISPLAY=:1
# 改用 graphical-session.target 的環境
```

## 核心原則

1. **從登入 session 啟動**：環境變數已正確設定，不需覆蓋
2. **從 cron/systemd 啟動**：使用預設值 `:0` 和 `~/.Xauthority`
3. **從 VSCode Extension 啟動**：繼承 VSCode 的環境變數

# 受影響的檔案

1. `hooks/notification-hook.sh` - 新增 XAUTHORITY fallback
2. `hooks/stop-hook.sh` - 新增 XAUTHORITY fallback
3. `hooks/permission-hook.sh` - 新增 XAUTHORITY fallback
4. `systemd/claude-notify-gtk.service` - 移除寫死的 DISPLAY，改用動態繼承
5. `restart-daemon.sh` - 新增環境變數處理

# 測試方法

```bash
# 1. 重啟 daemon
pkill -f daemon.py
./restart-daemon.sh

# 2. 發送測試通知
echo '{"hook_event_name": "Stop", "message": "Test"}' | ./src/client.py

# 3. 確認通知顯示
```

# 未來排查指引

如果通知再次不顯示：

1. 檢查 daemon 進程的環境變數：
   ```bash
   cat /proc/$(pgrep -f daemon.py)/environ | tr '\0' '\n' | grep DISPLAY
   ```

2. 確認實際的 DISPLAY：
   ```bash
   echo $DISPLAY
   dcv list-sessions  # 如果用 DCV
   ```

3. 測試 X11 連線：
   ```bash
   xdpyinfo | head -5
   ```

4. 手動設定正確環境後啟動 daemon：
   ```bash
   export DISPLAY=:1  # 或正確的值
   export XAUTHORITY=/run/user/$(id -u)/dcv/ubuntu-session.xauth  # DCV 用
   ./src/daemon.py &
   ```
