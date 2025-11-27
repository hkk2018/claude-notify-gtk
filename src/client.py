#!/usr/bin/env python3
"""
Claude Code 通知發送客戶端
- 連接到守護程式的 Unix socket
- 發送通知資料
"""

import socket
import sys
import json

SOCKET_PATH = "/tmp/claude-notifier.sock"


def send_notification(hook_data):
    """發送通知到守護程式"""
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps(hook_data).encode('utf-8'))
        client.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        # 守護程式未運行
        import os
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print("Error: Notification daemon is not running", file=sys.stderr)
        print(f"Please start: {script_dir}/src/daemon.py &", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error sending notification: {e}", file=sys.stderr)
        return False


def main():
    """主程式"""
    # 從 stdin 讀取 hook 資料
    try:
        hook_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        hook_data = {"message": "Invalid JSON data"}

    send_notification(hook_data)


if __name__ == "__main__":
    main()
