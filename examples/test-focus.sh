#!/bin/bash
# 測試 focus 功能的腳本
# 發送通知並測試點擊卡片後 focus 視窗

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Testing focus functionality..."
echo "1. Make sure the daemon is running"
echo "2. Make sure VSCode is open with this project"
echo "3. Click the notification card to test focus"
echo ""

# 發送測試通知
echo '{
  "cwd": "'"$PROJECT_ROOT"'",
  "message": "Click this card to focus back to VSCode!",
  "notification_type": "test",
  "session_id": "test-session-123",
  "hook_event_name": "focus_test",
  "transcript_path": "/tmp/test-transcript.md"
}' | "$PROJECT_ROOT/src/client.py"

echo "Test notification sent. Please click the notification card to test focus."
