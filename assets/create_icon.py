#!/usr/bin/env python3
"""生成一個簡單的托盤圖標"""
from PIL import Image, ImageDraw

# 創建 22x22 的圖標（標準托盤尺寸）
size = 22
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 繪製一個簡單的通知鈴鐺形狀
# 使用 Catppuccin Mocha 的 Peach 顏色: #fab387
color = '#fab387'

# 鈴鐺主體（梯形）
draw.polygon([
    (7, 8),   # 左上
    (15, 8),  # 右上
    (16, 14), # 右下
    (6, 14)   # 左下
], fill=color)

# 鈴鐺頂部（小矩形）
draw.rectangle([10, 5, 12, 8], fill=color)

# 鈴鐺底部小點（舌頭）
draw.ellipse([9, 14, 13, 18], fill=color)

# 儲存為 PNG
img.save('icon.png')
print("✅ 圖標已生成: icon.png")
