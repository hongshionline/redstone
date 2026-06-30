# -*- coding: utf-8 -*-
"""红石联机的启动入口、配置和公共工具。"""
from __future__ import annotations

import json
import os
import queue
import re
import secrets
import socket
import statistics
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import win32api
    import win32con
except Exception:
    win32api = None
    win32con = None

try:
    import darkdetect
except Exception:
    darkdetect = None

try:
    import pywinstyles
except Exception:
    pywinstyles = None

try:
    from hPyT import title_bar_color
except Exception:
    title_bar_color = None

try:
    from PySide6.QtCore import (
        QEvent,
        QEasingCurve,
        QPoint,
        QRect,
        QSize,
        QTimer,
        QPropertyAnimation,
        QAbstractAnimation,
        Property,
        QUrl,
        Qt,
    )
    from PySide6.QtGui import (
        QColor,
        QDesktopServices,
        QFont,
        QIcon,
        QPainter,
        QPen,
        QPixmap,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QDialog,
        QFormLayout,
        QFrame,
        QGraphicsDropShadowEffect,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    missing = exc.name or "PySide6"
    print("启动失败：缺少 Python 依赖包。")
    print(f"缺少模块：{missing}")
    print("请在项目根目录双击 run.bat，或执行：")
    print("  python -m pip install -r requirements.txt")
    if os.name == "nt":
        try:
            input("按 Enter 退出...")
        except Exception:
            pass
    raise SystemExit(1)

if getattr(sys, "frozen", False):
    WORK_PATH = os.path.dirname(sys.executable)
    DATA_PATH = getattr(sys, "_MEIPASS", WORK_PATH)
else:
    WORK_PATH = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = WORK_PATH

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
VERSION = "108"
CONFIG_PATH = os.path.join(WORK_PATH, "config")
_JSON_LOCK = threading.RLock()


def resource_file(*parts: str) -> str:
    """优先读取可写工作目录；打包程序则回退到资源目录。"""
    work_candidate = os.path.join(WORK_PATH, *parts)
    if os.path.exists(work_candidate):
        return work_candidate
    return os.path.join(DATA_PATH, *parts)


def get_frpc_path() -> str:
    return resource_file("frp", "frpc.exe")


class Log:
    """线程安全、有限大小的本地日志。"""

    def __init__(self) -> None:
        self.log_path = os.path.join(WORK_PATH, "log", "log.txt")
        self.logs: list[str] = []
        self._lock = threading.RLock()
        self._max_memory_lines = 500
        self._max_file_bytes = 512 * 1024
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            Path(self.log_path).touch()
        self._trim_file_if_needed()

    def _trim_file_if_needed(self) -> None:
        try:
            size = os.path.getsize(self.log_path)
            if size <= self._max_file_bytes:
                return
            with open(self.log_path, "rb") as handle:
                handle.seek(max(0, size - self._max_file_bytes // 2))
                data = handle.read()
            newline = data.find(b"\n")
            if newline >= 0:
                data = data[newline + 1 :]
            with open(self.log_path, "wb") as handle:
                handle.write(data)
        except OSError:
            pass

    def logging(self, content: object = "", type_: str = "[INFO]", owner: str = "[APP]") -> None:
        line = f"{type_}{owner}[{time.strftime('%H:%M:%S')}]:{content}\n"
        with self._lock:
            self.logs.append(line)
            if len(self.logs) > self._max_memory_lines:
                del self.logs[: len(self.logs) - self._max_memory_lines]
            try:
                self._trim_file_if_needed()
                with open(self.log_path, "a", encoding="utf-8") as handle:
                    handle.write(line)
            except OSError:
                pass


def get_wallpaper():
    if win32api is None or win32con is None or Image is None:
        return None
    try:
        key = win32api.RegOpenKeyEx(win32con.HKEY_CURRENT_USER, "Control Panel\\Desktop", 0, win32con.KEY_READ)
        wallpaper_path, _ = win32api.RegQueryValueEx(key, "WallPaper")
        win32api.RegCloseKey(key)
        if wallpaper_path and os.path.exists(wallpaper_path):
            return Image.open(wallpaper_path).convert("RGB")
    except Exception:
        return None
    return None


def is_light_theme() -> bool:
    try:
        return bool(darkdetect.isLight()) if darkdetect is not None else True
    except Exception:
        return True


_VERSION_SUFFIX = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3, "final": 4, "stable": 4, "release": 4, "": 4}


def compare_versions(v1: object, v2: object) -> int:
    """比较 107-alpha、107-beta.2、108 等版本；返回 -1 / 0 / 1。"""

    def parse(value: object):
        text = str(value or "").strip().lower().lstrip("v")
        match = re.match(r"^(\d+)(?:[-_.]?([a-z]+))?(?:[-_.]?(\d+))?$", text)
        if not match:
            return (0, 0, 0, text)
        return (
            int(match.group(1)),
            _VERSION_SUFFIX.get(match.group(2) or "", 0),
            int(match.group(3) or 0),
            "",
        )

    left, right = parse(v1), parse(v2)
    return (left > right) - (left < right)


def _load_json(path: str, default, expected_type=None):
    try:
        with _JSON_LOCK, open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if expected_type is not None and not isinstance(data, expected_type):
            return default
        return data
    except Exception:
        return default


def _save_json(path: str, data) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with _JSON_LOCK:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            os.replace(temp_path, path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def is_valid_server_host(value: object) -> bool:
    """仅接受 IPv4、IPv6 或普通主机名，避免配置被误写成 URL/命令。"""
    host = str(value or "").strip()
    if not host or len(host) > 253 or any(char.isspace() for char in host):
        return False
    try:
        socket.inet_pton(socket.AF_INET, host)
        return True
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, host)
        return True
    except OSError:
        pass
    return bool(re.fullmatch(r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", host))


def safe_server_entries(servers) -> list[dict[str, str]]:
    if not isinstance(servers, list):
        return []
    output: list[dict[str, str]] = []
    names: set[str] = set()
    hosts: set[str] = set()
    for item in servers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        host = str(item.get("ip", "")).strip()
        if not name or len(name) > 32 or not is_valid_server_host(host):
            continue
        name_key = name.casefold()
        host_key = host.casefold()
        if name_key in names or host_key in hosts:
            continue
        names.add(name_key)
        hosts.add(host_key)
        output.append({"name": name, "ip": host})
    return output


def init_config() -> list[tuple[str, str, str]]:
    logs: list[tuple[str, str, str]] = []
    os.makedirs(CONFIG_PATH, exist_ok=True)
    logs.append(("config 目录已就绪", "[INFO]", "[INIT]"))

    config_file = os.path.join(CONFIG_PATH, "config.json")
    config = _load_json(config_file, {}, dict)
    if not isinstance(config, dict):
        config = {}
        logs.append(("config.json 格式异常，已重置", "[WARN]", "[INIT]"))

    api_key = str(config.get("apikey", ""))
    if len(api_key) < 16:
        alphabet = string.ascii_letters + string.digits
        config["apikey"] = "".join(secrets.choice(alphabet) for _ in range(40))
        logs.append(("本机联机标识已生成", "[INFO]", "[INIT]"))

    server_file = os.path.join(CONFIG_PATH, "server.json")
    default_servers = [{"name": "上海", "ip": "122.51.108.96"}, {"name": "成都", "ip": "162.14.105.219"}]
    servers = safe_server_entries(_load_json(server_file, default_servers, list))
    if not servers:
        servers = default_servers
        logs.append(("server.json 无有效服务器，已恢复默认服务器", "[WARN]", "[INIT]"))

    selected = str(config.get("selected_server", ""))
    if not any(item["name"] == selected for item in servers):
        config["selected_server"] = servers[0]["name"]
        logs.append((f"默认选择服务器：{servers[0]['name']}", "[INFO]", "[INIT]"))

    tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
    tunnels = _load_json(tunnels_file, [], list)
    if not isinstance(tunnels, list):
        tunnels = []
        logs.append(("tunnels.json 格式异常，已重置", "[WARN]", "[INIT]"))

    _save_json(config_file, config)
    _save_json(server_file, servers)
    _save_json(tunnels_file, tunnels)
    return logs


def run() -> int:
    """程序启动入口。"""
    sys.modules.setdefault("main", sys.modules[__name__])
    from window import App

    app = QApplication(sys.argv)
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    window = App()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
