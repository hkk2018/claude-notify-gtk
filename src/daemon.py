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
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf
import json
import datetime
import subprocess
import os
import socket
import threading
from pathlib import Path

SOCKET_PATH = "/tmp/claude-notifier.sock"
CONFIG_DIR = Path.home() / ".config" / "claude-notify-gtk"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 預設設定
DEFAULT_CONFIG = {
    "window": {
        "width": 400,
        "height": 600,
        "min_width": 300,
        "min_height": 400,
        "resizable": True,
        "position": "top-right",
        "remember_position": True,
        "remember_size": True
    },
    "appearance": {
        "opacity": 0.95,
        "font_family": "Sans",
        "font_size_title": 13,
        "font_size_body": 11,
        "card_border_radius": 3,
        "card_border_width": 2
    },
    "behavior": {
        "sound_enabled": True,
        "auto_hide_empty": False,
        "max_notifications": 50,
        "scroll_to_newest": True
    },
    "notification_content": {
        "show_timestamp": True,
        "show_full_path": False,
        "show_session_id": True,
        "time_format": "%Y-%m-%d %H:%M:%S"
    }
}

def load_config():
    """載入設定檔，如果不存在則創建預設設定"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            # 合併使用者設定和預設設定（深度合併）
            config = DEFAULT_CONFIG.copy()
            for section, values in user_config.items():
                if section in config and isinstance(config[section], dict):
                    config[section].update(values)
                else:
                    config[section] = values
            return config
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        # 創建預設設定檔
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"Created default config at: {CONFIG_FILE}")
        return DEFAULT_CONFIG.copy()


class NotificationCard(Gtk.Box):
    """單一通知卡片 (V0 - 原始版本)"""

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
        # 增加訊息內容的 padding，讓文字不要太貼邊框
        message_label.set_margin_start(12)
        message_label.set_margin_end(12)
        message_label.set_margin_top(8)
        message_label.set_margin_bottom(8)

        # 組裝（增加更多 padding 讓內容不要太緊）
        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(16)
        self.set_margin_bottom(16)

        self.pack_start(header, False, False, 0)
        self.pack_start(message_label, True, True, 0)

        # 通知不自動消失，讓使用者手動清除或保留訊息佇列

    def on_close(self, widget=None):
        """關閉通知"""
        if self.on_close_callback:
            self.on_close_callback(self)


class NotificationCardV1(Gtk.Box):
    """通知卡片 V1 - 精簡設計版本"""

    def __init__(self, title, message, urgency="normal", on_close=None, metadata=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.on_close_callback = on_close
        self.urgency = urgency
        metadata = metadata or {}

        # 設定樣式
        if urgency == "critical":
            self.get_style_context().add_class("notification-critical")
        else:
            self.get_style_context().add_class("notification-normal")

        # === Header: icon + type + 時間（右側小字）+ 關閉按鈕 ===
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(12)
        header.set_margin_end(8)
        header.set_margin_top(8)
        header.set_margin_bottom(4)

        # Type 標籤（精簡版標題）
        type_label = Gtk.Label()
        type_label.set_markup(f"<b>{title}</b>")
        type_label.set_halign(Gtk.Align.START)
        type_label.get_style_context().add_class("notification-title")

        # 時間標籤（小字，灰色）
        time_label = Gtk.Label()
        timestamp = metadata.get("timestamp", "")
        time_label.set_markup(f'<span size="small" alpha="70%">{timestamp}</span>')
        time_label.set_halign(Gtk.Align.END)
        time_label.set_hexpand(True)

        # 關閉按鈕
        close_button = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect("clicked", self.on_close)
        close_button.get_style_context().add_class("close-button")

        header.pack_start(type_label, False, False, 0)
        header.pack_start(time_label, True, True, 0)
        header.pack_start(close_button, False, False, 0)

        # === Body: 訊息主體（突出顯示）===
        message_label = Gtk.Label(label=message)
        message_label.set_line_wrap(True)
        message_label.set_halign(Gtk.Align.START)
        message_label.set_valign(Gtk.Align.START)
        message_label.set_xalign(0)
        message_label.set_selectable(True)
        message_label.get_style_context().add_class("notification-body")
        message_label.set_margin_start(12)
        message_label.set_margin_end(12)
        message_label.set_margin_top(4)
        message_label.set_margin_bottom(8)

        # === Footer: Project + Session（小字灰色）===
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.set_margin_start(12)
        footer.set_margin_end(12)
        footer.set_margin_bottom(8)

        footer_parts = []
        if metadata.get("project"):
            footer_parts.append(f'📦 {metadata["project"]}')
        if metadata.get("session"):
            footer_parts.append(f'Session: {metadata["session"]}')

        if footer_parts:
            footer_label = Gtk.Label()
            footer_text = " • ".join(footer_parts)
            footer_label.set_markup(f'<span size="small" alpha="60%">{footer_text}</span>')
            footer_label.set_halign(Gtk.Align.START)
            footer_label.set_ellipsize(3)  # 過長時省略
            footer.pack_start(footer_label, True, True, 0)

        # 組裝
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self.pack_start(header, False, False, 0)
        self.pack_start(message_label, True, True, 0)
        if footer_parts:
            self.pack_start(footer, False, False, 0)

    def on_close(self, widget=None):
        """關閉通知"""
        if self.on_close_callback:
            self.on_close_callback(self)


class NotificationCardV2(Gtk.Box):
    """通知卡片 V2 - 完整資訊版本（使用所有可用欄位）"""

    def __init__(self, title, message, urgency="normal", on_close=None, metadata=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.on_close_callback = on_close
        self.urgency = urgency
        metadata = metadata or {}

        # 設定樣式
        if urgency == "critical":
            self.get_style_context().add_class("notification-critical")
        else:
            self.get_style_context().add_class("notification-normal")

        # === Header: icon + type + 時間（右側，精簡格式）+ 關閉按鈕 ===
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(12)
        header.set_margin_end(8)
        header.set_margin_top(8)
        header.set_margin_bottom(4)

        # Type 標籤
        type_label = Gtk.Label()
        type_label.set_markup(f"<b>{title}</b>")
        type_label.set_halign(Gtk.Align.START)
        type_label.get_style_context().add_class("notification-title")

        # 時間標籤（只顯示時:分，完整時間在 tooltip）
        time_label = Gtk.Label()
        timestamp = metadata.get("timestamp", "")
        if timestamp:
            time_only = timestamp.split(" ")[1][:5] if " " in timestamp else timestamp[:5]
            time_label.set_markup(f'<span size="small" alpha="70%">{time_only}</span>')
            time_label.set_tooltip_text(f'Full time: {timestamp}')
        time_label.set_halign(Gtk.Align.END)
        time_label.set_hexpand(True)

        # 關閉按鈕
        close_button = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect("clicked", self.on_close)
        close_button.get_style_context().add_class("close-button")

        header.pack_start(type_label, False, False, 0)
        header.pack_start(time_label, True, True, 0)
        header.pack_start(close_button, False, False, 0)

        # === Body: 訊息主體 ===
        message_label = Gtk.Label(label=message)
        message_label.set_line_wrap(True)
        message_label.set_halign(Gtk.Align.START)
        message_label.set_valign(Gtk.Align.START)
        message_label.set_xalign(0)
        message_label.set_selectable(True)
        message_label.get_style_context().add_class("notification-body")
        message_label.set_margin_start(12)
        message_label.set_margin_end(12)
        message_label.set_margin_top(4)
        message_label.set_margin_bottom(6)

        # === Footer: 完整資訊（緊湊排列）===
        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        footer.set_margin_start(12)
        footer.set_margin_end(12)
        footer.set_margin_bottom(8)

        # 第一行：Project + Hook Event（如果有）
        line1_parts = []
        if metadata.get("project"):
            line1_parts.append(f'📦 {metadata["project"]}')
        if metadata.get("hook_event"):
            line1_parts.append(f'⚡ {metadata["hook_event"]}')

        if line1_parts:
            line1_label = Gtk.Label()
            line1_label.set_markup(f'<span size="small" alpha="60%">{" • ".join(line1_parts)}</span>')
            line1_label.set_halign(Gtk.Align.START)
            line1_label.set_ellipsize(3)
            footer.pack_start(line1_label, False, False, 0)

        # 第二行：Session（縮短顯示，完整ID在tooltip）
        if metadata.get("session"):
            session_label = Gtk.Label()
            session_short = metadata["session"][:8]
            session_label.set_markup(f'<span size="small" alpha="50%">🔑 {session_short}...</span>')
            session_label.set_halign(Gtk.Align.START)
            session_label.set_tooltip_text(f'Session ID: {metadata["session"]}')
            footer.pack_start(session_label, False, False, 0)

        # 第三行：Transcript（只顯示檔名）
        if metadata.get("transcript"):
            transcript_label = Gtk.Label()
            transcript_file = metadata["transcript"].split("/")[-1]
            if len(transcript_file) > 25:
                transcript_file = transcript_file[:22] + "..."
            transcript_label.set_markup(f'<span size="x-small" alpha="40%">📄 {transcript_file}</span>')
            transcript_label.set_halign(Gtk.Align.START)
            transcript_label.set_tooltip_text(metadata["transcript"])
            footer.pack_start(transcript_label, False, False, 0)

        # 組裝
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self.pack_start(header, False, False, 0)
        self.pack_start(message_label, True, True, 0)
        if line1_parts or metadata.get("session") or metadata.get("transcript"):
            self.pack_start(footer, False, False, 0)

    def on_close(self, widget=None):
        """關閉通知"""
        if self.on_close_callback:
            self.on_close_callback(self)


class NotificationCardV3(Gtk.Box):
    """通知卡片 V3 - 優化版面配置"""

    def __init__(self, title, message, urgency="normal", on_close=None, metadata=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.on_close_callback = on_close
        self.urgency = urgency
        metadata = metadata or {}

        # 設定樣式
        if urgency == "critical":
            self.get_style_context().add_class("notification-critical")
        else:
            self.get_style_context().add_class("notification-normal")

        # === Header: Icon + Project + 關閉按鈕 ===
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header.set_margin_start(12)
        header.set_margin_end(8)
        header.set_margin_top(8)
        header.set_margin_bottom(4)

        # Icon
        icon = metadata.get("icon", "💬")
        icon_label = Gtk.Label()
        icon_label.set_markup(f"{icon}")
        icon_label.set_halign(Gtk.Align.START)

        # 專案名稱
        project_name = metadata.get("project", "")
        project_label = Gtk.Label()
        project_label.set_markup(f"<b>{project_name}</b>")
        project_label.set_halign(Gtk.Align.START)
        project_label.set_hexpand(True)
        project_label.set_ellipsize(3)  # 過長時省略
        project_label.set_max_width_chars(30)  # 限制最大寬度
        project_label.get_style_context().add_class("notification-title")

        # 關閉按鈕
        close_button = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect("clicked", self.on_close)
        close_button.get_style_context().add_class("close-button")

        header.pack_start(icon_label, False, False, 0)
        header.pack_start(project_label, True, True, 0)
        header.pack_start(close_button, False, False, 0)

        # === Body: 訊息主體 ===
        message_label = Gtk.Label(label=message)
        message_label.set_line_wrap(True)
        message_label.set_halign(Gtk.Align.START)
        message_label.set_valign(Gtk.Align.START)
        message_label.set_xalign(0)
        message_label.set_selectable(True)
        message_label.get_style_context().add_class("notification-body")
        message_label.set_margin_start(12)
        message_label.set_margin_end(12)
        message_label.set_margin_top(4)
        message_label.set_margin_bottom(6)

        # === Footer: Session + Transcript（左側）+ Event at Time（右側）===
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        footer.set_margin_start(12)
        footer.set_margin_end(12)
        footer.set_margin_bottom(8)

        # 左側：Session + Transcript（垂直排列）
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        # Session（有文字標示）
        if metadata.get("session"):
            session_label = Gtk.Label()
            session_short = metadata["session"][:8]
            session_label.set_markup(f'<span size="small" alpha="70%">Session: {session_short}...</span>')
            session_label.set_halign(Gtk.Align.START)
            session_label.set_tooltip_text(f'Full Session ID: {metadata["session"]}')
            left_box.pack_start(session_label, False, False, 0)

        # Transcript（有文字標示）
        if metadata.get("transcript"):
            transcript_label = Gtk.Label()
            transcript_file = metadata["transcript"].split("/")[-1]
            if len(transcript_file) > 20:
                transcript_file = transcript_file[:17] + "..."
            transcript_label.set_markup(f'<span size="x-small" alpha="70%">Transcript: {transcript_file}</span>')
            transcript_label.set_halign(Gtk.Align.START)
            transcript_label.set_tooltip_text(f'Full path: {metadata["transcript"]}')
            left_box.pack_start(transcript_label, False, False, 0)

        # 右側：Event at Time
        event_name = metadata.get("event_name", "")
        timestamp = metadata.get("timestamp", "")
        event_time_label = Gtk.Label()
        if timestamp:
            time_only = timestamp.split(" ")[1][:5] if " " in timestamp else timestamp[:5]
            event_time_text = f"{event_name} at {time_only}"
        else:
            event_time_text = event_name
        event_time_label.set_markup(f'<span size="small" alpha="70%">{event_time_text}</span>')
        event_time_label.set_halign(Gtk.Align.END)
        event_time_label.set_valign(Gtk.Align.END)
        event_time_label.set_tooltip_text(f'Full time: {timestamp}' if timestamp else '')

        footer.pack_start(left_box, False, False, 0)
        footer.pack_end(event_time_label, False, False, 0)

        # 組裝
        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self.pack_start(header, False, False, 0)
        self.pack_start(message_label, True, True, 0)
        # Footer 總是顯示（至少有 event at time）
        self.pack_start(footer, False, False, 0)

    def on_close(self, widget=None):
        """關閉通知"""
        if self.on_close_callback:
            self.on_close_callback(self)


class SettingsDialog(Gtk.Dialog):
    """設定對話框"""

    def __init__(self, parent, config):
        super().__init__(title="Settings", transient_for=parent, flags=0)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.parent = parent  # 保存父視窗引用，用於即時預覽
        self.config = config
        self.original_config = json.loads(json.dumps(config))  # 深拷貝原始設定
        self.set_default_size(450, 400)
        self.set_border_width(10)

        # 加入 "Reset to Default" 按鈕（放在左側）
        reset_button = Gtk.Button(label="Reset to Default")
        reset_button.connect("clicked", self.on_reset_to_default)
        action_area = self.get_action_area()
        action_area.pack_start(reset_button, False, False, 0)
        action_area.set_child_secondary(reset_button, True)  # 放在左側

        # 創建內容區域
        box = self.get_content_area()
        box.set_spacing(12)

        # 使用 Notebook 分頁管理不同類別的設定
        notebook = Gtk.Notebook()
        box.pack_start(notebook, True, True, 0)

        # 頁面1: 外觀設定
        appearance_page = self.create_appearance_page()
        notebook.append_page(appearance_page, Gtk.Label(label="Appearance"))

        # 頁面2: 視窗設定
        window_page = self.create_window_page()
        notebook.append_page(window_page, Gtk.Label(label="Window"))

        # 頁面3: 行為設定
        behavior_page = self.create_behavior_page()
        notebook.append_page(behavior_page, Gtk.Label(label="Behavior"))

        # 連接信號以實現即時預覽
        self.connect_preview_signals()

        self.show_all()

    def create_appearance_page(self):
        """創建外觀設定頁面"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)
        grid.set_border_width(12)

        row = 0

        # 透明度調整
        label = Gtk.Label(label="Opacity:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        opacity_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 1.0, 0.05)
        opacity_scale.set_value(self.config["appearance"]["opacity"])
        opacity_scale.set_hexpand(True)
        opacity_scale.set_value_pos(Gtk.PositionType.RIGHT)
        opacity_scale.set_digits(2)
        grid.attach(opacity_scale, 1, row, 2, 1)
        self.opacity_scale = opacity_scale
        row += 1

        # 標題字體大小
        label = Gtk.Label(label="Title Font Size:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        title_font_spin = Gtk.SpinButton()
        title_font_spin.set_range(8, 24)
        title_font_spin.set_increments(1, 2)
        title_font_spin.set_value(self.config["appearance"]["font_size_title"])
        grid.attach(title_font_spin, 1, row, 1, 1)
        self.title_font_spin = title_font_spin
        row += 1

        # 內容字體大小
        label = Gtk.Label(label="Body Font Size:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        body_font_spin = Gtk.SpinButton()
        body_font_spin.set_range(8, 20)
        body_font_spin.set_increments(1, 2)
        body_font_spin.set_value(self.config["appearance"]["font_size_body"])
        grid.attach(body_font_spin, 1, row, 1, 1)
        self.body_font_spin = body_font_spin
        row += 1

        # 卡片圓角
        label = Gtk.Label(label="Card Border Radius:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        radius_spin = Gtk.SpinButton()
        radius_spin.set_range(0, 20)
        radius_spin.set_increments(1, 2)
        radius_spin.set_value(self.config["appearance"]["card_border_radius"])
        grid.attach(radius_spin, 1, row, 1, 1)
        self.radius_spin = radius_spin
        row += 1

        return grid

    def create_window_page(self):
        """創建視窗設定頁面"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)
        grid.set_border_width(12)

        row = 0

        # 視窗寬度
        label = Gtk.Label(label="Window Width:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        width_spin = Gtk.SpinButton()
        width_spin.set_range(300, 800)
        width_spin.set_increments(10, 50)
        width_spin.set_value(self.config["window"]["width"])
        grid.attach(width_spin, 1, row, 1, 1)
        self.width_spin = width_spin
        row += 1

        # 視窗高度
        label = Gtk.Label(label="Window Height:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        height_spin = Gtk.SpinButton()
        height_spin.set_range(400, 1200)
        height_spin.set_increments(10, 50)
        height_spin.set_value(self.config["window"]["height"])
        grid.attach(height_spin, 1, row, 1, 1)
        self.height_spin = height_spin
        row += 1

        return grid

    def create_behavior_page(self):
        """創建行為設定頁面"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)
        grid.set_border_width(12)

        row = 0

        # 音效開關
        label = Gtk.Label(label="Enable Sound:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        sound_switch = Gtk.Switch()
        sound_switch.set_active(self.config["behavior"]["sound_enabled"])
        sound_switch.set_halign(Gtk.Align.START)  # 靠左對齊，不擴展
        grid.attach(sound_switch, 1, row, 1, 1)
        self.sound_switch = sound_switch
        row += 1

        # 最大通知數量
        label = Gtk.Label(label="Max Notifications:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        max_notif_spin = Gtk.SpinButton()
        max_notif_spin.set_range(10, 100)
        max_notif_spin.set_increments(5, 10)
        max_notif_spin.set_value(self.config["behavior"]["max_notifications"])
        grid.attach(max_notif_spin, 1, row, 1, 1)
        self.max_notif_spin = max_notif_spin
        row += 1

        return grid

    def get_updated_config(self):
        """獲取更新後的設定"""
        config = self.config.copy()

        # 更新外觀設定
        config["appearance"]["opacity"] = self.opacity_scale.get_value()
        config["appearance"]["font_size_title"] = int(self.title_font_spin.get_value())
        config["appearance"]["font_size_body"] = int(self.body_font_spin.get_value())
        config["appearance"]["card_border_radius"] = int(self.radius_spin.get_value())

        # 更新視窗設定
        config["window"]["width"] = int(self.width_spin.get_value())
        config["window"]["height"] = int(self.height_spin.get_value())

        # 更新行為設定
        config["behavior"]["sound_enabled"] = self.sound_switch.get_active()
        config["behavior"]["max_notifications"] = int(self.max_notif_spin.get_value())

        return config

    def connect_preview_signals(self):
        """連接控件信號以實現即時預覽"""
        # 透明度滑桿
        self.opacity_scale.connect("value-changed", self.on_preview_change)
        # 字體大小
        self.title_font_spin.connect("value-changed", self.on_preview_change)
        self.body_font_spin.connect("value-changed", self.on_preview_change)
        # 卡片圓角
        self.radius_spin.connect("value-changed", self.on_preview_change)
        # 視窗大小
        self.width_spin.connect("value-changed", self.on_preview_change)
        self.height_spin.connect("value-changed", self.on_preview_change)

    def on_preview_change(self, widget):
        """當設定改變時，即時預覽效果"""
        # 獲取當前設定值
        opacity = self.opacity_scale.get_value()
        font_size_title = int(self.title_font_spin.get_value())
        font_size_body = int(self.body_font_spin.get_value())
        card_border_radius = int(self.radius_spin.get_value())
        width = int(self.width_spin.get_value())
        height = int(self.height_spin.get_value())

        # 應用到父視窗
        self.parent.opacity = opacity

        # 更新暫時的設定（用於重新生成 CSS）
        self.parent.config["appearance"]["opacity"] = opacity
        self.parent.config["appearance"]["font_size_title"] = font_size_title
        self.parent.config["appearance"]["font_size_body"] = font_size_body
        self.parent.config["appearance"]["card_border_radius"] = card_border_radius
        self.parent.config["window"]["width"] = width
        self.parent.config["window"]["height"] = height

        # 調整視窗大小
        self.parent.resize(width, height)

        # 重新應用樣式（CSS 中包含 opacity）
        self.parent.apply_styles()

    def restore_original_settings(self):
        """恢復原始設定"""
        # 恢復父視窗的設定
        self.parent.config = json.loads(json.dumps(self.original_config))
        self.parent.opacity = self.original_config["appearance"]["opacity"]

        # 恢復視窗大小
        orig_width = self.original_config["window"]["width"]
        orig_height = self.original_config["window"]["height"]
        self.parent.resize(orig_width, orig_height)

        # 重新應用樣式（CSS 中包含 opacity）
        self.parent.apply_styles()

    def on_reset_to_default(self, button):
        """重置所有設定為預設值"""
        # 更新所有控件的值為預設值
        self.opacity_scale.set_value(DEFAULT_CONFIG["appearance"]["opacity"])
        self.title_font_spin.set_value(DEFAULT_CONFIG["appearance"]["font_size_title"])
        self.body_font_spin.set_value(DEFAULT_CONFIG["appearance"]["font_size_body"])
        self.radius_spin.set_value(DEFAULT_CONFIG["appearance"]["card_border_radius"])
        self.width_spin.set_value(DEFAULT_CONFIG["window"]["width"])
        self.height_spin.set_value(DEFAULT_CONFIG["window"]["height"])
        self.sound_switch.set_active(DEFAULT_CONFIG["behavior"]["sound_enabled"])
        self.max_notif_spin.set_value(DEFAULT_CONFIG["behavior"]["max_notifications"])

        # 控件的 value-changed 信號會自動觸發 on_preview_change，所以不需要手動調用


class NotificationContainer(Gtk.Window):
    """通知容器視窗"""

    def __init__(self):
        super().__init__(title="Claude Code Notifications")

        # 載入設定
        self.config = load_config()

        self.notifications = []
        self.opacity = self.config["appearance"]["opacity"]  # 從設定讀取初始透明度

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

        # 創建系統托盤圖標
        self.create_tray_icon()

    def setup_window(self):
        """設定視窗屬性（從設定檔讀取）"""
        win_config = self.config["window"]

        self.set_decorated(False)  # 無邊框
        self.set_keep_above(True)  # 保持在最上層
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)

        # 視窗大小（從設定讀取）
        self.set_default_size(win_config["width"], win_config["height"])

        # 可調整大小
        self.set_resizable(win_config["resizable"])
        if win_config["resizable"]:
            # 設定最小尺寸
            self.set_size_request(win_config["min_width"], win_config["min_height"])

        # 設定 RGBA visual 以支援透明度
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

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

        # 設定按鈕
        settings_button = Gtk.Button.new_from_icon_name("preferences-system", Gtk.IconSize.BUTTON)
        settings_button.set_relief(Gtk.ReliefStyle.NONE)
        settings_button.set_tooltip_text("Settings")
        settings_button.connect("clicked", self.open_settings_dialog)

        # 清除全部按鈕
        clear_button = Gtk.Button(label="Clear All")
        clear_button.connect("clicked", self.clear_all)
        clear_button.get_style_context().add_class("clear-button")

        # 最小化按鈕
        minimize_button = Gtk.Button.new_from_icon_name("window-minimize", Gtk.IconSize.BUTTON)
        minimize_button.set_relief(Gtk.ReliefStyle.NONE)
        minimize_button.connect("clicked", lambda w: self.hide())

        header.pack_start(title_label, True, True, 0)
        header.pack_start(settings_button, False, False, 0)
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
        """套用 CSS 樣式（從設定讀取字體大小等參數）"""
        app_config = self.config["appearance"]

        # 動態生成 CSS，使用設定的字體大小和透明度
        css = f"""
        window {{
            background-color: rgba(30, 30, 46, 1);
            border: {app_config["card_border_width"]}px solid #89b4fa;
            border-radius: {app_config["card_border_radius"]}px;
            opacity: {app_config["opacity"]};
        }}

        .header {{
            background-color: rgba(17, 17, 27, 0.8);
        }}

        .header:hover {{
            background-color: rgba(17, 17, 27, 0.9);
        }}

        .header-title {{
            font-size: {app_config["font_size_title"]}px;
            font-weight: bold;
            color: #cdd6f4;
        }}

        .opacity-button, .clear-button {{
            font-size: {app_config["font_size_body"] - 1}px;
            padding: 4px 8px;
        }}

        .notification-normal {{
            background-color: rgba(30, 30, 46, 0.9);
            border: 1px solid #89b4fa;
            border-radius: {app_config["card_border_radius"]}px;
            margin: 4px;
        }}

        .notification-critical {{
            background-color: rgba(30, 30, 46, 0.9);
            border: 2px solid #f38ba8;
            border-radius: {app_config["card_border_radius"]}px;
            margin: 4px;
        }}

        .notification-title {{
            font-size: {app_config["font_size_title"]}px;
            font-weight: bold;
            color: #cdd6f4;
        }}

        .notification-critical .notification-title {{
            color: #f38ba8;
        }}

        .notification-body {{
            font-size: {app_config["font_size_body"]}px;
            color: #bac2de;
        }}

        .close-button {{
            min-width: 16px;
            min-height: 16px;
            padding: 2px;
        }}
        """.encode('utf-8')

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)

        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def create_tray_icon(self):
        """創建系統托盤圖標"""
        # 使用 StatusIcon (GTK3)
        self.status_icon = Gtk.StatusIcon()
        self.status_icon.set_from_icon_name("notification-message-im")
        self.status_icon.set_tooltip_text("Claude Code Notifier")
        self.status_icon.set_visible(True)

        # 連接事件
        self.status_icon.connect("activate", self.on_tray_activate)
        self.status_icon.connect("popup-menu", self.on_tray_popup_menu)

    def on_tray_activate(self, status_icon):
        """托盤圖標左鍵點擊 - 切換視窗顯示/隱藏"""
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
            self.present()

    def on_tray_popup_menu(self, status_icon, button, activate_time):
        """托盤圖標右鍵選單"""
        menu = Gtk.Menu()

        # Show/Hide 選項
        show_item = Gtk.MenuItem(label="Show/Hide Window")
        show_item.connect("activate", lambda x: self.on_tray_activate(status_icon))
        menu.append(show_item)

        # 分隔線
        menu.append(Gtk.SeparatorMenuItem())

        # Quit 選項
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        menu.append(quit_item)

        menu.show_all()
        menu.popup(None, None, None, None, button, activate_time)

    def on_quit(self, widget):
        """退出程式"""
        # 關閉 socket
        if hasattr(self, 'socket_path') and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        Gtk.main_quit()

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
        """切換透明度（已棄用，改用設定對話框）"""
        # 這個方法已不再使用，透明度調整移到設定對話框
        pass

    def clear_all(self, widget):
        """清除所有通知"""
        for child in self.notification_box.get_children():
            self.notification_box.remove(child)
        self.notifications.clear()
        self.hide()

    def open_settings_dialog(self, widget):
        """打開設定對話框"""
        dialog = SettingsDialog(self, self.config)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            # 獲取更新後的設定
            new_config = dialog.get_updated_config()

            # 保存設定到檔案
            try:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_config, f, indent=2, ensure_ascii=False)

                # 更新當前設定
                self.config = new_config
                self.opacity = new_config["appearance"]["opacity"]

                # 應用新設定（CSS 中包含 opacity）
                self.apply_styles()

            except Exception as e:
                error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Failed to save settings"
                )
                error_dialog.format_secondary_text(str(e))
                error_dialog.run()
                error_dialog.destroy()
        else:
            # 取消時恢復原始設定
            dialog.restore_original_settings()

        dialog.destroy()

    def add_notification(self, title, message, urgency="normal", sound=None, metadata=None, card_version=3):
        """新增通知

        Args:
            card_version: 0 = V0, 1 = V1, 2 = V2, 3 = V3（優化版面）
        """
        # 播放音效
        if sound:
            self.play_sound(sound)

        # 建立通知卡片（根據版本選擇）
        if card_version == 3:
            card = NotificationCardV3(title, message, urgency, self.remove_notification, metadata)
        elif card_version == 2:
            card = NotificationCardV2(title, message, urgency, self.remove_notification, metadata)
        elif card_version == 1:
            card = NotificationCardV1(title, message, urgency, self.remove_notification, metadata)
        else:
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
        # 讀取所有可用欄位
        cwd = hook_data.get("cwd", "")
        message = hook_data.get("message", "")  # 不設預設值，保持原樣
        notification_type = hook_data.get("notification_type", "")
        session_id = hook_data.get("session_id", "")
        hook_event_name = hook_data.get("hook_event_name", "")
        transcript_path = hook_data.get("transcript_path", "")

        # 專案名稱
        if cwd:
            project_name = cwd.split("/")[-1]
        else:
            project_name = "Claude Code"

        # 時間戳
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 根據通知類型設定標題、緊急程度和音效
        # V0/V1/V2 都使用相同的標題邏輯
        if notification_type == "permission_prompt":
            title_v0 = f"🔐 [{project_name}] Permission"
            title_v1 = "🔐 Permission"
            urgency = "critical"
            sound = "dialog-warning"
        elif notification_type == "idle_prompt":
            title_v0 = f"⏸️  [{project_name}] Waiting"
            title_v1 = "⏸️ Waiting"
            urgency = "critical"
            sound = "dialog-question"
        elif notification_type == "auth_success":
            title_v0 = f"✅ [{project_name}] Auth Success"
            title_v1 = "✅ Auth Success"
            urgency = "normal"
            sound = "complete"
        elif "waiting for your input" in message.lower():
            title_v0 = f"⏸️  [{project_name}] Waiting"
            title_v1 = "⏸️ Waiting"
            urgency = "critical"
            sound = "dialog-question"
        elif any(word in message.lower() for word in ["error", "failed", "exception"]):
            title_v0 = f"❌ [{project_name}] Error"
            title_v1 = "❌ Error"
            urgency = "critical"
            sound = "dialog-error"
        elif any(word in message.lower() for word in ["permission", "approve"]):
            title_v0 = f"🔐 [{project_name}] Permission"
            title_v1 = "🔐 Permission"
            urgency = "critical"
            sound = "dialog-warning"
        else:
            # Fallback: 根據 hook_event_name 判斷 icon
            if hook_event_name:
                # 根據 event 名稱給不同 icon
                event_lower = hook_event_name.lower()
                if "notification" in event_lower:
                    icon = "🔔"
                elif "start" in event_lower or "begin" in event_lower:
                    icon = "▶️"
                elif "stop" in event_lower or "end" in event_lower:
                    icon = "⏹️"
                elif "pause" in event_lower:
                    icon = "⏸️"
                elif "resume" in event_lower:
                    icon = "▶️"
                else:
                    icon = "💬"

                title_v0 = f"{icon} [{project_name}] {hook_event_name}"
                title_v1 = f"{icon} {hook_event_name}"
            else:
                title_v0 = f"💬 [{project_name}] Notification"
                title_v1 = "💬 Notification"
            urgency = "normal"
            sound = "message-new-instant"

        # 組合訊息內容（V0 版本：Session 放在最前面，如果有的話）
        body_lines = []
        if session_id:
            body_lines.append(f"📌 Session: {session_id}")
        body_lines.append(f"🕐 {timestamp}")
        if cwd:
            body_lines.append(f"📁 {cwd}")
        body_lines.append("")  # 空行分隔
        body_lines.append(message if message else "No message")

        body_v0 = "\n".join(body_lines)

        # V1/V2/V3 版本：訊息本體 + 完整 metadata
        body_v1 = message if message else "No message"

        # 從 title_v1 提取 icon 和 event name
        # title_v1 格式: "icon event_name"
        title_parts = title_v1.split(" ", 1)
        event_icon = title_parts[0] if len(title_parts) > 0 else "💬"
        event_name = title_parts[1] if len(title_parts) > 1 else "Notification"

        metadata = {
            "project": project_name,
            "session": session_id,
            "timestamp": timestamp,
            "cwd": cwd,
            "hook_event": hook_event_name,
            "transcript": transcript_path,
            "icon": event_icon,
            "event_name": event_name
        }

        # 新增通知（使用 V3 版本）
        self.add_notification(title_v1, body_v1, urgency, sound, metadata, card_version=3)


def main():
    """主程式"""
    container = NotificationContainer()
    container.show_all()
    container.hide()  # 一開始隱藏，等有通知才顯示

    Gtk.main()


if __name__ == "__main__":
    main()
