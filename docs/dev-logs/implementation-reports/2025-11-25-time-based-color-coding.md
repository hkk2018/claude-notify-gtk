---
title: "Time-based Color Coding for Notification Timestamps"
description: "Implementation report for dynamic timestamp color feature"
last_modified: "2025-11-25 14:18"
---

# Time-based Color Coding for Notification Timestamps

## Overview

實現了基於通知時間新舊程度的動態顏色編碼功能，讓用戶能一眼辨識哪些通知是最新的、哪些已經過時。

## User Requirement

用戶希望右下角的時間戳能根據時間的新舊程度使用不同的顏色：
- 5分鐘以內的通知使用鮮豔顏色，讓重要訊息一目了然
- 5-10分鐘的通知使用稍微暗一點的顏色
- 10-20分鐘的通知使用更暗的顏色
- 20分鐘以上的通知保留原本的灰階

## Implementation

### 1. Color Scheme (Catppuccin Mocha)

| Time Range | Color Code | Description |
|------------|------------|-------------|
| ≤ 5 min    | `#a6e3a1`  | 綠色，鮮豔 - 最新通知 |
| 5-10 min   | `#f9e2af`  | 黃色 - 較新通知 |
| 10-20 min  | `#fab387`  | 橙色 - 有點舊的通知 |
| 20+ min    | `#6c7086`  | 灰色 - 舊通知（低調顯示）|

### 2. Code Changes

#### 2.1 Add creation time tracking

[src/daemon.py:704](src/daemon.py#L704)
```python
self.creation_time = datetime.datetime.now()  # 記錄卡片創建時間
```

#### 2.2 Implement color calculation method

[src/daemon.py:846-873](src/daemon.py#L846-L873)
```python
def get_time_color(self, timestamp_str):
    """根據時間差返回對應的顏色"""
    try:
        notification_time = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        time_diff = (self.creation_time - notification_time).total_seconds() / 60

        if time_diff <= 5:
            return "#a6e3a1"  # 綠色
        elif time_diff <= 10:
            return "#f9e2af"  # 黃色
        elif time_diff <= 20:
            return "#fab387"  # 橙色
        else:
            return "#6c7086"  # 灰色
    except Exception:
        return "#6c7086"  # 預設灰色
```

#### 2.3 Apply color to timestamp label

[src/daemon.py:780-795](src/daemon.py#L780-L795)
```python
# 根據時間差獲取顏色
time_color = self.get_time_color(timestamp)

# 使用 foreground 屬性設置顏色
event_time_label.set_markup(f'<span size="small" foreground="{time_color}">{event_time_text}</span>')
```

#### 2.4 Support custom timestamp

[src/daemon.py:1698](src/daemon.py#L1698)
```python
# 優先使用通知中的 timestamp，否則使用當前時間
timestamp = hook_data.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
```

### 3. Testing

創建測試腳本 [test-time-colors.sh](../../test-time-colors.sh) 來模擬不同時間的通知：

```bash
~/Projects/claude-notify-gtk/test-time-colors.sh
```

測試內容：
- 3分鐘前的通知（綠色）
- 7分鐘前的通知（黃色）
- 15分鐘前的通知（橙色）
- 25分鐘前的通知（灰色）

## Design Decisions

### Why Pango `foreground` instead of `alpha`?

- `alpha` 控制透明度，會讓文字變模糊
- `foreground` 直接設置顏色，保持文字清晰度
- 顏色變化比透明度變化更明顯，更容易一眼辨識

### Why these time thresholds?

- **5分鐘**：通常的工作節奏，5分鐘內的通知仍然很重要
- **10分鐘**：超過10分鐘可能已經處理過或暫時不重要
- **20分鐘**：超過20分鐘基本可以歸類為歷史記錄

### Why calculate from `creation_time` instead of `datetime.now()`?

- 卡片創建後顏色固定，不會隨時間變化
- 避免需要定時器更新顏色的複雜性
- 性能更好，不需要持續計算

## UX Benefits

1. **快速辨識優先級**：一眼看出哪些通知最新、最重要
2. **減少認知負擔**：不需要讀取時間數字，顏色就能傳達資訊
3. **視覺層次**：舊通知自動「淡入背景」，不干擾注意力
4. **符合直覺**：綠色→黃色→橙色→灰色的漸變符合一般的警示級別認知

## Future Enhancements

可能的改進方向：

1. **動態更新**：添加定時器讓顏色隨時間動態更新（但會增加複雜度和性能開銷）
2. **可配置閾值**：讓用戶自訂時間閾值和顏色方案
3. **更多視覺提示**：結合字體大小、粗細等其他視覺元素
4. **動畫過渡**：顏色變化時添加平滑過渡動畫

## Related Files

- Implementation: [src/daemon.py](../../src/daemon.py)
- Test script: [test-time-colors.sh](../../test-time-colors.sh)
- User documentation: [README.md](../../README.md)
- Developer guide: [.claude/CLAUDE.md](../../.claude/CLAUDE.md)
