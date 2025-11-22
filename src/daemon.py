#!/usr/bin/env python3
"""
Claude Code 通知守護程式
- 單一容器視窗，固定在右下角
- 支援滾動查看多個通知
- 可調整透明度
- 持續運行，不會每次都新開視窗
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk
import json
import datetime
import subprocess
import os
import socket
import threading

SOCKET_PATH = "/tmp/claude-notifier.sock"


class NotificationCard(Gtk.Box):
    """單一通知卡片"""

    def __init__(self, title, message, urgency="normal", on_close=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self.on_close_callback = on_close
        self.urgency = urgency

        # 設定樣式
        if urgency == "critical":
            self.get_style_context().add_class("notification-critical")
        else:
            self.get_style_context().add_class("notification-normal")

        # 標題列（包含關閉按鈕）
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        title_label = Gtk.Label()
        title_label.set_markup(f"<b>{title}</b>")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        title_label.get_style_context().add_class("notification-title")

        close_button = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect("clicked", self.on_close)
        close_button.get_style_context().add_class("close-button")

        header.pack_start(title_label, True, True, 0)
        header.pack_start(close_button, False, False, 0)

        # 訊息內容
        message_label = Gtk.Label(label=message)
        message_label.set_line_wrap(True)
        message_label.set_halign(Gtk.Align.START)
        message_label.set_valign(Gtk.Align.START)
        message_label.set_xalign(0)
        message_label.set_selectable(True)  # 可選取文字
        message_label.get_style_context().add_class("notification-body")

        # 組裝
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        self.pack_start(header, False, False, 0)
        self.pack_start(message_label, True, True, 0)

        # 30 秒後自動關閉
        GLib.timeout_add_seconds(30, self.auto_close)

    def on_close(self, widget=None):
        """關閉通知"""
        if self.on_close_callback:
            self.on_close_callback(self)

    def auto_close(self):
        """自動關閉"""
        self.on_close()
        return False  # 不重複執行


class NotificationContainer(Gtk.Window):
    """通知容器視窗"""

    def __init__(self):
        super().__init__(title="Claude Code Notifications")

        self.notifications = []
        self.opacity = 0.95  # 預設透明度

        # 拖拉相關變數
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        self.setup_window()
        self.create_ui()
        self.position_window()
        self.apply_styles()

        # 啟動 socket 伺服器
        self.start_socket_server()

    def setup_window(self):
        """設定視窗屬性"""
        self.set_decorated(False)  # 無邊框
        self.set_keep_above(True)  # 保持在最上層
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_default_size(400, 600)
        self.set_opacity(self.opacity)

    def create_ui(self):
        """建立 UI"""
        # 主容器
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # 標題列（用 EventBox 包裝以支援拖拉）
        header_event_box = Gtk.EventBox()
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(12)
        header.set_margin_end(12)
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        header.get_style_context().add_class("header")

        # 設定拖拉事件
        header_event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                                    Gdk.EventMask.BUTTON_RELEASE_MASK |
                                    Gdk.EventMask.POINTER_MOTION_MASK)
        header_event_box.connect("button-press-event", self.on_drag_start)
        header_event_box.connect("button-release-event", self.on_drag_end)
        header_event_box.connect("motion-notify-event", self.on_drag_motion)

        title_label = Gtk.Label(label="Claude Code Notifications")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        title_label.get_style_context().add_class("header-title")

        # 透明度調整按鈕
        opacity_button = Gtk.Button(label=f"{int(self.opacity * 100)}%")
        opacity_button.connect("clicked", self.toggle_opacity)
        opacity_button.get_style_context().add_class("opacity-button")
        self.opacity_button = opacity_button

        # 清除全部按鈕
        clear_button = Gtk.Button(label="Clear All")
        clear_button.connect("clicked", self.clear_all)
        clear_button.get_style_context().add_class("clear-button")

        # 最小化按鈕
        minimize_button = Gtk.Button.new_from_icon_name("window-minimize", Gtk.IconSize.BUTTON)
        minimize_button.set_relief(Gtk.ReliefStyle.NONE)
        minimize_button.connect("clicked", lambda w: self.hide())

        header.pack_start(title_label, True, True, 0)
        header.pack_start(opacity_button, False, False, 0)
        header.pack_start(clear_button, False, False, 0)
        header.pack_start(minimize_button, False, False, 0)

        # 將 header 加入 EventBox
        header_event_box.add(header)

        # 滾動視窗
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)

        # 通知列表容器
        self.notification_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.notification_box.set_margin_start(4)
        self.notification_box.set_margin_end(4)
        self.notification_box.set_margin_top(4)
        self.notification_box.set_margin_bottom(4)

        scrolled.add(self.notification_box)

        # 組裝
        main_box.pack_start(header_event_box, False, False, 0)
        main_box.pack_start(Gtk.Separator(), False, False, 0)
        main_box.pack_start(scrolled, True, True, 0)

        self.add(main_box)

    def position_window(self):
        """定位視窗到右下角"""
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        if monitor is None:
            monitor = display.get_monitor(0)
        geometry = monitor.get_geometry()

        window_width, window_height = self.get_size()

        x = geometry.x + geometry.width - window_width - 10
        y = geometry.y + geometry.height - window_height - 50

        self.move(x, y)

    def apply_styles(self):
        """套用 CSS 樣式"""
        css = b"""
        window {
            background-color: rgba(30, 30, 46, 0.95);
            border: 2px solid #89b4fa;
            border-radius: 8px;
        }

        .header {
            background-color: rgba(17, 17, 27, 0.8);
        }

        .header:hover {
            background-color: rgba(17, 17, 27, 0.9);
        }

        .header-title {
            font-size: 12px;
            font-weight: bold;
            color: #cdd6f4;
        }

        .opacity-button, .clear-button {
            font-size: 10px;
            padding: 4px 8px;
        }

        .notification-normal {
            background-color: rgba(30, 30, 46, 0.9);
            border: 1px solid #89b4fa;
            border-radius: 6px;
            margin: 4px;
        }

        .notification-critical {
            background-color: rgba(30, 30, 46, 0.9);
            border: 2px solid #f38ba8;
            border-radius: 6px;
            margin: 4px;
        }

        .notification-title {
            font-size: 12px;
            font-weight: bold;
            color: #cdd6f4;
        }

        .notification-critical .notification-title {
            color: #f38ba8;
        }

        .notification-body {
            font-size: 10px;
            color: #bac2de;
        }

        .close-button {
            min-width: 16px;
            min-height: 16px;
            padding: 2px;
        }
        """

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)

        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_drag_start(self, widget, event):
        """開始拖拉"""
        if event.button == 1:  # 左鍵
            self.is_dragging = True
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root
            return True
        return False

    def on_drag_end(self, widget, event):
        """結束拖拉"""
        if event.button == 1:
            self.is_dragging = False
            return True
        return False

    def on_drag_motion(self, widget, event):
        """拖拉移動"""
        if self.is_dragging:
            # 計算移動距離
            delta_x = event.x_root - self.drag_start_x
            delta_y = event.y_root - self.drag_start_y

            # 獲取當前視窗位置
            win_x, win_y = self.get_position()

            # 移動視窗
            self.move(int(win_x + delta_x), int(win_y + delta_y))

            # 更新起始位置
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root

            return True
        return False

    def toggle_opacity(self, widget):
        """切換透明度"""
        opacities = [0.95, 0.85, 0.75, 0.65, 1.0]
        current_index = opacities.index(self.opacity) if self.opacity in opacities else 0
        next_index = (current_index + 1) % len(opacities)
        self.opacity = opacities[next_index]
        self.set_opacity(self.opacity)
        self.opacity_button.set_label(f"{int(self.opacity * 100)}%")

    def clear_all(self, widget):
        """清除所有通知"""
        for child in self.notification_box.get_children():
            self.notification_box.remove(child)
        self.notifications.clear()
        self.hide()

    def add_notification(self, title, message, urgency="normal", sound=None):
        """新增通知"""
        # 播放音效
        if sound:
            self.play_sound(sound)

        # 建立通知卡片
        card = NotificationCard(title, message, urgency, self.remove_notification)
        self.notifications.append(card)

        # 加入容器（最新的在最上面）
        self.notification_box.pack_start(card, False, False, 0)
        self.notification_box.reorder_child(card, 0)
        card.show_all()

        # 顯示視窗
        self.show_all()
        self.present()

    def remove_notification(self, card):
        """移除通知"""
        if card in self.notifications:
            self.notifications.remove(card)
        self.notification_box.remove(card)

        # 不自動隱藏視窗，讓使用者自己決定
        # 如果想要自動隱藏，取消下面的註解
        # if not self.notifications:
        #     self.hide()

    @staticmethod
    def play_sound(sound_name):
        """播放音效"""
        sound_files = [
            f"/usr/share/sounds/freedesktop/stereo/{sound_name}.oga",
            f"/usr/share/sounds/freedesktop/stereo/{sound_name}.wav"
        ]

        for sound_file in sound_files:
            if os.path.exists(sound_file):
                if sound_file.endswith(".oga"):
                    subprocess.Popen(["paplay", sound_file],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                elif sound_file.endswith(".wav"):
                    subprocess.Popen(["aplay", sound_file],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                break

    def start_socket_server(self):
        """啟動 Unix socket 伺服器接收通知"""
        def server_thread():
            # 移除舊的 socket
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(SOCKET_PATH)
            server.listen(5)

            while True:
                conn, _ = server.accept()
                try:
                    data = conn.recv(4096).decode('utf-8')
                    if data:
                        notification_data = json.loads(data)
                        GLib.idle_add(self.handle_notification, notification_data)
                finally:
                    conn.close()

        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()

    def handle_notification(self, hook_data):
        """處理通知資料"""
        cwd = hook_data.get("cwd", "")
        message = hook_data.get("message", "Task completed")
        notification_type = hook_data.get("notification_type", "")
        session_id = hook_data.get("session_id", "")

        # 專案名稱
        if cwd:
            project_name = cwd.split("/")[-1]
        else:
            project_name = "Claude Code"

        # 時間戳
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 根據通知類型設定標題、緊急程度和音效
        if notification_type == "permission_prompt":
            title = "🔐 Claude Code - Permission"
            urgency = "critical"
            sound = "dialog-warning"
        elif notification_type == "idle_prompt":
            title = "⏸️  Claude Code - Waiting"
            urgency = "critical"
            sound = "dialog-question"
        elif notification_type == "auth_success":
            title = "✅ Claude Code - Auth Success"
            urgency = "normal"
            sound = "complete"
        elif "waiting for your input" in message.lower():
            title = "⏸️  Claude Code - Waiting"
            urgency = "critical"
            sound = "dialog-question"
        elif any(word in message.lower() for word in ["error", "failed", "exception"]):
            title = "❌ Claude Code - Error"
            urgency = "critical"
            sound = "dialog-error"
        elif any(word in message.lower() for word in ["permission", "approve"]):
            title = "🔐 Claude Code - Permission"
            urgency = "critical"
            sound = "dialog-warning"
        else:
            title = "✅ Claude Code - Completed"
            urgency = "normal"
            sound = "message-new-instant"

        # 組合訊息內容
        body_lines = [f"Project: {project_name}"]
        if session_id:
            body_lines.append(f"Session: {session_id}")
        body_lines.append(f"Time: {timestamp}")
        if cwd:
            body_lines.append(f"Dir: {cwd}")
        body_lines.append("")
        body_lines.append(message)

        body = "\n".join(body_lines)

        # 新增通知
        self.add_notification(title, body, urgency, sound)


def main():
    """主程式"""
    container = NotificationContainer()
    container.show_all()
    container.hide()  # 一開始隱藏，等有通知才顯示

    Gtk.main()


if __name__ == "__main__":
    main()
