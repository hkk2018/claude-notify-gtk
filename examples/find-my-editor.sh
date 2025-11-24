#!/bin/bash
# 幫助找出你的編輯器視窗 class name

echo "=== 尋找編輯器視窗 ==="
echo ""

echo "1. 搜尋常見的編輯器視窗..."
echo ""

# 常見的編輯器 window class
EDITORS=(
  "Code"
  "code-oss"
  "VSCodium"
  "Cursor"
  "code-insiders"
  "Code - Insiders"
)

for editor in "${EDITORS[@]}"; do
  result=$(xdotool search --class "$editor" 2>/dev/null)
  if [ -n "$result" ]; then
    echo "✓ 找到: $editor"
    echo "  Window IDs: $result"
    for wid in $result; do
      title=$(xdotool getwindowname "$wid" 2>/dev/null)
      echo "    Title: $title"
    done
    echo ""
  fi
done

echo ""
echo "2. 列出所有視窗（包含 'code' 或 'visual'）..."
echo ""

xdotool search --name "" 2>/dev/null | while read wid; do
  classname=$(xdotool getwindowclassname "$wid" 2>/dev/null)
  title=$(xdotool getwindowname "$wid" 2>/dev/null)

  if echo "$classname $title" | grep -qi "code\|visual\|cursor"; then
    echo "Window ID: $wid"
    echo "  Class: $classname"
    echo "  Title: $title"
    echo ""
  fi
done

echo ""
echo "3. 建議的設定："
echo ""
echo "如果找到了你的編輯器，編輯設定檔："
echo "  nano ~/.config/claude-notify-gtk/focus-mapping.json"
echo ""
echo "範例設定："
echo '{'
echo '  "projects": {'
echo '    "/home/ubuntu/Projects/claude-notify-gtk": {'
echo '      "type": "vscode",'
echo '      "window_class": "你找到的class名稱"'
echo '    }'
echo '  },'
echo '  "default": {'
echo '    "type": "vscode",'
echo '    "window_class": "你找到的class名稱"'
echo '  }'
echo '}'
