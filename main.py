import os
import sys
import json
import secrets
import string
import time
import subprocess
import threading
import queue
import urllib.request
import urllib.error
from PIL import Image, ImageStat
import win32api
import win32con
import darkdetect
import pywinstyles
from hPyT import title_bar_color

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QButtonGroup, QStackedWidget,
    QPlainTextEdit, QMessageBox, QDialog, QLineEdit, QFormLayout
)
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QIcon, QFont, QPixmap, QDesktopServices
from PySide6.QtCore import QUrl

if getattr(sys, 'frozen', False):
    WORK_PATH = os.path.dirname(sys.executable)
    DATA_PATH = sys._MEIPASS
else:
    WORK_PATH = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = WORK_PATH

class Log:
    def __init__(self):
        self.log_path = os.path.join(WORK_PATH, "log", "log.txt")
        if not os.path.exists(self.log_path):
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding='utf-8') as file:
            pass
        self.logs = []

    def logging(self, content="", type_="[INFO]", owner="[APP]"):
        self.logs.append(f"{type_}{owner}[{time.strftime('%H:%M:%S')}]:{content}\n")
        with open(self.log_path, "a", encoding='utf-8') as file:
            file.write(self.logs[-1])

def get_wallpaper():
    try:
        key = win32api.RegOpenKeyEx(
            win32con.HKEY_CURRENT_USER,
            "Control Panel\\Desktop",
            0, win32con.KEY_READ
        )
        wallpaper_path, _ = win32api.RegQueryValueEx(key, "WallPaper")
        win32api.RegCloseKey(key)
        if wallpaper_path and os.path.exists(wallpaper_path):
            img = Image.open(wallpaper_path)
            try:
                return img.convert("RGB")
            finally:
                img.close()
    except Exception:
        pass
    return None

def is_light_theme():
    try:
        return darkdetect.isLight()
    except Exception:
        return True

def mix_color(c1, c2, ratio=0.5):
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(r1 * (1 - ratio) + r2 * ratio)
    g = int(g1 * (1 - ratio) + g2 * ratio)
    b = int(b1 * (1 - ratio) + b2 * ratio)
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

_cached_avg = None

def _load_avg_color():
    global _cached_avg
    if _cached_avg is not None:
        return _cached_avg
    img = get_wallpaper()
    if img is None:
        _cached_avg = (0, 120, 212)
    else:
        try:
            stat = ImageStat.Stat(img)
            _cached_avg = tuple(int(v) for v in stat.mean)
        finally:
            img.close()
    return _cached_avg

def get_avg_wallpaper_color():
    return '#{:02x}{:02x}{:02x}'.format(*_load_avg_color())

def calc_mica_color(factor=0.82):
    avg_r, avg_g, avg_b = _load_avg_color()
    light = is_light_theme()
    if light:
        r = int(avg_r * (1 - factor) + 255 * factor)
        g = int(avg_g * (1 - factor) + 255 * factor)
        b = int(avg_b * (1 - factor) + 255 * factor)
    else:
        r = int(avg_r * (1 - factor))
        g = int(avg_g * (1 - factor))
        b = int(avg_b * (1 - factor))
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

VERSION = "107-alpha"

_VERSION_SUFFIX = {"fable": 4, "gamma": 3, "beta": 2, "alpha": 1}

def compare_versions(v1, v2):
    parts1 = v1.split("-", 1)
    parts2 = v2.split("-", 1)
    n1, s1 = int(parts1[0]), _VERSION_SUFFIX.get(parts1[1] if len(parts1) > 1 else "", 0)
    n2, s2 = int(parts2[0]), _VERSION_SUFFIX.get(parts2[1] if len(parts2) > 1 else "", 0)
    if n1 != n2:
        return n1 - n2
    return s1 - s2
CONFIG_PATH = os.path.join(WORK_PATH, "config")

def init_config():
    logs = []
    os.makedirs(CONFIG_PATH, exist_ok=True)
    logs.append(("config 目录已就绪", "[INFO]", "[INIT]"))

    config_file = os.path.join(CONFIG_PATH, "config.json")
    if not os.path.exists(config_file):
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump({}, f)
        logs.append(("config.json 已创建", "[INFO]", "[INIT]"))
    else:
        logs.append(("config.json 已存在", "[INFO]", "[INIT]"))
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "apikey" not in config or not isinstance(config["apikey"], str) or len(config["apikey"]) < 8:
        length = secrets.randbelow(57) + 8
        alphabet = string.ascii_letters + string.digits
        config["apikey"] = "".join(secrets.choice(alphabet) for _ in range(length))
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logs.append((f"apikey 已生成 ({len(config['apikey'])} 位)", "[INFO]", "[INIT]"))
    else:
        logs.append(("apikey 已存在", "[INFO]", "[INIT]"))

    server_file = os.path.join(CONFIG_PATH, "server.json")
    if not os.path.exists(server_file):
        default_servers = [
            {"name": "上海", "ip": "122.51.108.96"},
            {"name": "成都", "ip": "162.14.105.219"}
        ]
        with open(server_file, "w", encoding="utf-8") as f:
            json.dump(default_servers, f, indent=2, ensure_ascii=False)
        logs.append(("server.json 已创建（含默认服务器）", "[INFO]", "[INIT]"))
    else:
        logs.append(("server.json 已存在", "[INFO]", "[INIT]"))

    tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
    if not os.path.exists(tunnels_file):
        with open(tunnels_file, "w", encoding="utf-8") as f:
            json.dump([], f)
        logs.append(("tunnels.json 已创建", "[INFO]", "[INIT]"))
    else:
        logs.append(("tunnels.json 已存在", "[INFO]", "[INIT]"))

    return logs

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        init_logs = init_config()

        frpc = os.path.join(WORK_PATH, "frp", "frpc.exe")
        if not os.path.exists(frpc):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("启动失败")
            msg.setText("未找到 frp/frpc.exe")
            msg.setInformativeText("请重新下载 frp 客户端")
            ok_btn = msg.addButton("确定（前往下载）", QMessageBox.AcceptRole)
            close_btn = msg.addButton("关闭程序", QMessageBox.RejectRole)
            msg.setDefaultButton(close_btn)
            msg.exec()
            if msg.clickedButton() == ok_btn:
                QDesktopServices.openUrl(QUrl("https://shithub.site"))
            import sys
            sys.exit(0)

        self.log = Log()
        for msg in init_logs:
            self.log.logging(*msg)
        self.log.logging("窗口初始化", owner="[INIT]")

        self.setWindowTitle("红石联机")
        try:
            self.setWindowIcon(QIcon(os.path.join(DATA_PATH, "icon.ico")))
        except Exception:
            pass

        screen = QApplication.primaryScreen().size()
        self._win_w = screen.width() // 3
        self._win_h = screen.height() // 3
        x = (screen.width() - self._win_w) // 2
        y = (screen.height() - self._win_h) // 2
        self.setGeometry(x, y, self._win_w, self._win_h)
        self.setFixedSize(self._win_w, self._win_h)

        self.active_color = calc_mica_color(0.82)
        self.inactive_color = calc_mica_color(0.9)
        self.nav_items = ["联机", "日志", "服务器", "版本"]

        self._setup_ui()
        self._apply_styles(self.active_color)
        self._activate(0)

        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(1000)

        try:
            pywinstyles.apply_style(self, "dark")
        except Exception:
            pass

        try:
            title_bar_color.set(int(self.winId()), self.active_color)
        except Exception:
            pass

        self._latest_version = None
        QTimer.singleShot(3000, self._check_update)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                self._apply_styles(self.active_color)
                try:
                    title_bar_color.set(int(self.winId()), self.active_color)
                except Exception:
                    pass
            else:
                self._apply_styles(self.inactive_color)
                try:
                    title_bar_color.set(int(self.winId()), self.inactive_color)
                except Exception:
                    pass
        super().changeEvent(event)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_w = self._win_w * 9 // 40
        sidebar = QWidget()
        sidebar.setFixedWidth(nav_w)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(4)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.btn_group.idClicked.connect(self._on_nav_clicked)

        for i, text in enumerate(self.nav_items):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            self.btn_group.addButton(btn, i)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)

        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        title_font = QFont("Microsoft YaHei", 18)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        content_layout.addWidget(self.title_label)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)

        for i in range(len(self.nav_items)):
            self.stack.addWidget(QWidget())

        self._build_log_page()
        self._build_connect_page()
        self._build_server_page()
        self._build_version_page()

        main_layout.addWidget(content, 1)

    def _build_connect_page(self):
        page = self.stack.widget(0)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        info_frame = QFrame()
        info_frame.setObjectName("connectInfo")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(6)

        info_layout.addWidget(QLabel("房间信息"))
        sep = QFrame()
        sep.setObjectName("connSep")
        sep.setFixedHeight(1)
        info_layout.addWidget(sep)

        def info_row(label, widget):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch()
            row.addWidget(widget)
            info_layout.addLayout(row)

        self._conn_server = QLabel("--")
        self._conn_ip = QLabel("--")
        self._conn_latency = QLabel("未检测")
        self._conn_refresh_btn = QPushButton("刷新")
        self._conn_addr = QLabel("--")
        self._conn_copy_btn = QPushButton("复制")
        self._conn_proto = QLabel("TCP")
        self._conn_uptime = QLabel("--")

        info_row("服务器:", self._conn_server)
        info_row("IP:", self._conn_ip)
        row = QHBoxLayout()
        row.addWidget(QLabel("延迟:"))
        row.addWidget(self._conn_latency)
        row.addStretch()
        row.addWidget(self._conn_refresh_btn)
        info_layout.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("联机地址:"))
        row2.addWidget(self._conn_addr)
        row2.addStretch()
        row2.addWidget(self._conn_copy_btn)
        info_layout.addLayout(row2)
        info_row("协议:", self._conn_proto)
        info_row("已运行:", self._conn_uptime)

        layout.addWidget(info_frame)
        layout.addStretch()

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("端口:"))
        self._conn_port = QLineEdit()
        self._conn_port.setPlaceholderText("输入端口号")
        port_layout.addWidget(self._conn_port)
        layout.addLayout(port_layout)

        self._conn_btn = QPushButton("创建房间")
        self._conn_btn.setObjectName("connBtn")
        self._conn_btn.clicked.connect(self._toggle_room)
        layout.addWidget(self._conn_btn)

        self._conn_refresh_btn.clicked.connect(self._ping_connect_server)
        self._conn_copy_btn.clicked.connect(self._copy_addr)

        self._conn_timer = QTimer(self)
        self._conn_timer.timeout.connect(self._update_uptime)
        self._frpc_monitor = QTimer(self)
        self._frpc_monitor.timeout.connect(self._check_frpc)
        self._room_created = None
        self._room_data = None
        self._frpc_proc = None
        self._tunnel_id = None

        QTimer.singleShot(100, self._refresh_connect_info)
        QTimer.singleShot(200, self._check_existing_tunnel)

    def _refresh_connect_info(self):
        config_file = os.path.join(CONFIG_PATH, "config.json")
        server_file = os.path.join(CONFIG_PATH, "server.json")
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            with open(server_file, "r", encoding="utf-8") as f:
                servers = json.load(f)
        except Exception:
            return
        selected = config.get("selected_server", "")
        for s in servers:
            if s["name"] == selected:
                self._conn_server.setText(s["name"])
                self._conn_ip.setText(s["ip"])
                return
        self._conn_server.setText("--")
        self._conn_ip.setText("--")

    def _ping_connect_server(self):
        ip = self._conn_ip.text()
        if ip == "--":
            return
        import re
        try:
            result = subprocess.run(["ping", "-n", "1", ip],
                                    capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                m = re.search(r"时间[=<]\s*(\d+)\s*ms", line)
                if m:
                    self._conn_latency.setText(f"{m.group(1)}ms")
                    return
                if "TTL=" in line:
                    self._conn_latency.setText("<1ms")
                    return
            self._conn_latency.setText("超时")
        except Exception:
            self._conn_latency.setText("失败")

    def _copy_addr(self):
        text = self._conn_addr.text()
        if text and text != "--":
            QApplication.clipboard().setText(text)

    def _toggle_room(self):
        if self._room_created is not None:
            self._destroy_room()
        else:
            self._create_room()

    def _create_room(self):
        port_text = self._conn_port.text().strip()
        if not port_text.isdigit() or len(port_text) > 5:
            QMessageBox.warning(self, "参数错误", "端口号应为 1-5 位数字")
            return

        ip = self._conn_ip.text()
        if ip == "--":
            QMessageBox.warning(self, "参数错误", "请先选择服务器")
            return

        config_file = os.path.join(CONFIG_PATH, "config.json")
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        apikey = config.get("apikey", "")

        url = f"http://{ip}:3001/api/tunnels"
        self.log.logging(f"创建房间请求: POST {url}")
        req = urllib.request.Request(url, method="POST",
                                     headers={"Authorization": f"Bearer {apikey}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                self.log.logging(f"创建房间响应: {json.dumps(data, ensure_ascii=False)}")
        except urllib.error.HTTPError as e:
            err_log = f"HTTP {e.code}"
            try:
                err_body = e.read()
                try:
                    err = json.loads(err_body)
                    msg = err.get("message", str(e))
                    err_log = json.dumps(err, ensure_ascii=False)
                except Exception:
                    msg = f"HTTP {e.code}"
            finally:
                e.close()
            self.log.logging(f"创建房间失败: {err_log}", type_="[ERROR]")
            QMessageBox.critical(self, "创建失败", msg)
            return
        except Exception as e:
            self.log.logging(f"请求失败: {e}", type_="[ERROR]")
            QMessageBox.critical(self, "请求失败", str(e))
            return

        tunnel_id = data.get("id")
        remote_port = data.get("remote_port")
        server_addr = data.get("server_addr")
        server_port = data.get("server_port")
        self.log.logging(f"隧道信息: id={tunnel_id} remote_port={remote_port} "
                         f"server={server_addr}:{server_port}")

        self._conn_addr.setText(f"{server_addr}:{remote_port}")
        self._room_data = data
        self._tunnel_id = tunnel_id

        frpc_path = os.path.join(WORK_PATH, "frp", "frpc.exe")
        frpc_args = [frpc_path, "tcp",
                     "--proxy-name", f"redstone-{apikey[:8]}",
                     "--local-port", port_text,
                     "--remote-port", str(remote_port),
                     "--server-addr", server_addr,
                     "--server-port", str(server_port)]
        self.log.logging(f"启动 frpc: {' '.join(frpc_args)}")
        try:
            self._frpc_proc = subprocess.Popen(
                frpc_args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._frpc_queue = queue.Queue()
            def frpc_reader():
                for line in iter(self._frpc_proc.stdout.readline, b''):
                    self._frpc_queue.put(line)
                self._frpc_proc.stdout.close()
            threading.Thread(target=frpc_reader, daemon=True).start()
            self.log.logging(f"frpc PID: {self._frpc_proc.pid}")
        except Exception as e:
            self.log.logging(f"frpc 启动失败: {e}", type_="[ERROR]")
            QMessageBox.critical(self, "启动失败", f"frpc 启动失败: {e}")
            self._destroy_room(api=False)
            return

        self._room_created = time.time()
        self._conn_btn.setText("销毁房间")
        self._conn_port.setEnabled(False)
        self._conn_timer.start(1000)
        self._frpc_monitor.start(3000)

        tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
        try:
            with open(tunnels_file, "r", encoding="utf-8") as f:
                tunnels = json.load(f)
        except Exception:
            tunnels = []
        tunnels.append({"tunnel_id": tunnel_id, "ip": ip, "apikey": apikey,
                        "local_port": port_text, "remote_port": remote_port,
                        "server_addr": server_addr, "server_port": server_port,
                        "server_name": self._conn_server.text(),
                        "created_at": self._room_created})
        with open(tunnels_file, "w", encoding="utf-8") as f:
            json.dump(tunnels, f, indent=2, ensure_ascii=False)
        self.log.logging(f"房间已创建: {server_addr}:{remote_port}")

    def _destroy_room(self, api=True):
        if self._frpc_proc is not None:
            try:
                self._frpc_proc.terminate()
                try:
                    self._frpc_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._frpc_proc.kill()
                    try:
                        self._frpc_proc.wait(timeout=2)
                    except Exception:
                        pass
            except Exception:
                pass
            self._frpc_proc = None
        self._frpc_queue = None

        self._frpc_monitor.stop()
        self._conn_timer.stop()

        if api and self._tunnel_id is not None:
            ip = self._conn_ip.text()
            config_file = os.path.join(CONFIG_PATH, "config.json")
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                apikey = config.get("apikey", "")
                url = f"http://{ip}:3001/api/tunnels/{self._tunnel_id}"
                self.log.logging(f"销毁隧道请求: DELETE {url}")
                req = urllib.request.Request(url, method="DELETE",
                                             headers={"Authorization": f"Bearer {apikey}"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = json.loads(resp.read())
                    self.log.logging(f"销毁隧道响应: {json.dumps(result, ensure_ascii=False)}")
            except Exception as e:
                self.log.logging(f"销毁隧道失败: {e}", type_="[ERROR]")

        self._room_created = None
        self._room_data = None
        self._tunnel_id = None
        self._conn_btn.setText("创建房间")
        self._conn_port.setEnabled(True)
        self._conn_addr.setText("--")
        self._conn_uptime.setText("--")
        self._clear_tunnels()
        self.log.logging("房间已销毁")

    def _check_existing_tunnel(self):
        tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
        try:
            with open(tunnels_file, "r", encoding="utf-8") as f:
                tunnels = json.load(f)
        except Exception:
            return
        if not tunnels:
            return
        saved = tunnels[-1]
        ip = saved.get("ip")
        apikey = saved.get("apikey")
        tunnel_id = saved.get("tunnel_id")
        if not ip or not apikey or not tunnel_id:
            return
        url = f"http://{ip}:3001/api/auth/info"
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {apikey}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
        except Exception:
            return
        tunnel = data.get("tunnel")
        if not tunnel or tunnel.get("status") != "active":
            self.log.logging("发现过期隧道记录，已清理")
            self._clear_tunnels()
            return
        self.log.logging(f"发现活跃隧道 id={tunnel_id}")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("发现已有隧道")
        msg.setText(f"服务器 {saved.get('server_addr','')}:{saved.get('remote_port','')} 的隧道仍活跃")
        reconnect_btn = msg.addButton("重新连接", QMessageBox.AcceptRole)
        destroy_btn = msg.addButton("销毁隧道", QMessageBox.RejectRole)
        msg.setDefaultButton(reconnect_btn)
        msg.exec()
        if msg.clickedButton() == reconnect_btn:
            self._restore_tunnel(saved)
        else:
            self._destroy_existing_tunnel(ip, apikey, tunnel_id)

    def _restore_tunnel(self, saved):
        if self._frpc_proc is not None or self._room_created is not None:
            QMessageBox.warning(self, "提示", "请先销毁当前房间再恢复")
            return
        self._tunnel_id = saved["tunnel_id"]
        self._conn_ip.setText(saved.get("ip", ""))
        name = saved.get("server_name", "")
        if not name:
            try:
                with open(os.path.join(CONFIG_PATH, "server.json"), "r", encoding="utf-8") as f:
                    for s in json.load(f):
                        if s["ip"] == saved.get("ip"):
                            name = s["name"]
                            break
            except Exception:
                pass
        self._conn_server.setText(name or "--")
        self._conn_addr.setText(f"{saved['server_addr']}:{saved['remote_port']}")
        self._conn_port.setText(str(saved.get("local_port", "")))
        self._conn_port.setEnabled(False)
        self.log.logging(f"重连隧道: {saved['server_addr']}:{saved['remote_port']}")
        frpc_path = os.path.join(WORK_PATH, "frp", "frpc.exe")
        frpc_args = [frpc_path, "tcp",
                     "--proxy-name", f"redstone-{saved['apikey'][:8]}",
                     "--local-port", str(saved["local_port"]),
                     "--remote-port", str(saved["remote_port"]),
                     "--server-addr", saved["server_addr"],
                     "--server-port", str(saved["server_port"])]
        self.log.logging(f"启动 frpc: {' '.join(frpc_args)}")
        try:
            self._frpc_proc = subprocess.Popen(
                frpc_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self._frpc_queue = queue.Queue()
            def frpc_reader():
                for line in iter(self._frpc_proc.stdout.readline, b''):
                    self._frpc_queue.put(line)
                self._frpc_proc.stdout.close()
            threading.Thread(target=frpc_reader, daemon=True).start()
        except Exception as e:
            self.log.logging(f"frpc 重连失败: {e}", type_="[ERROR]")
            QMessageBox.critical(self, "重连失败", f"frpc 启动失败: {e}")
            return
        self._room_created = saved.get("created_at", time.time())
        self._conn_btn.setText("销毁房间")
        self._conn_timer.start(1000)
        self._frpc_monitor.start(3000)

    def _destroy_existing_tunnel(self, ip, apikey, tunnel_id):
        url = f"http://{ip}:3001/api/tunnels/{tunnel_id}"
        self.log.logging(f"销毁旧隧道: DELETE {url}")
        try:
            req = urllib.request.Request(url, method="DELETE",
                                         headers={"Authorization": f"Bearer {apikey}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                self.log.logging(f"销毁响应: {json.dumps(result, ensure_ascii=False)}")
        except Exception as e:
            self.log.logging(f"销毁旧隧道失败: {e}", type_="[ERROR]")
        self._clear_tunnels()

    def _clear_tunnels(self):
        tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
        with open(tunnels_file, "w", encoding="utf-8") as f:
            json.dump([], f)

    def _check_frpc(self):
        if self._frpc_proc is None:
            return
        try:
            while True:
                line = self._frpc_queue.get_nowait()
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    self.log.logging(text, owner="[FRPC]")
        except queue.Empty:
            pass
        ret = self._frpc_proc.poll()
        if ret is not None:
            self._frpc_monitor.stop()
            self.log.logging(f"frpc 已退出 (code={ret})", type_="[WARN]")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("连接丢失")
            msg.setText("frpc 进程已退出，可能被安全软件拦截")
            msg.setInformativeText("隧道将被销毁")
            msg.exec()
            self._destroy_room()

    def closeEvent(self, event):
        self._destroy_room()
        super().closeEvent(event)

    def _update_uptime(self):
        if self._room_created is not None:
            elapsed = int(time.time() - self._room_created)
            h, r = divmod(elapsed, 3600)
            m, s = divmod(r, 60)
            self._conn_uptime.setText(f"{h}:{m:02d}:{s:02d}")

    def _build_log_page(self):
        page = self.stack.widget(1)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logText")
        layout.addWidget(self.log_text)
        btn = QPushButton("用记事本打开")
        btn.setObjectName("logBtn")
        btn.clicked.connect(self._open_log)
        layout.addWidget(btn)

    def _refresh_log(self):
        try:
            with open(os.path.join(WORK_PATH, "log", "log.txt"), "r", encoding="utf-8") as f:
                content = f.read()
            if content != self.log_text.toPlainText():
                self.log_text.setPlainText(content)
                self.log_text.verticalScrollBar().setValue(
                    self.log_text.verticalScrollBar().maximum()
                )
        except Exception:
            pass

    def _build_server_page(self):
        page = self.stack.widget(2)
        self._server_layout = QVBoxLayout(page)
        self._server_layout.setContentsMargins(0, 0, 0, 0)
        self._server_layout.setSpacing(8)
        self._load_servers()

    def _load_servers(self):
        server_file = os.path.join(CONFIG_PATH, "server.json")
        servers = []
        try:
            with open(server_file, "r", encoding="utf-8") as f:
                servers = json.load(f)
        except Exception:
            pass

        while self._server_layout.count():
            item = self._server_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        try:
            with open(os.path.join(CONFIG_PATH, "config.json"), "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}
        selected = config.get("selected_server", "")

        for s in servers:
            card = self._build_server_card(s["name"], s["ip"], selected == s["name"])
            self._server_layout.addWidget(card)

        add_btn = QPushButton("+ 新增服务器")
        add_btn.setObjectName("addServerBtn")
        add_btn.clicked.connect(self._add_server_dialog)
        self._server_layout.addWidget(add_btn)

        self._server_layout.addStretch()

    def _build_server_card(self, name, ip, is_selected):
        card = QFrame()
        card.setObjectName("serverCard")
        card.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        row1 = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        row1.addWidget(name_label)

        status_label = QLabel("● 已选" if is_selected else "○ 未选")
        status_label.setObjectName("statusLabel")
        row1.addWidget(status_label)
        row1.addStretch()

        ip_label = QLabel(ip)
        ip_label.setObjectName("ipLabel")
        row1.addWidget(ip_label)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        latency_label = QLabel("延迟: 未检测")
        latency_label.setObjectName("latencyLabel")
        row2.addWidget(latency_label)
        row2.addStretch()

        ping_btn = QPushButton("刷新")
        ping_btn.clicked.connect(lambda _, n=name, i=ip, l=latency_label: self._ping_server(i, l))
        row2.addWidget(ping_btn)

        select_btn = QPushButton("选择")
        select_btn.clicked.connect(lambda _, n=name: self._select_server(n))
        row2.addWidget(select_btn)

        register_btn = QPushButton("注册")
        register_btn.clicked.connect(lambda _, n=name, i=ip: self._register_server(n, i))
        row2.addWidget(register_btn)

        layout.addLayout(row2)
        return card

    def _ping_server(self, ip, latency_label):
        import re
        try:
            result = subprocess.run(["ping", "-n", "1", ip],
                                    capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                m = re.search(r"时间[=<]\s*(\d+)\s*ms", line)
                if m:
                    latency_label.setText(f"延迟: {m.group(1)}ms")
                    return
                if "TTL=" in line:
                    latency_label.setText("延迟: <1ms")
                    return
            latency_label.setText("延迟: 超时")
        except Exception:
            latency_label.setText("延迟: 失败")

    def _add_server_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("新增服务器")
        layout = QFormLayout(dialog)
        name_input = QLineEdit()
        ip_input = QLineEdit()
        layout.addRow("地域:", name_input)
        layout.addRow("IP:", ip_input)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)

        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            ip = ip_input.text().strip()
            if not name or not ip:
                return
            server_file = os.path.join(CONFIG_PATH, "server.json")
            with open(server_file, "r", encoding="utf-8") as f:
                servers = json.load(f)
            for s in servers:
                if s["name"] == name:
                    s["ip"] = ip
                    break
            else:
                servers.append({"name": name, "ip": ip})
            with open(server_file, "w", encoding="utf-8") as f:
                json.dump(servers, f, indent=2, ensure_ascii=False)
            self.log.logging(f"新增/更新服务器: {name} {ip}")
            self._load_servers()

    def _select_server(self, name):
        config_file = os.path.join(CONFIG_PATH, "config.json")
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        config["selected_server"] = name
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        self.log.logging(f"已选择服务器: {name}")
        self._load_servers()

    def _register_server(self, name, ip):
        config_file = os.path.join(CONFIG_PATH, "config.json")
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        apikey = config.get("apikey", "")
        url = f"http://{ip}:3001/api/register-key"
        body = json.dumps({"apikey": apikey})
        self.log.logging(f"注册请求 {name}({ip}): POST {body}")
        req = urllib.request.Request(url, data=body.encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                self.log.logging(f"注册响应 {name}: {json.dumps(result, ensure_ascii=False)}")
                self.log.logging(f"注册成功({name}): {result.get('message', '')}")
            self._select_server(name)
        except urllib.error.HTTPError as e:
            err_log = f"HTTP {e.code}"
            try:
                err_body = e.read()
                try:
                    err = json.loads(err_body)
                    err_log = json.dumps(err, ensure_ascii=False)
                    msg = err.get("message", f"HTTP {e.code}")
                except Exception:
                    msg = f"HTTP {e.code}"
            finally:
                e.close()
            self.log.logging(f"注册失败({name}): {err_log}", type_="[ERROR]")
            QMessageBox.critical(self, "注册失败", f"{name}：{msg}")
        except Exception as e:
            self.log.logging(f"注册失败({name}): {e}", type_="[ERROR]")
            QMessageBox.critical(self, "注册失败", f"{name}：{e}")

    def _build_version_page(self):
        page = self.stack.widget(3)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self._ver_cur_label = QLabel(f"V{VERSION}")
        self._ver_cur_label.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
        layout.addWidget(self._ver_cur_label)

        self._ver_latest_label = QLabel("最新版本: 检测中...")
        self._ver_latest_label.setObjectName("verLatestLabel")
        layout.addWidget(self._ver_latest_label)

        layout.addStretch()

        btn = QPushButton("前往官网下载最新版本客户端")
        btn.setObjectName("versionBtn")
        btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://shithub.site")))
        layout.addWidget(btn)

    def _check_update(self):
        url = "http://43.139.34.232:3000/api/version"
        self.log.logging(f"检查更新: GET {url}")
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                server_ver = data.get("version", "")
                self.log.logging(f"最新版本: {server_ver}")
        except Exception as e:
            self.log.logging(f"检查更新失败: {e}", type_="[WARN]")
            self._ver_latest_label.setText("最新版本: 获取失败")
            return

        self._latest_version = server_ver
        display = f"V{server_ver}" if server_ver else "未知"
        self._ver_latest_label.setText(f"最新版本: {display}")

        if server_ver and compare_versions(server_ver, VERSION) > 0:
            self.log.logging(f"发现新版本 V{server_ver}，当前 V{VERSION}")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("发现新版本")
            msg.setText(f"最新版本: V{server_ver}")
            msg.setInformativeText(f"当前版本: V{VERSION}\n是否下载更新？")
            update_btn = msg.addButton("立即更新", QMessageBox.AcceptRole)
            msg.addButton("稍后再说", QMessageBox.RejectRole)
            msg.setDefaultButton(update_btn)
            msg.exec()
            if msg.clickedButton() == update_btn:
                self._run_updater()

    def _run_updater(self):
        updater = os.path.join(WORK_PATH, "update.exe")
        if os.path.exists(updater):
            try:
                subprocess.Popen([updater], creationflags=subprocess.CREATE_NO_WINDOW)
                self.log.logging("启动 update.exe")
                QTimer.singleShot(500, self.close)
                return
            except Exception as e:
                self.log.logging(f"启动 update.exe 失败: {e}", type_="[ERROR]")
        self.log.logging("update.exe 不存在", type_="[ERROR]")
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("更新失败")
        msg.setText("未找到 update.exe")
        msg.setInformativeText("请前往官网下载最新版本")
        ok_btn = msg.addButton("前往下载", QMessageBox.AcceptRole)
        msg.addButton("关闭", QMessageBox.RejectRole)
        msg.setDefaultButton(ok_btn)
        msg.exec()
        if msg.clickedButton() == ok_btn:
            QDesktopServices.openUrl(QUrl("https://shithub.site"))

    def _open_log(self):
        os.startfile(os.path.join(WORK_PATH, "log", "log.txt"))

    def _activate(self, index):
        if hasattr(self, 'btn_group'):
            btn = self.btn_group.button(index)
            if btn:
                btn.setChecked(True)
        self.title_label.setText(self.nav_items[index])
        self.stack.setCurrentIndex(index)

    def _on_nav_clicked(self, index):
        self._activate(index)

    def _apply_styles(self, bg):
        light = is_light_theme()
        fg = "#f0f0f0" if not light else "#1a1a1a"
        hover_bg = mix_color("#ffffff", bg, 0.97) if not light else mix_color("#000000", bg, 0.97)
        active_bg = mix_color("#FFFFFF", bg, 0.95) if not light else mix_color("#000000", bg, 0.95)
        active_bar = get_avg_wallpaper_color()
        if light:
            log_bg = mix_color("#ffffff", bg, 0.8)
            log_fg = "#1a1a1a"
            log_btn_bg = mix_color("#ffffff", bg, 0.5)
        else:
            log_bg = mix_color("#000000", bg, 0.8)
            log_fg = "#f0f0f0"
            log_btn_bg = mix_color("#1e1e1e", bg, 0.5)

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {fg};
                font-family: "Microsoft YaHei", "Segoe UI";
                font-size: 10pt;
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 8px 16px;
                text-align: left;
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {hover_bg};
            }}
            QPushButton:checked {{
                background: {active_bg};
                border-left: 2px solid {active_bar};
            }}
            QLabel#titleLabel {{
                font-size: 18pt;
                font-weight: bold;
            }}
            QPlainTextEdit#logText {{
                background-color: {log_bg};
                color: {log_fg};
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-size: 9pt;
                font-family: "Consolas", "Courier New";
            }}
            QPushButton#logBtn {{
                background-color: {log_btn_bg};
                color: {log_fg};
                border-radius: 6px;
                padding: 8px 20px;
                text-align: center;
                border: none;
            }}
            QPushButton#logBtn:hover, QPushButton#versionBtn:hover {{
                background: {hover_bg};
            }}
            QPushButton#versionBtn {{
                background-color: {log_btn_bg};
                color: {log_fg};
                border-radius: 6px;
                padding: 8px 20px;
                text-align: center;
                border: none;
            }}
            QFrame#serverCard {{
                background-color: {log_bg};
                border-radius: 8px;
                border: 1px solid {hover_bg};
            }}
            QLabel#statusLabel {{
                color: {active_bar};
                font-size: 9pt;
            }}
            QLabel#ipLabel {{
                color: {fg};
                font-size: 9pt;
                font-family: "Consolas", "Courier New";
            }}
            QLabel#latencyLabel {{
                color: {fg};
                font-size: 9pt;
            }}
            QPushButton#addServerBtn {{
                background-color: transparent;
                border: 1px dashed {hover_bg};
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                font-size: 10pt;
            }}
            QPushButton#addServerBtn:hover {{
                background: {hover_bg};
            }}
            QLabel#verLatestLabel {{
                font-size: 10pt;
                color: {fg};
            }}
            QFrame#connectInfo {{
                background-color: {log_bg};
                border-radius: 8px;
            }}
            QFrame#connSep {{
                background-color: {hover_bg};
            }}
            QLineEdit {{
                background-color: {log_bg};
                color: {log_fg};
                border: 1px solid {hover_bg};
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QPushButton#connBtn {{
                background-color: {log_btn_bg};
                color: {log_fg};
                border-radius: 6px;
                padding: 10px;
                text-align: center;
                border: none;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton#connBtn:hover {{
                background: {hover_bg};
            }}

        """)

if __name__ == "__main__":
    import sys
    try:
        app = QApplication(sys.argv)
        window = App()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(e)
