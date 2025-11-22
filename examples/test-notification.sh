#!/bin/bash
# Test script for claude-notify-gtk

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT="$SCRIPT_DIR/src/client.py"

echo "Testing claude-notify-gtk notification system..."
echo ""

# Test 1: Basic notification
echo "[Test 1] Basic notification"
echo '{
  "cwd": "/home/user/test-project",
  "message": "This is a basic test notification",
  "session_id": "test-123"
}' | "$CLIENT"
sleep 2

# Test 2: Permission prompt (critical)
echo "[Test 2] Permission prompt (critical)"
echo '{
  "cwd": "/home/user/test-project",
  "message": "Permission required to access system resources",
  "notification_type": "permission_prompt",
  "session_id": "test-456"
}' | "$CLIENT"
sleep 2

# Test 3: Idle prompt (waiting)
echo "[Test 3] Idle prompt (waiting for input)"
echo '{
  "cwd": "/home/user/test-project",
  "message": "Waiting for your input to continue",
  "notification_type": "idle_prompt",
  "session_id": "test-789"
}' | "$CLIENT"
sleep 2

# Test 4: Auth success
echo "[Test 4] Authentication success"
echo '{
  "cwd": "/home/user/test-project",
  "message": "Successfully authenticated with API",
  "notification_type": "auth_success",
  "session_id": "test-abc"
}' | "$CLIENT"
sleep 2

# Test 5: Error notification
echo "[Test 5] Error notification"
echo '{
  "cwd": "/home/user/test-project",
  "message": "Error: Failed to compile project due to syntax error",
  "session_id": "test-def"
}' | "$CLIENT"
sleep 2

# Test 6: Completion notification
echo "[Test 6] Task completion"
echo '{
  "cwd": "/home/user/test-project",
  "message": "Successfully completed build and deployment",
  "session_id": "test-ghi"
}' | "$CLIENT"

echo ""
echo "Test complete! Check the notification window for results."
echo "The window should display 6 notifications with different styles and sounds."
