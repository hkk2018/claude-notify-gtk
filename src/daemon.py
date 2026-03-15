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
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, AppIndicator3
import json
import datetime
import subprocess
import sys
import os
import socket
import threading
from pathlib import Path

# ===== DEBUG MODE =====
# 設定為 True 時會記錄詳細的 debug 資訊
# Local 開發時開啟，上線時設為 False
DEBUG_MODE = True

SOCKET_PATH = "/tmp/claude-notifier.sock"
CONFIG_DIR = Path.home() / ".config" / "claude-notify-gtk"
CONFIG_FILE = CONFIG_DIR / "config.json"
FOCUS_MAPPING_FILE = CONFIG_DIR / "focus-mapping.json"

# Debug log 目錄
PROJECT_ROOT = Path(__file__).parent.parent
DEBUG_LOG_DIR = PROJECT_ROOT / "log"
DEBUG_LOG_FILE = DEBUG_LOG_DIR / "debug.log"
CRASH_LOG_FILE = DEBUG_LOG_DIR / "crash.log"


def debug_log(message, data=None):
    """記錄 debug 資訊到檔案

    Args:
        message: 日誌訊息
        data: 要記錄的資料（dict 或其他可序列化的資料）
    """
    if not DEBUG_MODE:
        return

    try:
        # 確保 log 目錄存在
        DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 檢查檔案大小，超過限制就輪替
        MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
        if DEBUG_LOG_FILE.exists() and DEBUG_LOG_FILE.stat().st_size > MAX_LOG_SIZE:
            # 輪替：保留最近一個備份
            backup_file = DEBUG_LOG_FILE.with_suffix('.log.1')
            if backup_file.exists():
                backup_file.unlink()
            DEBUG_LOG_FILE.rename(backup_file)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{timestamp}] {message}\n")

            if data is not None:
                if isinstance(data, dict):
                    f.write(json.dumps(data, indent=2, ensure_ascii=False))
                else:
                    f.write(str(data))
                f.write("\n")

            f.write(f"{'='*80}\n")

    except Exception as e:
        # Debug log 失敗不應該影響主程式運行
        print(f"Debug log error: {e}", file=sys.stderr)


def extract_last_messages_from_transcript(transcript_path, head_lines=5, tail_lines=5):
    """從 transcript 文件提取最後一條 assistant 回覆

    Claude Code 的 transcript 是 .jsonl 格式（JSON Lines），每行一個 JSON 物件。
    只提取最後一條 assistant 訊息，顯示前 N 行 + ... + 後 N 行。

    優化：只讀取檔案最後 N 行，避免大檔案阻塞 UI。

    Args:
        transcript_path: transcript 文件路徑（.jsonl 格式）
        head_lines: 顯示開頭幾行（預設 5）
        tail_lines: 顯示結尾幾行（預設 5）

    Returns:
        str: 格式化的訊息文字，如果失敗返回 None
    """
    try:
        debug_log("📂 開始讀取 transcript 檔案", {
            "路徑": transcript_path,
            "head_lines": head_lines,
            "tail_lines": tail_lines,
            "檔案存在": os.path.exists(transcript_path) if transcript_path else False
        })

        if not transcript_path or not os.path.exists(transcript_path):
            debug_log("❌ Transcript 檔案不存在或路徑為空")
            return None

        # 檢查檔案大小，決定讀取策略
        file_size = os.path.getsize(transcript_path)
        MAX_READ_SIZE = 512 * 1024  # 512KB - 只讀取最後這麼多

        debug_log("📊 檔案大小檢查", {
            "檔案大小": file_size,
            "最大讀取": MAX_READ_SIZE,
            "需要截斷": file_size > MAX_READ_SIZE
        })

        # 讀取 .jsonl 檔案，只保留 assistant 訊息
        # 優化：大檔案只讀取尾部
        assistant_messages = []

        if file_size > MAX_READ_SIZE:
            # 大檔案：只讀取最後 512KB
            with open(transcript_path, 'rb') as f:
                f.seek(-MAX_READ_SIZE, 2)  # 從檔尾往前 seek
                # 跳過可能被截斷的第一行
                f.readline()
                # 讀取剩餘內容
                content = f.read().decode('utf-8', errors='ignore')

            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get('type') == 'assistant':
                        assistant_messages.append(entry)
                except json.JSONDecodeError:
                    continue
        else:
            # 小檔案：正常讀取
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get('type') == 'assistant':
                            assistant_messages.append(entry)
                    except json.JSONDecodeError:
                        continue

        debug_log("📨 Transcript JSONL 解析結果", {
            "assistant 訊息數": len(assistant_messages),
            "類型": "JSONL (JSON Lines)",
            "讀取模式": "tail" if file_size > MAX_READ_SIZE else "full"
        })

        if not assistant_messages:
            debug_log("⚠️ Transcript 中沒有 assistant 訊息")
            return None

        # 取最後一條 assistant 訊息
        last_entry = assistant_messages[-1]
        msg = last_entry.get('message', {})
        content = msg.get('content', '')

        # 提取文字內容（content 通常是陣列）
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
            content = '\n'.join(text_parts)

        debug_log("📝 最後 assistant 訊息", {
            "content 長度": len(content)
        })

        if not content:
            return None

        # 按行分割
        lines = content.strip().split('\n')
        total_lines = len(lines)

        # 如果行數不多，直接顯示全部
        if total_lines <= head_lines + tail_lines + 2:
            result = content.strip()
        else:
            # 前 N 行 + ... + 後 N 行
            head_part = '\n'.join(lines[:head_lines])
            tail_part = '\n'.join(lines[-tail_lines:])
            omitted = total_lines - head_lines - tail_lines
            result = f"{head_part}\n\n... ({omitted} lines omitted) ...\n\n{tail_part}"

        debug_log("✅ Transcript 內容提取成功", {
            "總行數": total_lines,
            "結果長度": len(result)
        })
        return result

    except Exception as e:
        debug_log("❌ 讀取 transcript 失敗", {
            "錯誤訊息": str(e),
            "錯誤類型": type(e).__name__
        })
        return None

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
        "scroll_to_newest": True,
        "shortcut_max_chars": 10,
        "transcript_head_lines": 5,
        "transcript_tail_lines": 5
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


class FocusManager:
    """管理視窗 focus 的類別

    - 載入 focus-mapping.json 設定檔
    - 根據專案路徑查找對應的 focus 設定
    - 執行 focus 操作（內建編輯器或自訂指令）
    """

    # 預設 focus mapping 設定
    DEFAULT_FOCUS_MAPPING = {
        "projects": {},
        "default": {
            "type": "vscode"
        },
        "builtin_editors": {
            "vscode": {
                "window_title": "Visual Studio Code",
                "window_class": "Code"
            },
            "cursor": {
                "window_title": "Cursor",
                "window_class": "Cursor"
            }
        }
    }

    def __init__(self):
        """初始化 FocusManager"""
        self.mapping = self.load_focus_mapping()
        self.log_file = CONFIG_DIR / "focus-errors.log"
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._display = None  # 重用 Xlib Display 連線，避免 fd 洩漏
        self._display_lock = threading.Lock()  # Xlib Display 非 thread-safe，需要 lock

    def load_focus_mapping(self):
        """載入 focus mapping 設定檔"""
        if FOCUS_MAPPING_FILE.exists():
            try:
                with open(FOCUS_MAPPING_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load focus mapping: {e}")
                return self.DEFAULT_FOCUS_MAPPING.copy()
        else:
            # 創建預設設定檔
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(FOCUS_MAPPING_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.DEFAULT_FOCUS_MAPPING, f, indent=2, ensure_ascii=False)
            print(f"Created default focus mapping at: {FOCUS_MAPPING_FILE}")
            return self.DEFAULT_FOCUS_MAPPING.copy()

    def _get_display(self):
        """取得可重用的 Xlib Display 連線

        避免每次 focus 操作都開新連線造成 fd 洩漏。
        如果連線失效會自動重建。
        呼叫者必須持有 self._display_lock（python-xlib Display 非 thread-safe）。

        Returns:
            Xlib Display 物件
        """
        from Xlib import display as xlib_display

        env_display = os.environ.get("DISPLAY", ":1")

        if self._display is not None:
            try:
                # 測試連線是否仍有效
                self._display.get_display_name()
                return self._display
            except Exception:
                # 連線失效，關閉後重建
                try:
                    self._display.close()
                except Exception:
                    pass
                self._display = None

        self._display = xlib_display.Display(env_display)
        return self._display

    def get_focus_config(self, project_path):
        """根據專案路徑取得 focus 設定

        Args:
            project_path: 專案路徑（來自通知的 cwd）

        Returns:
            focus 設定字典
        """
        # 查找專案特定設定
        projects = self.mapping.get("projects", {})
        if project_path in projects:
            return projects[project_path]

        # 使用預設設定
        return self.mapping.get("default", {"type": "vscode"})

    def focus_window(self, notification_data):
        """執行視窗 focus 操作

        Args:
            notification_data: 完整的通知資料字典

        Returns:
            True if successful, False otherwise
        """
        cwd = notification_data.get("cwd", "")
        if not cwd:
            self.log_error("No cwd in notification data")
            return False

        # 取得 focus 設定
        focus_config = self.get_focus_config(cwd)
        focus_type = focus_config.get("type", "vscode")

        try:
            if focus_type == "custom":
                return self.execute_custom_command(focus_config, notification_data)
            else:
                return self.focus_builtin_editor(focus_type, focus_config, notification_data)
        except Exception as e:
            self.log_error(f"Failed to focus window: {e}")
            return False

    def focus_builtin_editor(self, editor_type, focus_config, notification_data=None):
        """Focus 內建編輯器視窗

        Args:
            editor_type: 編輯器類型（vscode, cursor, 等）
            focus_config: focus 設定字典

        Returns:
            True if successful, False otherwise
        """
        # 取得內建編輯器的預設設定
        builtin_editors = self.mapping.get("builtin_editors", {})
        editor_defaults = builtin_editors.get(editor_type, {})

        # focus_config 中的設定會覆蓋預設值
        window_title = focus_config.get("window_title") or editor_defaults.get("window_title")
        window_class = focus_config.get("window_class") or editor_defaults.get("window_class")

        # 優先使用 window_class（更可靠）
        try:
            # 確保使用正確的 DISPLAY 環境變數
            env = os.environ.copy()
            if not env.get("DISPLAY"):
                env["DISPLAY"] = ":1"

            # 第一步：使用 xdotool 搜尋視窗 ID
            if window_class:
                # 不使用 --limit，取得所有符合的視窗
                search_cmd = ["xdotool", "search", "--class", window_class]
            elif window_title:
                search_cmd = ["xdotool", "search", "--name", window_title]
            else:
                self.log_error(f"No window_title or window_class for editor type: {editor_type}")
                return False

            # 執行搜尋（timeout 2 秒）
            search_result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=2, env=env)
            if search_result.returncode != 0:
                self.log_error(f"xdotool search failed: {search_result.stderr}")
                return False

            # 取得所有視窗 ID
            all_window_ids = search_result.stdout.strip().split('\n')
            if not all_window_ids or all_window_ids[0] == '':
                self.log_error("No window found")
                return False

            # 取得專案名稱（用於匹配視窗）
            project_name = None
            if notification_data:
                project_name = notification_data.get("project_name", "")

            # 過濾掉隱藏視窗（只有 class 名稱的視窗，例如只叫 "cursor" 的視窗）
            # 這些通常是 DevTools 或其他輔助視窗
            window_id = None
            candidate_windows = []  # 收集所有候選視窗

            for wid in all_window_ids:
                try:
                    name_result = subprocess.run(
                        ["xdotool", "getwindowname", wid],
                        capture_output=True,
                        text=True,
                        timeout=1,
                        env=env
                    )
                    window_name = name_result.stdout.strip()
                    window_name_lower = window_name.lower()

                    # 跳過只有 class 名稱的視窗（例如 "cursor", "code" 等）
                    if window_name_lower == window_class.lower() or window_name_lower == editor_type.lower():
                        continue

                    # 收集候選視窗
                    candidate_windows.append((wid, window_name, window_name_lower))
                except Exception as e:
                    continue

            if not candidate_windows:
                self.log_error("No valid editor window found (all windows seem to be helper windows)")
                return False

            # 如果有專案名稱，優先選擇包含該名稱的視窗
            if project_name:
                project_name_lower = project_name.lower()
                for wid, wname, wname_lower in candidate_windows:
                    if project_name_lower in wname_lower:
                        window_id = wid
                        break

            # 如果沒找到匹配的，使用第一個候選視窗
            if not window_id:
                window_id, _, _ = candidate_windows[0]

            # 第二步：使用完整的多步驟 X11 focus 流程
            # Electron 應用需要多個步驟才能正確 focus
            try:
                from Xlib import X, Xatom
                from Xlib.protocol import event
                import time

                with self._display_lock:
                    d = self._get_display()
                    root = d.screen().root
                    target_window = d.create_resource_object('window', int(window_id))
                    active_window_atom = d.intern_atom("_NET_ACTIVE_WINDOW")

                    # Step 1: WM_CHANGE_STATE (取消最小化)
                    wm_state = d.intern_atom("WM_CHANGE_STATE")
                    ev = event.ClientMessage(
                        window=target_window,
                        client_type=wm_state,
                        data=(32, [1, 0, 0, 0, 0])  # NormalState
                    )
                    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                    d.flush()
                    time.sleep(0.1)

                    # Step 2: _NET_ACTIVE_WINDOW ClientMessage (請求視窗管理器 focus)
                    current_time = int(time.time() * 1000) & 0xFFFFFFFF
                    ev = event.ClientMessage(
                        window=target_window,
                        client_type=active_window_atom,
                        data=(32, [2, current_time, 0, 0, 0])  # source=2 (pager), timestamp
                    )
                    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                    d.flush()
                    time.sleep(0.1)

                    # Step 3: 直接設定 _NET_ACTIVE_WINDOW 屬性（確保設定生效）
                    root.change_property(
                        active_window_atom,
                        Xatom.WINDOW,
                        32,
                        [int(window_id)],
                        X.PropModeReplace
                    )
                    d.sync()
                    time.sleep(0.1)

                    # Step 4: map 視窗（確保可見）
                    target_window.map()
                    d.flush()
                    time.sleep(0.1)

                    # Step 5: raise 視窗（移到最上層）
                    target_window.configure(stack_mode=X.Above)
                    d.flush()
                    time.sleep(0.1)

                    # Step 6: 直接設定 keyboard focus（關鍵！）
                    target_window.set_input_focus(X.RevertToParent, X.CurrentTime)
                    d.flush()
                    d.sync()
                    time.sleep(0.1)

                    # 雙重 Focus 機制（解決 Electron 應用的 focus 問題）
                    #
                    # **問題**：VSCode/Cursor 等 Electron 應用在第一次 focus 時，
                    # 只會 focus 到應用程序本身，而不會 focus 到具體的編輯器視窗。
                    # 第二次點擊才會真正 focus 到目標視窗。
                    #
                    # **解決方案**：在程式中連續執行兩次 focus 流程（Steps 7-8），
                    # 模擬「第二次點擊」的效果，確保一次點擊就能成功 focus。
                    #
                    # Step 7: 再次發送 _NET_ACTIVE_WINDOW ClientMessage
                    current_time = int(time.time() * 1000) & 0xFFFFFFFF
                    ev = event.ClientMessage(
                        window=target_window,
                        client_type=active_window_atom,
                        data=(32, [2, current_time, 0, 0, 0])
                    )
                    root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                    d.flush()
                    time.sleep(0.05)

                    # Step 8: 再次 raise 和 focus
                    target_window.configure(stack_mode=X.Above)
                    target_window.set_input_focus(X.RevertToParent, X.CurrentTime)
                    d.flush()
                    d.sync()

                return True

            except ImportError:
                self.log_error("python3-xlib not installed. Please install: sudo apt install python3-xlib")
                return False
            except Exception as e:
                # 連線可能已損壞，重置以便下次重建
                self._display = None
                self.log_error(f"Xlib focus failed: {e}")
                return False

        except subprocess.TimeoutExpired:
            self.log_error("xdotool search timed out")
            return False
        except FileNotFoundError:
            self.log_error("xdotool not found. Please install: sudo apt install xdotool")
            return False

    def execute_custom_command(self, focus_config, notification_data):
        """執行自訂 focus 指令

        Args:
            focus_config: focus 設定字典
            notification_data: 完整的通知資料

        Returns:
            True if successful, False otherwise
        """
        custom_command = focus_config.get("custom_command")
        if not custom_command:
            self.log_error("custom_command not specified")
            return False

        pass_data = focus_config.get("pass_data", True)

        try:
            if pass_data:
                # 傳遞通知資料給自訂指令（通過 stdin）
                json_data = json.dumps(notification_data)
                result = subprocess.run(
                    custom_command,
                    input=json_data,
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=10
                )
            else:
                # 不傳遞資料，只執行指令
                result = subprocess.run(
                    custom_command,
                    capture_output=True,
                    text=True,
                    shell=True,
                    timeout=10
                )

            if result.returncode == 0:
                return True
            else:
                self.log_error(f"Custom command failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.log_error("Custom command timed out")
            return False
        except Exception as e:
            self.log_error(f"Custom command error: {e}")
            return False

    def log_error(self, message):
        """記錄錯誤到日誌檔"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_message)
        except Exception as e:
            print(f"Failed to write to log: {e}")
        # 同時輸出到 stderr
        print(f"FocusManager Error: {message}", file=sys.stderr)

    def scan_open_ide_windows(self):
        """掃描目前開著的 IDE 視窗

        Returns:
            list: 開著的 IDE 視窗列表，每個元素是字典：
                  {"window_id": str, "project_name": str, "editor_type": str, "window_title": str}
        """
        results = []
        builtin_editors = self.mapping.get("builtin_editors", {})

        # 確保使用正確的 DISPLAY 環境變數
        env = os.environ.copy()
        if not env.get("DISPLAY"):
            env["DISPLAY"] = ":1"

        for editor_type, editor_config in builtin_editors.items():
            window_class = editor_config.get("window_class")
            window_title_pattern = editor_config.get("window_title")

            if not window_class and not window_title_pattern:
                continue

            try:
                # 使用 xdotool 搜尋視窗
                if window_class:
                    search_cmd = ["xdotool", "search", "--class", window_class]
                else:
                    search_cmd = ["xdotool", "search", "--name", window_title_pattern]

                search_result = subprocess.run(
                    search_cmd,
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=env
                )

                if search_result.returncode != 0:
                    continue

                window_ids = search_result.stdout.strip().split('\n')
                if not window_ids or window_ids[0] == '':
                    continue

                # 取得每個視窗的名稱
                for wid in window_ids:
                    try:
                        name_result = subprocess.run(
                            ["xdotool", "getwindowname", wid],
                            capture_output=True,
                            text=True,
                            timeout=1,
                            env=env
                        )
                        window_name = name_result.stdout.strip()
                        window_name_lower = window_name.lower()

                        # 跳過只有 class 名稱的視窗（例如 "cursor", "code" 等輔助視窗）
                        if window_class and window_name_lower == window_class.lower():
                            continue
                        if window_name_lower == editor_type.lower():
                            continue

                        # 確認視窗標題符合 IDE 格式（結尾包含 IDE 名稱）
                        # 過濾掉非 IDE 視窗（如 Chrome for Testing 等）
                        ide_suffixes = ["cursor", "visual studio code", "code"]
                        is_ide_window = False
                        for suffix in ide_suffixes:
                            if window_name_lower.endswith(f" - {suffix}"):
                                is_ide_window = True
                                break
                        if not is_ide_window:
                            continue

                        # 從視窗標題提取專案名稱
                        project_name = self._extract_project_name(window_name, editor_type)

                        # 避免重複（同一個專案只顯示一次）
                        if not any(r["project_name"] == project_name and r["editor_type"] == editor_type for r in results):
                            results.append({
                                "window_id": wid,
                                "project_name": project_name,
                                "editor_type": editor_type,
                                "window_title": window_name
                            })
                    except Exception:
                        continue

            except subprocess.TimeoutExpired:
                continue
            except FileNotFoundError:
                print("xdotool not found. Please install: sudo apt install xdotool")
                break

        return results

    def _extract_project_name(self, window_title, editor_type):
        """從視窗標題提取專案名稱

        Cursor 格式: "<活動內容> - <專案名稱> - Cursor"
        VSCode 格式: "<檔案名稱> - <專案名稱> - Visual Studio Code"

        Args:
            window_title: 視窗標題
            editor_type: 編輯器類型（vscode, cursor 等）

        Returns:
            str: 專案名稱
        """
        # 使用 " - " 分割
        parts = window_title.split(" - ")

        if len(parts) >= 3:
            # 格式：<活動內容> - <專案名稱> - <IDE名稱>
            # 取倒數第二段作為專案名稱
            last_part = parts[-1].strip()
            # 確認最後一段是 IDE 名稱
            if last_part.lower() in ["cursor", "visual studio code", "code"]:
                return parts[-2].strip()

        if len(parts) >= 2:
            # 格式：<專案名稱> - <IDE名稱>
            last_part = parts[-1].strip()
            if last_part.lower() in ["cursor", "visual studio code", "code"]:
                return parts[-2].strip()
            # 格式：<活動內容> - <專案名稱>
            return parts[-1].strip()

        # 如果沒有找到分隔符號，返回整個標題（截斷）
        return window_title[:30] if len(window_title) > 30 else window_title

    def focus_window_by_id(self, window_id):
        """透過視窗 ID 直接 focus 視窗

        Args:
            window_id: X11 視窗 ID

        Returns:
            True if successful, False otherwise
        """
        try:
            from Xlib import X
            from Xlib.protocol import event
            import time

            with self._display_lock:
                d = self._get_display()
                root = d.screen().root
                target_window = d.create_resource_object('window', int(window_id))
                active_window_atom = d.intern_atom("_NET_ACTIVE_WINDOW")

                # Step 1: WM_CHANGE_STATE (取消最小化)
                wm_state = d.intern_atom("WM_CHANGE_STATE")
                ev = event.ClientMessage(
                    window=target_window,
                    client_type=wm_state,
                    data=(32, [1, 0, 0, 0, 0])
                )
                root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                d.flush()
                time.sleep(0.05)

                # Step 2: _NET_ACTIVE_WINDOW ClientMessage
                current_time = int(time.time() * 1000) & 0xFFFFFFFF
                ev = event.ClientMessage(
                    window=target_window,
                    client_type=active_window_atom,
                    data=(32, [2, current_time, 0, 0, 0])
                )
                root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                d.flush()
                time.sleep(0.05)

                # Step 3: raise 視窗
                target_window.configure(stack_mode=X.Above)
                d.flush()
                time.sleep(0.05)

                # Step 4: 設定 keyboard focus
                target_window.set_input_focus(X.RevertToParent, X.CurrentTime)
                d.flush()
                d.sync()
                time.sleep(0.05)

                # 雙重 Focus（Electron 應用需要）
                current_time = int(time.time() * 1000) & 0xFFFFFFFF
                ev = event.ClientMessage(
                    window=target_window,
                    client_type=active_window_atom,
                    data=(32, [2, current_time, 0, 0, 0])
                )
                root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                target_window.configure(stack_mode=X.Above)
                target_window.set_input_focus(X.RevertToParent, X.CurrentTime)
                d.flush()
                d.sync()

            return True

        except ImportError:
            self.log_error("python3-xlib not installed")
            return False
        except Exception as e:
            # 連線可能已損壞，重置以便下次重建
            self._display = None
            self.log_error(f"focus_window_by_id failed: {e}")
            return False


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
        self.close_button = close_button  # 保存引用以便點擊檢測

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

    def __init__(self, title, message, urgency="normal", on_close=None, metadata=None, notification_data=None, focus_manager=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.on_close_callback = on_close
        self.urgency = urgency
        metadata = metadata or {}
        self.notification_data = notification_data  # 保存完整通知資料
        self.focus_manager = focus_manager  # FocusManager 實例
        self.creation_time = datetime.datetime.now()  # 記錄卡片創建時間
        self.timestamp = metadata.get("timestamp", "")  # 保存時間字串
        self.timer_id = None  # 用於顏色更新的 timer ID
        self.event_time_label = None  # 時間標籤的引用（稍後設置）

        # 設定樣式
        if urgency == "critical":
            self.get_style_context().add_class("notification-critical")
        else:
            self.get_style_context().add_class("notification-normal")

        # === Header: Icon + Project ===
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

        # Menu button (⋮)
        menu_button = Gtk.Button()
        menu_button.set_label("⋮")
        menu_button.set_relief(Gtk.ReliefStyle.NONE)
        menu_button.set_focus_on_click(False)
        menu_button.set_tooltip_text("More options")
        menu_button.connect("clicked", self.on_show_menu)
        menu_button.set_size_request(20, 20)

        header.pack_start(icon_label, False, False, 0)
        header.pack_start(project_label, True, True, 0)
        header.pack_start(menu_button, False, False, 0)

        # === Body: 主要顯示 transcript 對話內容 ===
        # 優先從 transcript 讀取對話內容
        transcript_content = None
        transcript_path = metadata.get("transcript")

        debug_log("📄 Transcript 處理開始", {
            "提供的 transcript_path": transcript_path,
            "session_id": metadata.get("session"),
            "是否需要自動搜尋": not transcript_path and metadata.get("session")
        })

        # 如果沒有 transcript_path，嘗試從 session_id 推斷
        if not transcript_path and metadata.get("session"):
            session_id = metadata.get("session")
            cwd = metadata.get("cwd", "")
            project_name = metadata.get("project", "")

            # 嘗試常見的 transcript 路徑模式
            possible_paths = [
                # Claude Code 通常把 transcript 存在 ~/.claude/projects/{cwd_hash}/transcripts/{session_id}.jsonl
                Path.home() / ".claude" / "projects" / cwd / "transcripts" / f"{session_id}.jsonl",
                Path.home() / ".claude" / "transcripts" / f"{session_id}.jsonl",
            ]

            debug_log("🔍 開始搜尋 transcript 檔案", {
                "session_id": session_id,
                "預設搜尋路徑": [str(p) for p in possible_paths]
            })

            # 也可以嘗試搜尋 .claude 目錄
            claude_dir = Path.home() / ".claude"
            if claude_dir.exists():
                # 搜尋所有 transcripts 目錄下的 session_id.jsonl
                for transcript_file in claude_dir.rglob(f"*/{session_id}.jsonl"):
                    possible_paths.insert(0, transcript_file)
                    debug_log("✓ 使用 rglob 找到 transcript", {"路徑": str(transcript_file)})
                    break

            # 檢查每個可能的路徑
            found_path = None
            for path in possible_paths:
                if path.exists():
                    transcript_path = str(path)
                    found_path = transcript_path
                    debug_log("✓ 找到 transcript 檔案", {"路徑": transcript_path})
                    break
                else:
                    debug_log("✗ 路徑不存在", {"路徑": str(path)})

            if not found_path:
                debug_log("❌ 所有路徑都找不到 transcript 檔案", {
                    "嘗試過的路徑": [str(p) for p in possible_paths]
                })

        # 決定主要顯示內容和狀態訊息
        transcript_found = False
        transcript_read_success = False

        if transcript_path:
            # 使用預設值，不依賴 config（NotificationCardV3 沒有 config 屬性）
            head_lines = 5
            tail_lines = 5
            transcript_content = extract_last_messages_from_transcript(
                transcript_path, head_lines=head_lines, tail_lines=tail_lines
            )
            transcript_found = True
            transcript_read_success = transcript_content is not None
            debug_log("📖 Transcript 內容提取結果", {
                "成功": transcript_read_success,
                "內容長度": len(transcript_content) if transcript_content else 0
            })
        else:
            transcript_content = None
            debug_log("⚠️ 無 transcript_path，無法讀取對話內容")

        # 主要顯示區域：根據情況顯示不同訊息
        if transcript_content:
            # 成功讀取 transcript
            main_message = transcript_content
        elif message:
            # 沒有 transcript 但有 message
            main_message = message
        else:
            # 沒有 transcript 也沒有 message，顯示詳細狀態
            if transcript_found and not transcript_read_success:
                main_message = "⚠️ Transcript file found but failed to read"
            elif not transcript_found and metadata.get("session"):
                main_message = "ℹ️ No message\n(Transcript not found for this session)"
            else:
                main_message = "ℹ️ No message"

        main_label = Gtk.Label(label=main_message)
        main_label.set_line_wrap(True)
        main_label.set_halign(Gtk.Align.START)
        main_label.set_valign(Gtk.Align.START)
        main_label.set_xalign(0)
        main_label.set_selectable(True)
        main_label.get_style_context().add_class("notification-body")
        main_label.set_margin_start(12)
        main_label.set_margin_end(12)
        main_label.set_margin_top(4)
        main_label.set_margin_bottom(6)

        # === Footer: Message（左側）+ Event at Time（右側）===
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.set_margin_start(12)
        footer.set_margin_end(12)
        footer.set_margin_bottom(8)

        # 保存 session_id (用於 Detail 對話框)
        if metadata.get("session"):
            self.session_id = metadata["session"]

        # Message（靠左，灰色小字，只在有值時顯示）
        if message:
            # 限制 message 長度，避免擠壓時間
            display_message = message if len(message) <= 40 else message[:37] + "..."
            message_label = Gtk.Label()
            message_label.set_markup(f'<span size="small" foreground="#6c7086">{display_message}</span>')
            message_label.set_halign(Gtk.Align.START)
            message_label.set_hexpand(True)
            message_label.set_ellipsize(3)  # 過長時省略
            message_label.set_max_width_chars(35)
            footer.pack_start(message_label, True, True, 0)

        # Event at Time（靠右）
        self.event_name = metadata.get("event_name", "")
        timestamp = metadata.get("timestamp", "")
        self.event_time_label = Gtk.Label()
        if timestamp:
            time_only = timestamp.split(" ")[1][:5] if " " in timestamp else timestamp[:5]
            event_time_text = f"{self.event_name} at {time_only}"
            # 根據時間差獲取顏色
            time_color = self.get_time_color(timestamp)
        else:
            event_time_text = self.event_name
            time_color = "#6c7086"  # 預設灰色

        self.event_time_label.set_markup(f'<span size="small" foreground="{time_color}">{event_time_text}</span>')
        self.event_time_label.set_halign(Gtk.Align.END)
        self.event_time_label.set_valign(Gtk.Align.END)
        self.event_time_label.set_tooltip_text(f'Full time: {timestamp}' if timestamp else '')

        footer.pack_end(self.event_time_label, False, False, 0)

        # === 左側內容區 ===
        left_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_content.pack_start(header, False, False, 0)
        left_content.pack_start(main_label, False, False, 0)  # 主要內容（transcript）
        left_content.pack_start(footer, False, False, 0)

        # === 右側 Focus 按鈕區（整個 column 都是按鈕）===
        right_focus_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right_focus_area.set_size_request(40, -1)  # 固定寬度 40px
        right_focus_area.set_halign(Gtk.Align.END)  # 靠右對齊

        if self.focus_manager and self.notification_data:
            # 整個右側空間都是按鈕
            self.focus_button = Gtk.Button()
            self.focus_button.set_relief(Gtk.ReliefStyle.NONE)
            self.focus_button.get_style_context().add_class("focus-button")

            # 創建一個 box 來放置 icon（垂直置中）
            icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            icon_box.set_valign(Gtk.Align.CENTER)  # icon 垂直置中
            icon_box.set_halign(Gtk.Align.CENTER)  # icon 水平置中

            # 創建 icon 和 spinner（初始顯示向右箭頭）
            self.focus_icon = Gtk.Image.new_from_icon_name("go-next", Gtk.IconSize.LARGE_TOOLBAR)
            self.focus_spinner = Gtk.Spinner()

            # 添加 icon 到 box
            icon_box.pack_start(self.focus_icon, False, False, 0)

            # 將 icon_box 放入按鈕
            self.focus_button.add(icon_box)
            # 使用 button-press-event 而不是 clicked，這樣在窗口沒焦點時也能響應
            self.focus_button.connect("button-press-event", self.on_focus_clicked)

            # 保存 icon_box 引用，以便後續切換 icon
            self.icon_box = icon_box

            right_focus_area.pack_start(self.focus_button, True, True, 0)  # 填滿整個右側空間

        # === 組裝：左右兩區 ===
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main_hbox.pack_start(left_content, True, True, 0)  # 左側可擴展
        main_hbox.pack_start(right_focus_area, False, False, 0)  # 右側固定寬度

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self.pack_start(main_hbox, False, False, 0)

        # 啟動顏色更新 timer（5 分鐘後第一次檢查）
        if self.timestamp and self.event_time_label:
            self.schedule_next_color_update()

    def get_time_color(self, timestamp_str):
        """根據時間差返回對應的顏色

        Args:
            timestamp_str: 時間字串 (格式: "YYYY-MM-DD HH:MM:SS")

        Returns:
            顏色字串 (hex 格式)
        """
        try:
            # 解析時間戳
            notification_time = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

            # 計算時間差（分鐘）- 使用當前時間，這樣顏色會隨時間變化
            time_diff = (datetime.datetime.now() - notification_time).total_seconds() / 60

            # 根據時間差返回顏色（Catppuccin Mocha 配色）
            if time_diff <= 5:
                return "#a6e3a1"  # 綠色，鮮豔（5分鐘內）
            elif time_diff <= 10:
                return "#f9e2af"  # 黃色（5-10分鐘）
            elif time_diff <= 20:
                return "#fab387"  # 橙色（10-20分鐘）
            else:
                return "#6c7086"  # 灰色（20分鐘以上）

            # DEBUG 模式（用於快速測試，使用 1 分鐘單位）：
            # if time_diff <= 1:
            #     return "#a6e3a1"  # 綠色，鮮豔（1分鐘內）
            # elif time_diff <= 2:
            #     return "#f9e2af"  # 黃色（1-2分鐘）
            # elif time_diff <= 4:
            #     return "#fab387"  # 橙色（2-4分鐘）
            # else:
            #     return "#6c7086"  # 灰色（4分鐘以上）
        except Exception:
            # 解析失敗，返回預設灰色
            return "#6c7086"

    def on_focus_clicked(self, widget, event=None):
        """Focus icon button 被點擊

        Args:
            widget: 按鈕控件
            event: 事件對象（button-press-event 時會傳入）
        """
        print("=" * 60)
        print("[DEBUG] on_focus_clicked TRIGGERED!")
        print(f"[DEBUG] widget: {widget}")
        print(f"[DEBUG] event: {event}")
        if event:
            print(f"[DEBUG] event.type: {event.type}")
            print(f"[DEBUG] event.button: {event.button}")
        print("=" * 60)

        # 切換到 loading 狀態
        self.set_focus_icon_state("loading")

        # 在背景執行 focus 操作
        def focus_thread():
            result = self.focus_manager.focus_window(self.notification_data)
            # 使用 GLib.idle_add 在主線程更新 UI
            if result:
                GLib.idle_add(self.set_focus_icon_state, "success")
            else:
                GLib.idle_add(self.set_focus_icon_state, "error")

        thread = threading.Thread(target=focus_thread, daemon=True)
        thread.start()

        # 對於 button-press-event，返回 False 讓事件繼續傳播（給按鈕的 clicked）
        # 但我們已經不使用 clicked 了，所以這裡返回 True 停止事件傳播
        return True

    def set_focus_icon_state(self, state):
        """設定 focus icon 狀態

        Args:
            state: "idle", "loading", "success", "error"
        """
        if not hasattr(self, 'icon_box'):
            return

        # 移除 icon_box 中的當前 child
        for child in self.icon_box.get_children():
            self.icon_box.remove(child)

        if state == "loading":
            # 顯示 spinner 並啟動
            self.icon_box.pack_start(self.focus_spinner, False, False, 0)
            self.focus_spinner.start()
            self.focus_spinner.show()
            self.focus_button.set_sensitive(False)  # 禁用按鈕
        elif state == "success":
            # 顯示成功 icon
            success_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
            self.icon_box.pack_start(success_icon, False, False, 0)
            success_icon.show()
            self.focus_button.set_sensitive(True)  # 重新啟用按鈕
            # 3 秒後恢復 idle 狀態
            GLib.timeout_add_seconds(3, lambda: self.set_focus_icon_state("idle"))
        elif state == "error":
            # 顯示錯誤 icon
            error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
            self.icon_box.pack_start(error_icon, False, False, 0)
            error_icon.show()
            self.focus_button.set_sensitive(True)  # 重新啟用按鈕
            # 3 秒後恢復 idle 狀態
            GLib.timeout_add_seconds(3, lambda: self.set_focus_icon_state("idle"))
        else:  # idle
            # 恢復原本的 icon
            self.focus_spinner.stop()
            self.icon_box.pack_start(self.focus_icon, False, False, 0)
            self.focus_icon.show()
            self.focus_button.set_sensitive(True)  # 重新啟用按鈕

    def schedule_next_color_update(self):
        """安排下一次顏色更新

        根據當前經過的時間，決定下一次更新時間：

        DEBUG 模式（1 分鐘單位）：
        - 0-1 分鐘：1 分鐘後更新
        - 1-2 分鐘：2 分鐘後更新
        - 2-4 分鐘：4 分鐘後更新
        - 4 分鐘以上：不再更新

        正式模式（5 分鐘單位）：
        - 0-5 分鐘：5 分鐘後更新
        - 5-10 分鐘：10 分鐘後更新
        - 10-20 分鐘：20 分鐘後更新
        - 20 分鐘以上：不再更新
        """
        # 取消之前的 timer
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

        if not self.timestamp:
            return

        try:
            # 解析通知時間戳
            notification_time = datetime.datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S")
            # 計算已經過的時間（分鐘）- 從通知時間開始算
            elapsed = (datetime.datetime.now() - notification_time).total_seconds() / 60
        except Exception:
            return

        # 決定下一次更新的時間點
        if elapsed < 5:
            next_update_minutes = 5 - elapsed
        elif elapsed < 10:
            next_update_minutes = 10 - elapsed
        elif elapsed < 20:
            next_update_minutes = 20 - elapsed
        else:
            # 超過 20 分鐘，不再更新
            return

        # DEBUG 模式（用於快速測試，使用 1 分鐘單位）：
        # if elapsed < 1:
        #     next_update_minutes = 1 - elapsed
        # elif elapsed < 2:
        #     next_update_minutes = 2 - elapsed
        # elif elapsed < 4:
        #     next_update_minutes = 4 - elapsed
        # else:
        #     return

        # 設定 timer（轉換為毫秒）
        timeout_ms = int(next_update_minutes * 60 * 1000)
        self.timer_id = GLib.timeout_add(timeout_ms, self.update_time_color)

    def update_time_color(self):
        """更新時間標籤的顏色"""
        if not self.event_time_label or not self.timestamp:
            return False  # 停止 timer

        # 獲取新的顏色
        new_color = self.get_time_color(self.timestamp)

        # 更新標籤
        if self.timestamp:
            time_only = self.timestamp.split(" ")[1][:5] if " " in self.timestamp else self.timestamp[:5]
            event_time_text = f"{self.event_name} at {time_only}"
        else:
            event_time_text = self.event_name

        self.event_time_label.set_markup(f'<span size="small" foreground="{new_color}">{event_time_text}</span>')

        # 安排下一次更新
        self.schedule_next_color_update()

        return False  # 停止當前 timer（因為已經安排了新的）

    def on_show_menu(self, widget):
        """顯示選項選單"""
        menu = Gtk.Menu()
        detail_item = Gtk.MenuItem(label="詳情")
        detail_item.connect("activate", self.on_show_detail)
        menu.append(detail_item)
        menu.show_all()
        menu.popup_at_widget(widget, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)

    def on_show_detail(self, widget):
        """顯示通知詳細資訊對話框"""
        if not self.notification_data:
            return

        # 創建對話框
        dialog = Gtk.Dialog(
            title="Notification Details",
            parent=self.get_toplevel(),
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT
        )
        dialog.set_default_size(600, 400)

        # 創建可滾動的文字區域
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_margin_start(10)
        scrolled_window.set_margin_end(10)
        scrolled_window.set_margin_top(10)
        scrolled_window.set_margin_bottom(10)

        # 使用 TextView 顯示 JSON 資料
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_left_margin(10)
        text_view.set_right_margin(10)
        text_view.set_top_margin(10)
        text_view.set_bottom_margin(10)

        # 格式化 JSON 資料
        formatted_json = json.dumps(self.notification_data, indent=2, ensure_ascii=False)
        text_buffer = text_view.get_buffer()
        text_buffer.set_text(formatted_json)

        scrolled_window.add(text_view)

        # 加入 Copy SessionID 按鈕
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_margin_start(10)
        button_box.set_margin_end(10)
        button_box.set_margin_bottom(10)

        if hasattr(self, 'session_id') and self.session_id:
            copy_button = Gtk.Button(label="Copy Session ID")
            copy_button.connect("clicked", lambda w: self.copy_session_id_to_clipboard(w, dialog))
            button_box.pack_start(copy_button, False, False, 0)

        close_button = Gtk.Button(label="Close")
        close_button.connect("clicked", lambda w: dialog.destroy())
        button_box.pack_end(close_button, False, False, 0)

        # 組裝對話框
        content_area = dialog.get_content_area()
        content_area.pack_start(scrolled_window, True, True, 0)
        content_area.pack_start(button_box, False, False, 0)

        dialog.show_all()

    def copy_session_id_to_clipboard(self, widget, dialog):
        """複製 SessionID 到剪貼簿"""
        if not hasattr(self, 'session_id') or not self.session_id:
            return

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.session_id, -1)
        clipboard.store()

        # 顯示複製成功的提示
        widget.set_label(f"✓ Copied: {self.session_id[:16]}...")

        # 2 秒後關閉對話框
        GLib.timeout_add_seconds(2, dialog.destroy)

    def on_close(self, widget=None):
        """關閉通知"""
        # 取消顏色更新 timer
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None

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

        # 快捷按鈕顯示字數
        label = Gtk.Label(label="Shortcut Max Chars:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        shortcut_chars_spin = Gtk.SpinButton()
        shortcut_chars_spin.set_range(4, 20)
        shortcut_chars_spin.set_increments(1, 2)
        shortcut_chars_spin.set_value(self.config["behavior"].get("shortcut_max_chars", 10))
        grid.attach(shortcut_chars_spin, 1, row, 1, 1)
        self.shortcut_chars_spin = shortcut_chars_spin
        row += 1

        # Transcript 預覽行數設定
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(8)
        separator.set_margin_bottom(8)
        grid.attach(separator, 0, row, 2, 1)
        row += 1

        section_label = Gtk.Label(label="<b>Transcript Preview</b>", xalign=0)
        section_label.set_use_markup(True)
        grid.attach(section_label, 0, row, 2, 1)
        row += 1

        # 頭部行數
        label = Gtk.Label(label="Head Lines:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        head_lines_spin = Gtk.SpinButton()
        head_lines_spin.set_range(1, 20)
        head_lines_spin.set_increments(1, 5)
        head_lines_spin.set_value(self.config["behavior"].get("transcript_head_lines", 5))
        grid.attach(head_lines_spin, 1, row, 1, 1)
        self.head_lines_spin = head_lines_spin
        row += 1

        # 尾部行數
        label = Gtk.Label(label="Tail Lines:", xalign=0)
        grid.attach(label, 0, row, 1, 1)

        tail_lines_spin = Gtk.SpinButton()
        tail_lines_spin.set_range(1, 20)
        tail_lines_spin.set_increments(1, 5)
        tail_lines_spin.set_value(self.config["behavior"].get("transcript_tail_lines", 5))
        grid.attach(tail_lines_spin, 1, row, 1, 1)
        self.tail_lines_spin = tail_lines_spin
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
        config["behavior"]["shortcut_max_chars"] = int(self.shortcut_chars_spin.get_value())
        config["behavior"]["transcript_head_lines"] = int(self.head_lines_spin.get_value())
        config["behavior"]["transcript_tail_lines"] = int(self.tail_lines_spin.get_value())

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
        # 快捷按鈕字數
        self.shortcut_chars_spin.connect("value-changed", self.on_shortcut_chars_change)

    def on_shortcut_chars_change(self, widget):
        """當快捷按鈕字數改變時，即時更新快捷列"""
        max_chars = int(self.shortcut_chars_spin.get_value())
        self.parent.config["behavior"]["shortcut_max_chars"] = max_chars
        # 重新載入快捷列
        self.parent.refresh_shortcut_bar()

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
        self.shortcut_chars_spin.set_value(DEFAULT_CONFIG["behavior"]["shortcut_max_chars"])
        self.head_lines_spin.set_value(DEFAULT_CONFIG["behavior"]["transcript_head_lines"])
        self.tail_lines_spin.set_value(DEFAULT_CONFIG["behavior"]["transcript_tail_lines"])

        # 控件的 value-changed 信號會自動觸發 on_preview_change，所以不需要手動調用


class NotificationContainer(Gtk.Window):
    """通知容器視窗"""

    def __init__(self):
        super().__init__(title="Claude Code Notifications")

        # 載入設定
        self.config = load_config()

        self.notifications = []
        self.opacity = self.config["appearance"]["opacity"]  # 從設定讀取初始透明度

        # 創建 FocusManager 實例
        self.focus_manager = FocusManager()

        # 拖拉相關變數
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        # 調整大小相關變數
        self.resize_edge = None
        self.is_resizing = False
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.resize_start_width = 0
        self.resize_start_height = 0
        self.resize_start_win_x = 0
        self.resize_start_win_y = 0
        self.edge_size = 10

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
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)  # 使用 UTILITY 類型（可接受點擊）
        self.set_accept_focus(False)  # 不搶奪焦點

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

        # 視窗事件（邊緣調整大小）
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("motion-notify-event", self.on_window_motion)
        self.connect("button-press-event", self.on_window_button_press)
        self.connect("button-release-event", self.on_window_button_release)

    def create_ui(self):
        """建立 UI"""
        # 主容器 - 不設 margin，讓子元件各自控制
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # 標題列（用 EventBox 包裝以支援拖拉）
        # 背景色放在 EventBox 上，用 CSS padding 控制內容距離
        header_event_box = Gtk.EventBox()
        header_event_box.get_style_context().add_class("header")
        # 設定 margin 讓標題列跟卡片對齊
        header_event_box.set_margin_start(20)
        header_event_box.set_margin_end(20)
        header_event_box.set_margin_top(12)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        # 內部 margin = EventBox 的 padding 效果
        header.set_margin_start(12)
        header.set_margin_end(12)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        # 設定拖拉事件
        header_event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                                    Gdk.EventMask.BUTTON_RELEASE_MASK |
                                    Gdk.EventMask.POINTER_MOTION_MASK |
                                    Gdk.EventMask.ENTER_NOTIFY_MASK |
                                    Gdk.EventMask.LEAVE_NOTIFY_MASK)
        header_event_box.connect("button-press-event", self.on_drag_start)
        header_event_box.connect("button-release-event", self.on_drag_end)
        header_event_box.connect("motion-notify-event", self.on_drag_motion)
        header_event_box.connect("enter-notify-event", self.on_header_enter)
        header_event_box.connect("leave-notify-event", self.on_header_leave)

        title_label = Gtk.Label(label="Claude Code Notifications")
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        title_label.get_style_context().add_class("header-title")

        # 設定選單按鈕（齒輪圖示）
        settings_menu_button = Gtk.MenuButton()
        settings_menu_button.set_relief(Gtk.ReliefStyle.NONE)
        settings_menu_button.set_tooltip_text("Settings")
        settings_icon = Gtk.Image.new_from_icon_name("preferences-system", Gtk.IconSize.BUTTON)
        settings_menu_button.add(settings_icon)

        # 建立設定選單
        settings_menu = Gtk.Menu()
        # 設定選項
        settings_item = Gtk.MenuItem(label="Settings")
        settings_item.connect("activate", lambda w: self.open_settings_dialog(w))
        settings_menu.append(settings_item)
        # Clear All 選項
        clear_item = Gtk.MenuItem(label="Clear All")
        clear_item.connect("activate", lambda w: self.clear_all(w))
        settings_menu.append(clear_item)
        settings_menu.show_all()
        settings_menu_button.set_popup(settings_menu)

        # 最小化按鈕
        minimize_button = Gtk.Button.new_from_icon_name("window-minimize", Gtk.IconSize.BUTTON)
        minimize_button.set_relief(Gtk.ReliefStyle.NONE)
        minimize_button.connect("clicked", lambda w: self.hide())

        header.pack_start(title_label, True, True, 0)
        header.pack_start(settings_menu_button, False, False, 0)
        header.pack_start(minimize_button, False, False, 0)

        # 將 header 加入 EventBox
        header_event_box.add(header)

        # IDE 快捷列
        self.shortcut_bar = self.create_shortcut_bar()

        # 滾動視窗
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        # 設定 margin 讓 resize 邊界可以被偵測（edge_size = 10px）
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        scrolled.set_margin_bottom(10)

        # 通知列表容器（scrolled 已有外部 margin，這裡只需要內部間距）
        self.notification_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.notification_box.set_margin_start(2)
        self.notification_box.set_margin_end(2)
        self.notification_box.set_margin_top(4)
        self.notification_box.set_margin_bottom(4)

        scrolled.add(self.notification_box)

        # 組裝
        main_box.pack_start(header_event_box, False, False, 0)
        main_box.pack_start(self.shortcut_bar, False, False, 0)
        main_box.pack_start(Gtk.Separator(), False, False, 0)
        main_box.pack_start(scrolled, True, True, 0)

        self.add(main_box)

    def create_shortcut_bar(self):
        """建立 IDE 快捷列"""
        # 外層容器（包含 margin）
        shortcut_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        shortcut_container.set_margin_start(20)
        shortcut_container.set_margin_end(20)
        shortcut_container.set_margin_top(10)
        shortcut_container.set_margin_bottom(0)
        shortcut_container.get_style_context().add_class("shortcut-bar")

        # 快捷按鈕容器（可滾動）
        self.shortcut_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.shortcut_buttons_box.set_hexpand(True)

        # 使用 ScrolledWindow 來處理按鈕過多的情況
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scrolled.set_hexpand(True)
        scrolled.set_min_content_height(28)
        scrolled.add(self.shortcut_buttons_box)

        # Refresh 按鈕
        refresh_button = Gtk.Button()
        refresh_button.set_relief(Gtk.ReliefStyle.NONE)
        refresh_button.set_tooltip_text("Refresh IDE windows")
        refresh_icon = Gtk.Image.new_from_icon_name("view-refresh", Gtk.IconSize.SMALL_TOOLBAR)
        refresh_button.add(refresh_icon)
        refresh_button.connect("clicked", self.on_refresh_shortcut_bar)
        refresh_button.get_style_context().add_class("shortcut-refresh")

        shortcut_container.pack_start(scrolled, True, True, 0)
        shortcut_container.pack_end(refresh_button, False, False, 0)

        # 初始載入 IDE 視窗
        GLib.idle_add(self.refresh_shortcut_bar)

        return shortcut_container

    def refresh_shortcut_bar(self):
        """重新載入 IDE 視窗快捷按鈕（非阻塞）

        scan_open_ide_windows() 需要多次呼叫 xdotool subprocess，
        在 main thread 執行會阻塞 GTK main loop 導致視窗無回應。
        改為在背景 thread 掃描，完成後用 GLib.idle_add 回到 main thread 更新 UI。
        """
        def scan_thread():
            ide_windows = self.focus_manager.scan_open_ide_windows()
            GLib.idle_add(self._update_shortcut_buttons, ide_windows)

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()
        return False  # GLib.idle_add 只執行一次

    def _update_shortcut_buttons(self, ide_windows):
        """在 main thread 更新快捷列按鈕（由 refresh_shortcut_bar 的背景 thread 回呼）"""
        # 清除現有按鈕
        for child in self.shortcut_buttons_box.get_children():
            self.shortcut_buttons_box.remove(child)

        if not ide_windows:
            # 沒有開著的 IDE 視窗，顯示提示
            empty_label = Gtk.Label(label="No IDE windows")
            empty_label.get_style_context().add_class("shortcut-empty")
            self.shortcut_buttons_box.pack_start(empty_label, False, False, 0)
        else:
            # 從設定讀取按鈕顯示字數限制
            max_chars = self.config["behavior"].get("shortcut_max_chars", 10)

            # 建立按鈕
            for window_info in ide_windows:
                project_name = window_info["project_name"]
                editor_type = window_info["editor_type"]
                window_id = window_info["window_id"]

                # 截取專案名稱
                display_name = project_name[:max_chars] if len(project_name) > max_chars else project_name

                # 根據 IDE 類型設定顏色 class
                button = Gtk.Button(label=display_name)
                button.set_relief(Gtk.ReliefStyle.NONE)
                button.set_tooltip_text(f"{project_name} ({editor_type.upper()})")
                button.get_style_context().add_class("shortcut-button")
                button.get_style_context().add_class(f"shortcut-{editor_type}")

                # 連接點擊事件
                button.connect("clicked", self.on_shortcut_button_clicked, window_id)

                self.shortcut_buttons_box.pack_start(button, False, False, 0)

        self.shortcut_buttons_box.show_all()
        return False  # GLib.idle_add 只執行一次

    def on_refresh_shortcut_bar(self, button):
        """Refresh 按鈕點擊事件"""
        self.refresh_shortcut_bar()

    def on_shortcut_button_clicked(self, button, window_id):
        """快捷按鈕點擊事件"""
        # 在背景執行 focus 操作
        def focus_thread():
            self.focus_manager.focus_window_by_id(window_id)

        thread = threading.Thread(target=focus_thread, daemon=True)
        thread.start()

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

        /* Dialog 視窗不要套用透明度和動畫 */
        dialog {{
            opacity: 1;
            transition: none;
        }}

        .header {{
            background-color: rgba(17, 17, 27, 0.8);
            padding: 12px 12px 8px 12px;
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

        .focus-button {{
            background-color: rgba(137, 180, 250, 0.15);
            border-left: 2px solid rgba(137, 180, 250, 0.3);
            border-radius: 0px;
            padding: 0px;
            min-width: 40px;
        }}

        .focus-button:hover {{
            background-color: rgba(137, 180, 250, 0.25);
            border-left-color: rgba(137, 180, 250, 0.5);
        }}

        .focus-button:active {{
            background-color: rgba(137, 180, 250, 0.35);
        }}

        /* IDE 快捷列 */
        .shortcut-bar {{
            padding: 2px 4px;
        }}

        .shortcut-button {{
            font-size: 11px;
            padding: 2px 8px;
            min-height: 20px;
            border-radius: 4px;
            background-color: rgba(137, 180, 250, 0.15);
            color: #cdd6f4;
        }}

        .shortcut-button:hover {{
            background-color: rgba(137, 180, 250, 0.3);
        }}

        .shortcut-button:active {{
            background-color: rgba(137, 180, 250, 0.45);
        }}

        /* VSCode - 藍色 */
        .shortcut-vscode {{
            border-left: 3px solid #89b4fa;
        }}

        /* Cursor - 紫色 */
        .shortcut-cursor {{
            border-left: 3px solid #cba6f7;
        }}

        .shortcut-refresh {{
            padding: 2px 4px;
            min-width: 24px;
            min-height: 24px;
        }}

        .shortcut-refresh:hover {{
            background-color: rgba(137, 180, 250, 0.2);
            border-radius: 4px;
        }}

        .shortcut-empty {{
            font-size: 11px;
            color: rgba(205, 214, 244, 0.5);
            font-style: italic;
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
        """創建系統托盤圖標（使用 AppIndicator3）

        AppIndicator3 是 GNOME 3+ 上正確的系統托盤實現，
        取代已 deprecated 的 Gtk.StatusIcon。
        需要 ubuntu-appindicators extension（Ubuntu 預設啟用）。
        """
        # 決定圖標
        icon_path = PROJECT_ROOT / "assets" / "icon.png"
        if icon_path.exists():
            # 使用自訂圖標（AppIndicator 需要絕對路徑，不含副檔名）
            # 但 icon_theme_path 模式需要目錄和圖標名稱分開
            icon_dir = str(icon_path.parent)
            icon_name = icon_path.stem  # "icon" (不含 .png)
            self.indicator = AppIndicator3.Indicator.new(
                "claude-notify-gtk",
                icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_icon_theme_path(icon_dir)
            debug_log("✅ 使用自訂托盤圖標 (AppIndicator3)", {"path": str(icon_path)})
        else:
            # Fallback 到系統圖標
            self.indicator = AppIndicator3.Indicator.new(
                "claude-notify-gtk",
                "dialog-information",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            debug_log("✅ 使用系統圖標 (AppIndicator3): dialog-information")

        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Claude Code Notifier")

        # AppIndicator3 必須設定 menu（不像 StatusIcon 有 activate signal）
        menu = Gtk.Menu()

        show_item = Gtk.MenuItem(label="顯示視窗 (Show)")
        show_item.connect("activate", lambda x: self.show_window())
        menu.append(show_item)

        hide_item = Gtk.MenuItem(label="隱藏視窗 (Hide)")
        hide_item.connect("activate", lambda x: self.hide())
        menu.append(hide_item)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label="結束服務 (Quit Daemon)")
        quit_item.connect("activate", self.on_quit)
        menu.append(quit_item)

        menu.show_all()
        self.indicator.set_menu(menu)

    def show_window(self):
        """顯示視窗"""
        self.show_all()
        self.present()

    def on_quit(self, widget):
        """退出程式"""
        # 關閉 socket
        if hasattr(self, 'socket_path') and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        Gtk.main_quit()

    def on_window_clicked(self, widget, event):
        """當窗口被點擊時，確保它獲得焦點

        這樣可以讓窗口在背景時也能響應按鈕點擊
        """
        self.present()
        return False  # 讓事件繼續傳播到子控件（按鈕等）

    def on_header_enter(self, widget, event):
        """滑鼠進入 header - 顯示拖拽游標"""
        win_x, win_y = self.get_position()
        window_rel_x = event.x_root - win_x
        window_rel_y = event.y_root - win_y
        if self.config["window"]["resizable"]:
            edge = self.get_edge_at_position(window_rel_x, window_rel_y)
            if edge:
                return False
        gdk_window = widget.get_window()
        if gdk_window:
            cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), Gdk.CursorType.FLEUR)
            gdk_window.set_cursor(cursor)
        return False

    def on_header_leave(self, widget, event):
        """滑鼠離開 header - 恢復游標"""
        gdk_window = widget.get_window()
        if gdk_window:
            gdk_window.set_cursor(None)
        return False

    def on_drag_start(self, widget, event):
        """開始拖拉"""
        if event.button == 1:  # 左鍵
            # 檢查是否在邊緣區域（調整大小優先）
            win_x, win_y = self.get_position()
            window_rel_x = event.x_root - win_x
            window_rel_y = event.y_root - win_y
            if self.config["window"]["resizable"]:
                edge = self.get_edge_at_position(window_rel_x, window_rel_y)
                if edge:
                    return False  # 讓 resize 處理
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

    def get_edge_at_position(self, x, y):
        """檢測滑鼠位置是否在視窗邊緣"""
        width, height = self.get_size()
        edge = self.edge_size
        at_left = x <= edge
        at_right = x >= width - edge
        at_top = y <= edge
        at_bottom = y >= height - edge

        if at_top and at_left: return 'nw'
        if at_top and at_right: return 'ne'
        if at_bottom and at_left: return 'sw'
        if at_bottom and at_right: return 'se'
        if at_top: return 'n'
        if at_bottom: return 's'
        if at_left: return 'w'
        if at_right: return 'e'
        return None

    def get_cursor_for_edge(self, edge):
        """根據邊緣位置返回游標類型"""
        cursor_map = {
            'n': Gdk.CursorType.TOP_SIDE,
            's': Gdk.CursorType.BOTTOM_SIDE,
            'e': Gdk.CursorType.RIGHT_SIDE,
            'w': Gdk.CursorType.LEFT_SIDE,
            'ne': Gdk.CursorType.TOP_RIGHT_CORNER,
            'nw': Gdk.CursorType.TOP_LEFT_CORNER,
            'se': Gdk.CursorType.BOTTOM_RIGHT_CORNER,
            'sw': Gdk.CursorType.BOTTOM_LEFT_CORNER,
        }
        return cursor_map.get(edge)

    def on_window_motion(self, widget, event):
        """視窗滑鼠移動 - 游標變化和調整大小"""
        if not self.config["window"]["resizable"]:
            return False

        if self.is_resizing:
            if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
                self.is_resizing = False
                self.resize_edge = None
                gdk_window = self.get_window()
                if gdk_window:
                    gdk_window.set_cursor(None)
                return False
            self.do_resize(event)
            return True

        edge = self.get_edge_at_position(event.x, event.y)
        gdk_window = self.get_window()
        if gdk_window:
            if edge:
                cursor_type = self.get_cursor_for_edge(edge)
                cursor = Gdk.Cursor.new_for_display(Gdk.Display.get_default(), cursor_type)
                gdk_window.set_cursor(cursor)
            else:
                gdk_window.set_cursor(None)
        return False

    def on_window_button_press(self, widget, event):
        """視窗滑鼠按下 - 開始調整大小"""
        if event.button != 1 or not self.config["window"]["resizable"]:
            return False
        edge = self.get_edge_at_position(event.x, event.y)
        if edge:
            self.is_resizing = True
            self.resize_edge = edge
            self.resize_start_x = event.x_root
            self.resize_start_y = event.y_root
            self.resize_start_width, self.resize_start_height = self.get_size()
            self.resize_start_win_x, self.resize_start_win_y = self.get_position()
            return True
        return False

    def on_window_button_release(self, widget, event):
        """視窗滑鼠釋放 - 結束調整大小"""
        if event.button == 1 and self.is_resizing:
            self.is_resizing = False
            self.resize_edge = None
            gdk_window = self.get_window()
            if gdk_window:
                gdk_window.set_cursor(None)
            return True
        return False

    def do_resize(self, event):
        """執行調整大小"""
        if not self.resize_edge:
            return
        delta_x = event.x_root - self.resize_start_x
        delta_y = event.y_root - self.resize_start_y
        min_width = self.config["window"]["min_width"]
        min_height = self.config["window"]["min_height"]
        new_width = self.resize_start_width
        new_height = self.resize_start_height
        new_x = self.resize_start_win_x
        new_y = self.resize_start_win_y
        edge = self.resize_edge

        if 'e' in edge:
            new_width = max(min_width, self.resize_start_width + delta_x)
        if 'w' in edge:
            proposed = self.resize_start_width - delta_x
            if proposed >= min_width:
                new_width = proposed
                new_x = self.resize_start_win_x + delta_x
        if 's' in edge:
            new_height = max(min_height, self.resize_start_height + delta_y)
        if 'n' in edge:
            proposed = self.resize_start_height - delta_y
            if proposed >= min_height:
                new_height = proposed
                new_y = self.resize_start_win_y + delta_y

        self.resize(int(new_width), int(new_height))
        self.move(int(new_x), int(new_y))

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
                error_dialog.hide()
                error_dialog.destroy()
        else:
            # 取消時恢復原始設定
            dialog.restore_original_settings()

        # 先隱藏再銷毀，避免合成器的淡出動畫
        dialog.hide()
        dialog.destroy()

    def add_notification(self, title, message, urgency="normal", sound=None, metadata=None, card_version=3, notification_data=None):
        """新增通知

        Args:
            card_version: 0 = V0, 1 = V1, 2 = V2, 3 = V3（優化版面）
            notification_data: 完整的通知資料（用於 focus 功能）
        """
        # 檢查是否超過上限，清理最舊的通知
        max_notif = self.config.get("behavior", {}).get("max_notifications", 50)
        while len(self.notifications) >= max_notif:
            oldest = self.notifications[0]
            self.remove_notification(oldest)
            oldest.destroy()  # 確保 GTK widget 被銷毀，釋放資源

        # 播放音效
        if sound:
            self.play_sound(sound)

        # 建立通知卡片（根據版本選擇）
        if card_version == 3:
            card = NotificationCardV3(title, message, urgency, self.remove_notification, metadata, notification_data, self.focus_manager)
        elif card_version == 2:
            card = NotificationCardV2(title, message, urgency, self.remove_notification, metadata)
        elif card_version == 1:
            card = NotificationCardV1(title, message, urgency, self.remove_notification, metadata)
        else:
            card = NotificationCard(title, message, urgency, self.remove_notification)

        self.notifications.append(card)

        # 加入容器（最新的在最上面）
        # 使用 expand=False, fill=True 讓卡片填滿容器寬度，但不增加額外高度
        self.notification_box.pack_start(card, False, True, 0)
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
        self.socket_server = None
        self.socket_healthy = True

        def server_thread():
            # 移除舊的 socket
            if os.path.exists(SOCKET_PATH):
                os.remove(SOCKET_PATH)

            self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket_server.bind(SOCKET_PATH)
            self.socket_server.listen(5)

            while True:
                try:
                    conn, _ = self.socket_server.accept()
                    try:
                        data = conn.recv(4096).decode('utf-8')
                        if data:
                            notification_data = json.loads(data)
                            GLib.idle_add(self.handle_notification, notification_data)
                    finally:
                        conn.close()
                except Exception as e:
                    debug_log("❌ Socket server error", {"error": str(e)})
                    self.socket_healthy = False
                    break

        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()

        # 啟動 health check watchdog
        GLib.timeout_add_seconds(30, self.check_socket_health)

    def check_socket_health(self):
        """定期檢查 socket 是否健康，異常時自動重啟"""
        try:
            # 嘗試連線測試
            test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_sock.settimeout(2)
            test_sock.connect(SOCKET_PATH)
            test_sock.close()
            debug_log("✅ Socket health check passed")
            return True  # 繼續定時檢查
        except Exception as e:
            debug_log("⚠️ Socket health check failed, restarting...", {"error": str(e)})
            self.restart_socket_server()
            return True  # 繼續定時檢查

    def restart_socket_server(self):
        """重啟 socket server"""
        debug_log("🔄 Restarting socket server...")

        # 關閉舊的 socket
        if self.socket_server:
            try:
                self.socket_server.close()
            except:
                pass

        # 移除舊的 socket 檔案
        if os.path.exists(SOCKET_PATH):
            try:
                os.remove(SOCKET_PATH)
            except:
                pass

        # 重新啟動
        self.socket_healthy = True
        self.start_socket_server()

    def handle_notification(self, hook_data):
        """處理通知資料"""
        # 記錄接收到的原始資料（完整的 JSON）
        debug_log("🔔 接收到新通知", hook_data)

        # 讀取所有可用欄位
        cwd = hook_data.get("cwd", "")
        message = hook_data.get("message", "")  # 不設預設值，保持原樣
        notification_type = hook_data.get("notification_type", "")
        session_id = hook_data.get("session_id", "")
        hook_event_name = hook_data.get("hook_event_name", "")
        transcript_path = hook_data.get("transcript_path", "")

        # 記錄關鍵欄位的解析結果
        debug_log("📋 解析欄位", {
            "message": message,
            "message_length": len(message) if message else 0,
            "notification_type": notification_type,
            "session_id": session_id,
            "hook_event_name": hook_event_name,
            "transcript_path": transcript_path,
            "cwd": cwd
        })

        # 專案名稱
        # 從 cwd 向上查找，找到編碼後與 transcript_path 中的專案路徑相同的目錄
        # transcript_path 格式: ~/.claude/projects/-home-ubuntu-Projects-ken-onexas/xxx.jsonl
        # 編碼規則：把 / 換成 -，去掉開頭 /（如 /home/ubuntu → -home-ubuntu）
        project_name = None
        if transcript_path and cwd:
            try:
                # 從 transcript_path 提取編碼後的專案路徑
                parts = transcript_path.split("/")
                encoded_path = None
                for i, part in enumerate(parts):
                    if part == "projects" and i + 1 < len(parts):
                        encoded_path = parts[i + 1]  # 如 -home-ubuntu-Projects-ken-onexas
                        break

                if encoded_path and encoded_path.startswith("-"):
                    # 從 cwd 向上遍歷父目錄，找到編碼後與 encoded_path 相同的目錄
                    current = Path(cwd)
                    while current != current.parent:  # 直到根目錄
                        # 把當前路徑編碼：去掉開頭 /，把 / 換成 -，加上開頭 -
                        current_encoded = "-" + str(current)[1:].replace("/", "-")
                        if current_encoded == encoded_path:
                            project_name = current.name
                            break
                        current = current.parent
            except Exception as e:
                debug_log("⚠️ 從 transcript_path 推斷專案名稱失敗", {"error": str(e)})

        # Fallback 到 cwd
        if not project_name:
            if cwd:
                project_name = cwd.split("/")[-1]
            else:
                project_name = "Claude Code"

        # 時間戳（優先使用通知中的 timestamp，否則使用當前時間）
        timestamp = hook_data.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

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
                if "permissionrequest" in event_lower:
                    # PermissionRequest hook event - 權限請求
                    icon = "🔓"
                    title_v0 = f"{icon} [{project_name}] Permission Request"
                    title_v1 = f"{icon} Permission Request"
                    urgency = "critical"
                    sound = "dialog-warning"
                elif "notification" in event_lower:
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

                # 只有非 PermissionRequest 才在這裡設定 title 和預設 urgency/sound
                if "permissionrequest" not in event_lower:
                    title_v0 = f"{icon} [{project_name}] {hook_event_name}"
                    title_v1 = f"{icon} {hook_event_name}"
                    urgency = "normal"
                    sound = "message-new-instant"
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

        # 完整的通知資料（用於 focus 功能）
        notification_data = {
            "cwd": cwd,
            "message": message,
            "notification_type": notification_type,
            "session_id": session_id,
            "hook_event_name": hook_event_name,
            "transcript_path": transcript_path,
            "project_name": project_name,
            "timestamp": timestamp
        }

        # 新增通知（使用 V3 版本）
        self.add_notification(title_v1, body_v1, urgency, sound, metadata, card_version=3, notification_data=notification_data)


def detect_display_environment():
    """偵測並設定正確的顯示環境

    自動偵測 DISPLAY 和 GDK_BACKEND，支援：
    - X11 (傳統 X Window)
    - Wayland (新一代顯示協議)
    - XWayland (Wayland 下的 X11 相容層)

    Returns:
        dict: 偵測結果資訊
    """
    info = {
        "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown"),
        "display_before": os.environ.get("DISPLAY", ""),
        "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
        "gdk_backend_before": os.environ.get("GDK_BACKEND", ""),
        "actions": []
    }

    # 1. 偵測 session 類型
    session_type = info["session_type"]

    # 2. 處理 DISPLAY
    if not os.environ.get("DISPLAY"):
        # 嘗試找到可用的 X11 display
        for display in [":0", ":1", ":2"]:
            socket_path = f"/tmp/.X11-unix/X{display[1:]}"
            if os.path.exists(socket_path):
                os.environ["DISPLAY"] = display
                info["actions"].append(f"Set DISPLAY={display} (found X11 socket)")
                break
        else:
            # Fallback
            os.environ["DISPLAY"] = ":0"
            info["actions"].append("Set DISPLAY=:0 (fallback)")

    # 3. 處理 GDK_BACKEND
    # 只在沒有設定時才介入，尊重用戶的設定
    if not os.environ.get("GDK_BACKEND"):
        if session_type == "wayland" and info["wayland_display"]:
            # Wayland session，讓 GTK 自動選擇（優先 Wayland）
            # 不強制設定，GTK 會自己處理
            info["actions"].append("GDK_BACKEND not set, letting GTK auto-detect (Wayland session)")
        elif session_type == "x11" or os.environ.get("DISPLAY"):
            # X11 session 或有 DISPLAY，不需要特別設定
            info["actions"].append("GDK_BACKEND not set, letting GTK auto-detect (X11 session)")
        else:
            info["actions"].append("GDK_BACKEND not set, no session detected")

    # 4. 防止意外使用 Broadway（Web 渲染後端）
    # Broadway 通常是透過 broadwayd 啟動，會設定特殊的環境變數
    if os.environ.get("GDK_BACKEND") == "broadway" or os.environ.get("BROADWAY_DISPLAY"):
        # 如果偵測到 Broadway 但實際上有正常的 display，優先使用
        if info["wayland_display"]:
            os.environ["GDK_BACKEND"] = "wayland"
            info["actions"].append("Overrode Broadway with Wayland backend")
        elif os.environ.get("DISPLAY"):
            os.environ["GDK_BACKEND"] = "x11"
            info["actions"].append("Overrode Broadway with X11 backend")

    info["display_after"] = os.environ.get("DISPLAY", "")
    info["gdk_backend_after"] = os.environ.get("GDK_BACKEND", "auto")

    return info


def setup_crash_logging():
    """將 stderr 導向 crash log 檔案，用於追蹤未捕獲的異常和 GTK 錯誤"""
    import sys
    DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 輪替：超過 2MB 就備份
    max_size = 2 * 1024 * 1024
    if CRASH_LOG_FILE.exists() and CRASH_LOG_FILE.stat().st_size > max_size:
        backup = CRASH_LOG_FILE.with_suffix('.log.1')
        if backup.exists():
            backup.unlink()
        CRASH_LOG_FILE.rename(backup)

    crash_fd = open(CRASH_LOG_FILE, 'a', encoding='utf-8')
    # 寫入啟動標記
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    crash_fd.write(f"\n{'='*60}\n")
    crash_fd.write(f"[{timestamp}] Daemon started (PID {os.getpid()})\n")
    crash_fd.flush()
    sys.stderr = crash_fd
    return crash_fd


def main():
    """主程式"""
    # 設定 crash log — 捕獲所有 stderr 輸出（含 GTK 警告、未捕獲異常）
    crash_fd = setup_crash_logging()

    try:
        # 偵測並設定顯示環境
        display_info = detect_display_environment()

        # 記錄環境偵測結果
        debug_log("🖥️ 顯示環境偵測", display_info)

        if display_info["actions"]:
            for action in display_info["actions"]:
                print(f"Display setup: {action}")

        container = NotificationContainer()
        container.show_all()
        container.hide()  # 一開始隱藏，等有通知才顯示

        Gtk.main()
    except Exception as e:
        # 頂層 exception handler — 確保 crash 被記錄
        import traceback
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        crash_msg = f"\n[{timestamp}] ❌ FATAL: Unhandled exception\n{traceback.format_exc()}\n"
        try:
            crash_fd.write(crash_msg)
            crash_fd.flush()
        except:
            pass
        debug_log("❌ FATAL: Daemon crashed", {"error": str(e), "traceback": traceback.format_exc()})
        raise
    finally:
        try:
            crash_fd.close()
        except:
            pass


if __name__ == "__main__":
    main()
