---
title: "系統托盤圖標對齊問題修復"
description: "修正 Cinnamon 桌面環境中托盤圖標往下飄移的問題"
last_modified: "2025-12-12 22:33"
---

# 系統托盤圖標對齊問題修復

## 問題描述

在 Cinnamon 桌面環境中，系統托盤圖標與托盤背景的位置分開，圖標往下飄移，沒有正確對齊。

## 根本原因

1. **Symbolic Icon 對齊問題**：原本使用的 `preferences-system-notifications-symbolic` 是 symbolic icon，在某些系統托盤實現（如 Cinnamon）上可能無法正確對齊
2. **缺少明確尺寸**：沒有明確指定圖標大小，讓系統自動處理可能導致對齊問題
3. **圖標類型差異**：不同的桌面環境對 symbolic vs. regular icon 的處理方式不同

## 解決方案

### 1. 創建自訂圖標檔案

在 `assets/icon.png` 創建一個 22x22 的 PNG 圖標：
- 使用標準托盤圖標尺寸（22x22）
- 使用 Catppuccin Mocha Peach 顏色（#fab387）
- 簡單的鈴鐺形狀設計

### 2. 修改圖標載入邏輯

更新 `create_tray_icon()` 方法（src/daemon.py:2340-2399）：

#### 優先級策略
1. **優先使用自訂圖標**：如果 `assets/icon.png` 存在
   - 使用 `GdkPixbuf.Pixbuf.new_from_file_at_scale()` 明確設定 22x22 尺寸
   - 這樣可以確保圖標在托盤中正確對齊
2. **Fallback 到系統圖標**：使用非 symbolic 圖標
   - 優先清單：`notification-message-im`, `notification-new`, `dialog-information`, `mail-unread`, `emblem-important`
   - 非 symbolic 圖標在大部分系統托盤上對齊較好
3. **最終 Fallback**：`application-x-executable`

#### 關鍵改進
```python
# 明確指定尺寸（22x22）
pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
    str(icon_path),
    22, 22,  # 標準托盤圖標尺寸
    True     # preserve aspect ratio
)
self.status_icon.set_from_pixbuf(pixbuf)
```

### 3. 加入 Debug 日誌

- 記錄使用的圖標類型（自訂 vs. 系統圖標）
- 記錄圖標載入失敗的錯誤
- 方便後續問題追蹤

## 測試建議

重啟 daemon 後，應該可以看到：
1. 托盤圖標正確對齊托盤背景
2. Debug log 中顯示 "✅ 使用自訂托盤圖標"
3. 圖標顏色為 Catppuccin Mocha Peach

## 相關檔案

- `src/daemon.py:2340-2399` - `create_tray_icon()` 方法
- `assets/icon.png` - 自訂托盤圖標
- `assets/create_icon.py` - 圖標生成腳本

## 技術筆記

### 為什麼 22x22？
- GNOME HIG（Human Interface Guidelines）建議的標準托盤圖標尺寸
- 大部分系統托盤實現（GNOME、KDE、Cinnamon）都支援這個尺寸
- 太大或太小都可能導致對齊問題

### Symbolic vs. Regular Icon
- **Symbolic Icon**：單色、線條風格，可自動適應主題顏色
  - 優點：自動適應深色/淺色主題
  - 缺點：在某些托盤實現上可能有對齊問題（如 Cinnamon）
- **Regular Icon**：彩色、完整設計
  - 優點：對齊較穩定
  - 缺點：需要手動處理主題適應

### 為什麼不使用 AppIndicator？
- AppIndicator 是針對 Ubuntu Unity/GNOME 的解決方案
- 需要額外依賴（`gir1.2-appindicator3-0.1`）
- `Gtk.StatusIcon` 在大部分環境都可用，更通用
- 未來如果有跨桌面環境的需求，可以考慮切換到 AppIndicator

## 未來改進方向

1. **動態主題適應**：根據系統主題（深色/淺色）調整圖標顏色
2. **高 DPI 支援**：提供不同尺寸的圖標檔案（16x16, 22x22, 32x32）
3. **圖標狀態指示**：根據通知數量改變圖標外觀（如加上數字徽章）
