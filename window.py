# -*- coding: utf-8 -*-
"""红石联机主窗口和交互控制。"""
from __future__ import annotations

from main import *
from main import _load_json, _save_json
from tunnel import *
from tunnel import _decode_process_output
from layout import PanelMixin, JellyButton, MotionCard


class App(PanelMixin, QMainWindow):

    def __init__(self):
        super().__init__()
        init_logs = init_config()

        frpc = get_frpc_path()
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
        self._background_events = queue.Queue()
        self._background_jobs = set()
        self._server_metrics = {}
        self._server_card_widgets = {}
        self._recommended_server_name = ""
        self._quality_loss_streak = 0
        self._quality_state = ""
        self._manual_destroying = False
        self._reconnect_attempt = 0
        self._reconnect_scheduled = False
        self._room_session = None
        self._frpc_start_busy = False
        self._local_port_miss_streak = 0
        self._room_ending_for_liveness = False
        self._background_event_timer = QTimer(self)
        self._background_event_timer.setInterval(40)
        self._background_event_timer.timeout.connect(self._poll_background_events)
        self._background_event_timer.start()

        self.setWindowTitle("红石联机")
        try:
            self.setWindowIcon(QIcon(os.path.join(DATA_PATH, "icon.ico")))
        except Exception:
            pass

        geo = QApplication.primaryScreen().availableGeometry()
        sw, sh = geo.width(), geo.height()
        self._win_w = max(980, min(1180, int(sw * 0.72)))
        self._win_h = max(600, min(760, int(sh * 0.72)))
        x = geo.x() + (sw - self._win_w) // 2
        y = geo.y() + (sh - self._win_h) // 2
        self.setGeometry(x, y, self._win_w, self._win_h)
        self.setMinimumSize(900, 560)

        self.active_color = "#ffffff"
        self.inactive_color = "#f7f7f7"
        self.nav_items = ["联机", "日志", "服务器", "版本", "教程"]
        self._fx_animations = []
        self._ui_animations = []
        self._jelly_base_geometries = {}
        self._jelly_animations = {}
        self._frame_interval_ms = 22
        self._activation_ready = False

        self._setup_ui()
        self._apply_styles(self.active_color)
        self._activate(0)

        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._log_timer.start(1000)

        try:
            pywinstyles.apply_style(self, "light") if pywinstyles is not None else None
        except Exception:
            pass

        try:
            title_bar_color.set(int(self.winId()), self.active_color) if title_bar_color is not None else None
        except Exception:
            pass

        self._latest_version = None
        QTimer.singleShot(3000, self._check_update_async)


    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                self._apply_styles(self.active_color)
                try:
                    title_bar_color.set(int(self.winId()), self.active_color) if title_bar_color is not None else None
                except Exception:
                    pass
            else:
                self._apply_styles(self.inactive_color)
                try:
                    title_bar_color.set(int(self.winId()), self.inactive_color) if title_bar_color is not None else None
                except Exception:
                    pass
        super().changeEvent(event)


    def _refresh_connect_info(self):
        config_file = os.path.join(CONFIG_PATH, "config.json")
        server_file = os.path.join(CONFIG_PATH, "server.json")
        config = _load_json(config_file, {}, dict)
        servers = safe_server_entries(_load_json(server_file, [], list))
        selected = config.get("selected_server", "")
        for srv in servers:
            if srv.get("name") == selected:
                self._conn_server.setText(srv.get("name", "--"))
                self._conn_ip.setText(srv.get("ip", "--"))
                return
        self._conn_server.setText("--")
        self._conn_ip.setText("--")


    def _ping_connect_server(self):
        ip = self._conn_ip.text().strip()
        if ip and ip != "--":
            self._start_server_probe(ip, context="connect_refresh", count=2)


    def _launch_background(self, key, worker, name):
        if key in self._background_jobs:
            return False
        self._background_jobs.add(key)

        def run_worker():
            try:
                worker()
            except Exception as exc:
                self._background_events.put(("background_error", {"key": key, "error": str(exc)}))

        threading.Thread(target=run_worker, name=name, daemon=True).start()
        return True


    def _poll_background_events(self):
        processed = 0
        while processed < 60:
            try:
                kind, payload = self._background_events.get_nowait()
            except queue.Empty:
                break
            processed += 1
            try:
                if kind == "server_probe":
                    self._handle_server_probe(payload)
                elif kind == "server_register":
                    self._handle_server_register(payload)
                elif kind == "update_check":
                    self._handle_update_check(payload)
                elif kind == "existing_tunnel":
                    self._handle_existing_tunnel_check(payload)
                elif kind == "frpc_start":
                    self._handle_frpc_start(payload)
                elif kind == "port_detect":
                    self._handle_port_detect(payload)
                elif kind == "room_liveness":
                    self._handle_room_liveness(payload)
                elif kind == "tunnel_delete":
                    self._handle_tunnel_delete(payload)
                elif kind == "background_error":
                    key = str(payload.get("key", ""))
                    self._background_jobs.discard(key)
                    self.log.logging(f"后台任务失败: {payload.get('error', '')}", type_="[WARN]", owner="[ASYNC]")
            except Exception as exc:
                self.log.logging(f"后台结果处理失败: {exc}", type_="[WARN]", owner="[ASYNC]")


    def _handle_server_register(self, payload):
        ip = str(payload.get("ip", ""))
        self._background_jobs.discard(f"register:{ip}")
        if payload.get("ok"):
            self.log.logging(f"服务器注册成功: {payload.get('name', '')}", owner="[NET]")
            self._select_server(str(payload.get("name", "")))
        else:
            reason = str(payload.get("reason", "") or "服务器拒绝注册")
            self.log.logging(f"服务器注册失败: {reason}", type_="[WARN]", owner="[NET]")
            QMessageBox.warning(self, "服务器", reason)


    @staticmethod
    def _metrics_text(metrics, prefix=""):
        """Render only human-readable probe values; never expose the raw metrics dictionary."""
        prefix = str(prefix or "")
        if not isinstance(metrics, dict):
            return f"{prefix}未检测".strip()
        if not metrics.get("connected"):
            return f"{prefix}连接失败".strip()
        avg = metrics.get("avg_ms")
        try:
            avg_number = float(avg) if avg is not None else None
        except (TypeError, ValueError):
            avg_number = None
        try:
            jitter = max(0, int(float(metrics.get("jitter_ms", 0) or 0)))
        except (TypeError, ValueError):
            jitter = 0
        if avg_number is None:
            latency = "TCP 可达" if metrics.get("tcp_ok") else "连接成功"
        elif avg_number < 1:
            latency = "<1ms"
        else:
            latency = f"{int(round(avg_number))}ms"
        if jitter >= 8:
            latency += f" · 抖动 {jitter}ms"
        return f"{prefix}{latency}".strip()


    def _start_server_probe(self, ip, context="server", count=3):
        ip = str(ip).strip()
        if not ip or ip == "--":
            return
        key = f"probe:{ip}"
        task = ServerProbeTask(ip, context, self._background_events, count=count)
        if self._launch_background(key, task.run, "ServerProbeWorker"):
            if context in ("connect_refresh", "manual"):
                self._conn_latency.setText("检测中...")


    def _start_server_probe_all(self):
        servers = safe_server_entries(_load_json(os.path.join(CONFIG_PATH, "server.json"), [], list))
        for server in servers:
            self._start_server_probe(server["ip"], context="startup", count=3)


    def _update_recommendation(self):
        servers = safe_server_entries(_load_json(os.path.join(CONFIG_PATH, "server.json"), [], list))
        candidates = []
        for server in servers:
            metric = self._server_metrics.get(server["ip"])
            if metric and metric.get("connected"):
                candidates.append((float(metric.get("score", 99999)), server["name"]))
        new_name = min(candidates)[1] if candidates else ""
        if new_name and new_name != self._recommended_server_name:
            self._recommended_server_name = new_name
            self.log.logging(f"测速推荐服务器: {new_name}", owner="[NET]")
        self._refresh_server_metric_widgets()


    def _refresh_server_metric_widgets(self):
        config = _load_json(os.path.join(CONFIG_PATH, "config.json"), {}, dict)
        selected = config.get("selected_server", "")
        for ip, widgets in list(self._server_card_widgets.items()):
            metric = self._server_metrics.get(ip)
            latency_label = widgets.get("latency")
            status_label = widgets.get("status")
            name = widgets.get("name", "")
            if latency_label is not None:
                if metric:
                    latency_label.setText("延迟: " + self._metrics_text(metric))
                else:
                    latency_label.setText("延迟: 未检测")
            if status_label is not None:
                if name == selected and name == self._recommended_server_name:
                    status_label.setText("● 已选 · 推荐")
                elif name == selected:
                    status_label.setText("● 已选")
                elif name == self._recommended_server_name:
                    status_label.setText("★ 推荐")
                else:
                    status_label.setText("○ 未选")


    def _handle_server_probe(self, payload):
        if not isinstance(payload, dict):
            return
        ip = str(payload.get("ip", ""))
        self._background_jobs.discard(f"probe:{ip}")
        metrics = payload.get("metrics")
        if not isinstance(metrics, dict):
            return
        self._server_metrics[ip] = metrics
        self._update_recommendation()
        if ip == self._conn_ip.text().strip():
            self._conn_latency.setText(self._metrics_text(metrics))
        if payload.get("context") == "quality":
            self._handle_connection_quality(metrics)


    def _connection_quality_tick(self):
        if self._room_created is None or self._frpc_proc is None:
            return
        ip = self._room_server_ip or self._conn_ip.text().strip()
        if ip and ip != "--":
            self._start_server_probe(ip, context="quality", count=3)


    def _handle_connection_quality(self, metrics):
        lost = int(metrics.get("loss_pct", 100) or 0)
        avg = metrics.get("avg_ms")
        jitter = int(metrics.get("jitter_ms", 0) or 0)
        tcp_ok = bool(metrics.get("tcp_ok"))
        if lost >= 100 or not metrics.get("connected"):
            self._quality_loss_streak += 1
        else:
            self._quality_loss_streak = 0

        if self._quality_loss_streak >= 2:
            state = "lost"
            message = f"网络质量异常：连续网络探测失败 {self._quality_loss_streak} 次，正在保持隧道并等待网络恢复"
        elif lost >= 34 or (avg is not None and avg >= 250) or jitter >= 80 or not tcp_ok:
            state = "poor"
            stability_note = "连接稳定性下降" if lost >= 34 else "网络波动明显"
            message = f"网络质量较差：{stability_note} · {self._metrics_text(metrics)}"
        else:
            state = "good"
            message = ""
        if state != self._quality_state:
            self._quality_state = state
            if state == "good":
                self.log.logging("网络质量已恢复", owner="[NET]")
            elif message:
                self.log.logging(message, type_="[WARN]", owner="[NET]")


    def _start_room_liveness_monitor(self):
        """房间创建/恢复成功后启动本地 LAN 存活检测。"""
        session = getattr(self, "_room_session", None)
        if not isinstance(session, dict) or not is_valid_port_text(session.get("local_port", "")):
            return
        self._local_port_miss_streak = 0
        self._room_ending_for_liveness = False
        if not self._room_liveness_timer.isActive():
            self._room_liveness_timer.start()
        QTimer.singleShot(250, self._room_liveness_tick)


    def _stop_room_liveness_monitor(self):
        if getattr(self, "_room_liveness_timer", None) is not None:
            self._room_liveness_timer.stop()
        self._local_port_miss_streak = 0


    def _room_liveness_tick(self):
        session = getattr(self, "_room_session", None)
        if self._manual_destroying or self._room_ending_for_liveness or not isinstance(session, dict):
            return
        port = str(session.get("local_port", "")).strip()
        token = str(session.get("token", ""))
        if not is_valid_port_text(port) or not token:
            return
        key = f"room_liveness:{token}"
        task = LocalPortLivenessTask(port, token, self._background_events)
        self._launch_background(key, task.run, "RoomLivenessWorker")


    def _handle_room_liveness(self, payload):
        if not isinstance(payload, dict):
            return
        token = str(payload.get("token", ""))
        self._background_jobs.discard(f"room_liveness:{token}")
        session = getattr(self, "_room_session", None)
        if self._manual_destroying or self._room_ending_for_liveness or not isinstance(session, dict):
            return
        if token != str(session.get("token", "")):
            return

        port = str(payload.get("port") or session.get("local_port", ""))
        if payload.get("alive"):
            if self._local_port_miss_streak:
                self.log.logging(f"本地 Minecraft 局域网端口 {port} 已恢复", owner="[PORT]")
            self._local_port_miss_streak = 0
            return

        self._local_port_miss_streak += 1
        if self._local_port_miss_streak == 1:
            self.log.logging(
                f"未检测到本地 Minecraft 局域网端口 {port}，正在确认房间状态",
                type_="[WARN]",
                owner="[PORT]",
            )
            return

        self._end_room_when_local_port_closed(port)


    def _end_room_when_local_port_closed(self, port):
        """本地世界已关闭时，不再重连 FRP，并后台清理远端隧道。"""
        if self._room_ending_for_liveness:
            return
        session = dict(getattr(self, "_room_session", None) or {})
        if not session:
            return

        self._room_ending_for_liveness = True
        self._manual_destroying = True
        self._stop_room_liveness_monitor()
        self._frpc_monitor.stop()
        self._quality_timer.stop()
        self._conn_timer.stop()
        self._reconnect_scheduled = False
        self._reconnect_attempt = 0
        self._quality_loss_streak = 0
        self._quality_state = ""

        proc = self._frpc_proc
        self._frpc_proc = None
        self._frpc_queue = None
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

        tunnel_id = self._tunnel_id or session.get("tunnel_id")
        ip = self._room_server_ip or session.get("ip") or self._conn_ip.text().strip()
        apikey = str(session.get("apikey", "")).strip()
        if tunnel_id:
            self.log.logging(f"检测到本地 Minecraft 局域网端口 {port} 已关闭，房间已结束", type_="[WARN]", owner="[PORT]")
            self.log.logging(f"正在后台清理已结束房间的隧道: {tunnel_id}", owner="[NET]")
            self._delete_tunnel_async(ip, apikey, tunnel_id, reason="local_port_closed")
        else:
            self.log.logging(f"检测到本地 Minecraft 局域网端口 {port} 已关闭，房间已结束", type_="[WARN]", owner="[PORT]")

        self._room_created = None
        self._room_data = None
        self._room_server_ip = None
        self._tunnel_id = None
        self._room_session = None
        self._conn_btn.setText("创建房间")
        self._conn_btn.setEnabled(True)
        self._conn_port.setEnabled(True)
        self._conn_addr.setText("--")
        self._conn_uptime.setText("--")
        self._clear_tunnels()
        self._manual_destroying = False

        QMessageBox.information(self, "房间已结束", "检测到 Minecraft 局域网已关闭，房间已自动结束。")
        self._room_ending_for_liveness = False


    def _auto_detect_minecraft_port(self, force=False):
        """后台扫描 Minecraft Java LAN 监听端口。

        启动时仅自动填充空输入框；用户点击“识别”时会强制刷新，
        方便在重新开启局域网世界后直接替换旧端口。
        """
        if getattr(self, "_port_detecting", False):
            return
        self._port_detecting = True
        self._port_detect_force = bool(force)
        if hasattr(self, "_conn_detect_port_btn"):
            self._conn_detect_port_btn.setEnabled(False)
            self._conn_detect_port_btn.setText("识别中")
        task = PortDetectTask(self._background_events, force=force)
        if not self._launch_background("port_detect", task.run, "MinecraftPortDetect"):
            self._port_detecting = False
            if hasattr(self, "_conn_detect_port_btn"):
                self._conn_detect_port_btn.setEnabled(True)
                self._conn_detect_port_btn.setText("识别")


    def _handle_port_detect(self, payload):
        self._background_jobs.discard("port_detect")
        self._port_detecting = False
        force = bool(payload.get("force", getattr(self, "_port_detect_force", False))) if isinstance(payload, dict) else False
        if hasattr(self, "_conn_detect_port_btn"):
            self._conn_detect_port_btn.setEnabled(True)
            self._conn_detect_port_btn.setText("识别")
        candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
        if not candidates:
            error = str(payload.get("error", "")).strip() if isinstance(payload, dict) else ""
            if force:
                detail = f"：{error}" if error else ""
                self.log.logging(
                    "未识别到 Minecraft 局域网端口。请先进入世界并在游戏内开启局域网，然后再次点击识别" + detail,
                    type_="[WARN]", owner="[PORT]",
                )
            return

        first = candidates[0] if isinstance(candidates[0], dict) else {}
        port = str(first.get("port", "")).strip()
        if not port:
            return

        old = self._conn_port.text().strip()
        can_replace = force or not old or old == getattr(self, "_auto_detected_port", "")
        if not can_replace:
            self.log.logging(
                f"已发现 Minecraft 局域网端口 {port}，未覆盖当前手动输入的端口 {old}",
                owner="[PORT]",
            )
            return

        self._conn_port.setText(port)
        self._auto_detected_port = port
        process = str(first.get("process") or "javaw.exe")
        source = str(first.get("source") or "Windows 网络接口")
        if len(candidates) > 1:
            alternatives = "、".join(str(item.get("port", "")) for item in candidates[1:4] if isinstance(item, dict))
            suffix = f"；其他候选：{alternatives}" if alternatives else ""
            self.log.logging(
                f"已识别 Minecraft 局域网端口: {port}（{process}，{source}）{suffix}",
                owner="[PORT]",
            )
        else:
            self.log.logging(
                f"已识别 Minecraft 局域网端口: {port}（{process}，{source}）",
                owner="[PORT]",
            )


    def _start_frpc_async(self, session, purpose="reconnect"):
        if not isinstance(session, dict) or self._frpc_start_busy:
            return
        token = str(session.get("token", ""))
        self._frpc_start_busy = True
        task = FrpcStartTask(session, self._background_events)
        if not self._launch_background(f"frpc_start:{token}", task.run, "FrpcStartWorker"):
            self._frpc_start_busy = False


    def _handle_frpc_start(self, payload):
        session = payload.get("session", {}) if isinstance(payload, dict) else {}
        token = str(session.get("token", ""))
        self._background_jobs.discard(f"frpc_start:{token}")
        self._frpc_start_busy = False
        current = getattr(self, "_room_session", None)
        if not current or str(current.get("token", "")) != token or self._manual_destroying:
            proc = payload.get("proc") if isinstance(payload, dict) else None
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            return
        if not payload.get("ok"):
            self.log.logging(f"frpc 自动重连启动失败: {payload.get('error', '')}", type_="[WARN]", owner="[NET]")
            self._schedule_frpc_reconnect("启动失败")
            return
        self._frpc_proc = payload["proc"]
        self._frpc_queue = queue.Queue()
        self._start_frpc_reader(self._frpc_proc, self._frpc_queue)
        self._room_created = self._room_created or current.get("created_at", time.time())
        self._conn_btn.setText("销毁房间")
        self._conn_btn.setEnabled(True)
        self._conn_port.setEnabled(False)
        self._frpc_monitor.start(3000)
        self._quality_timer.start()
        self._start_room_liveness_monitor()
        self._reconnect_attempt = 0
        self._reconnect_scheduled = False
        self.log.logging("frpc 已自动重连", owner="[NET]")


    def _schedule_frpc_reconnect(self, reason):
        session = getattr(self, "_room_session", None)
        if self._manual_destroying or not session or self._reconnect_scheduled:
            return
        self._reconnect_scheduled = True
        self._reconnect_attempt += 1
        delay = min(30, [1, 2, 4, 8, 15, 30][min(self._reconnect_attempt - 1, 5)])
        token = str(session.get("token", ""))
        self.log.logging(f"frpc 连接中断（{reason}），{delay} 秒后第 {self._reconnect_attempt} 次自动重连", type_="[WARN]", owner="[NET]")

        def start_later():
            self._reconnect_scheduled = False
            current = getattr(self, "_room_session", None)
            if self._manual_destroying or not current or str(current.get("token", "")) != token or self._frpc_proc is not None:
                return
            self._start_frpc_async(current, purpose="reconnect")

        QTimer.singleShot(delay * 1000, start_later)


    def _delete_tunnel_async(self, ip, apikey, tunnel_id, reason=""):
        if not ip or not apikey or not tunnel_id:
            return
        key = f"delete:{tunnel_id}"
        task = TunnelDeleteTask(ip, apikey, tunnel_id, self._background_events, reason=reason)
        self._launch_background(key, task.run, "TunnelDeleteWorker")


    def _handle_tunnel_delete(self, payload):
        tunnel_id = str(payload.get("tunnel_id", ""))
        self._background_jobs.discard(f"delete:{tunnel_id}")
        if payload.get("ok"):
            self.log.logging("服务器隧道已清理", owner="[NET]")
        else:
            self.log.logging(f"销毁隧道失败: {payload.get('error', '')}", type_="[WARN]", owner="[NET]")


    def _copy_addr(self):
        text = self._conn_addr.text()
        if text and text != "--":
            QApplication.clipboard().setText(text)


    def _toggle_room(self):
        if self._room_created is not None:
            self._destroy_room()
        else:
            self._create_room()


    def _register_key_silent(self, name, ip, apikey):
        url = f"http://{ip}:3001/api/register-key"
        body = json.dumps({"apikey": apikey})
        self.log.logging(f"注册请求 {name}({ip}): POST {{apikey: ***}}")
        req = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw = resp.read()
                result = json.loads(raw) if raw else {}
                self.log.logging(f"注册响应 {name}: {json.dumps(result, ensure_ascii=False)}")
            return True, ""
        except urllib.error.HTTPError as e:
            raw = ""
            msg = f"HTTP {e.code}"
            try:
                raw = e.read().decode("utf-8", errors="replace")
                err = json.loads(raw) if raw else {}
                msg = err.get("message", msg) if isinstance(err, dict) else raw
                self.log.logging(f"注册失败({name}): {raw}", type_="[ERROR]")
            except Exception:
                self.log.logging(f"注册失败({name}): HTTP {e.code}", type_="[ERROR]")
            low = (msg + raw).lower()
            if e.code in (400, 409) and any(k in low for k in ("already", "exist", "duplicate", "重复", "已存在", "已注册")):
                self.log.logging(f"注册状态可继续({name}): key 已存在")
                return True, ""
            return False, msg
        except Exception as e:
            self.log.logging(f"注册失败({name}): {e}", type_="[ERROR]")
            return False, str(e)


    def _set_creating_state(self, creating):
        try:
            self._creating_room = bool(creating)
            if self._room_created is None:
                self._conn_btn.setEnabled(not creating)
                self._conn_btn.setText("创建中..." if creating else "创建房间")
        except Exception:
            pass


    def _start_frpc_reader(self, proc, out_queue):
        if proc is None or proc.stdout is None:
            return

        def frpc_reader(process, output_queue):
            try:
                for line in iter(process.stdout.readline, b''):
                    if line:
                        output_queue.put(line)
            finally:
                try:
                    process.stdout.close()
                except Exception:
                    pass

        threading.Thread(target=frpc_reader, args=(proc, out_queue), daemon=True).start()


    def _cancel_room_creation(self):
        cancel_event = getattr(self, "_room_create_cancel", None)
        if cancel_event is not None:
            cancel_event.set()


    def _poll_room_create_events(self):
        events = getattr(self, "_room_create_events", None)
        if events is None:
            self._room_create_poll_timer.stop()
            return

        handled = 0
        while handled < 40:
            try:
                kind, *payload = events.get_nowait()
            except queue.Empty:
                break
            handled += 1
            if kind == "log":
                content, type_, owner = payload
                self.log.logging(content, type_=type_, owner=owner)
            elif kind == "result":
                result = payload[0]
                self._room_create_poll_timer.stop()
                self._room_create_events = None
                self._room_create_cancel = None
                self._room_create_thread = None
                self._apply_room_create_result(result)
                break


    def _apply_room_create_result(self, result):
        self._creating_room = False
        if not isinstance(result, dict) or not result.get("ok"):
            if not isinstance(result, dict) or not result.get("cancelled"):
                title = result.get("title", "创建失败") if isinstance(result, dict) else "创建失败"
                message = result.get("message", "创建房间失败") if isinstance(result, dict) else "创建房间失败"
                self.log.logging(f"{title}: {message}", type_="[ERROR]")
                QMessageBox.critical(self, title, message)
            self._set_creating_state(False)
            return

        data = result["data"]
        tunnel_id = result["tunnel_id"]
        remote_port = result["remote_port"]
        server_addr = result["server_addr"]
        server_port = result["server_port"]
        self._room_data = data
        self._room_server_ip = result["ip"]
        self._tunnel_id = tunnel_id
        self._frpc_proc = result["frpc_proc"]
        self._frpc_queue = queue.Queue()
        self._start_frpc_reader(self._frpc_proc, self._frpc_queue)
        self.log.logging(f"frpc PID: {self._frpc_proc.pid}")

        self._conn_addr.setText(f"{server_addr}:{remote_port}")
        self._room_created = time.time()
        self._manual_destroying = False
        self._reconnect_attempt = 0
        self._reconnect_scheduled = False
        self._room_session = {
            "token": secrets.token_hex(8),
            "tunnel_id": tunnel_id,
            "ip": result["ip"],
            "apikey": result["apikey"],
            "local_port": result["port_text"],
            "remote_port": remote_port,
            "server_addr": server_addr,
            "server_port": server_port,
            "server_name": result["server_name"],
            "proxy_name": result.get("proxy_name", ""),
            "created_at": self._room_created,
        }
        self._conn_btn.setText("销毁房间")
        self._conn_btn.setEnabled(True)
        self._conn_port.setEnabled(False)
        self._conn_timer.start(1000)
        self._frpc_monitor.start(3000)
        self._quality_timer.start()
        self._start_room_liveness_monitor()
        QTimer.singleShot(500, self._connection_quality_tick)

        tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
        tunnels = _load_json(tunnels_file, [], list)
        tunnels.append({
            "tunnel_id": tunnel_id,
            "ip": result["ip"],
            "apikey": result["apikey"],
            "local_port": result["port_text"],
            "remote_port": remote_port,
            "server_addr": server_addr,
            "server_port": server_port,
            "server_name": result["server_name"],
            "proxy_name": result.get("proxy_name", ""),
            "created_at": self._room_created,
        })
        _save_json(tunnels_file, tunnels)
        self.log.logging(f"房间已创建: {server_addr}:{remote_port}")
        self.log.logging("已使用独立代理标识，支持多个客户端同时创建房间", owner="[NET]")


    def _create_room(self):
        if getattr(self, "_creating_room", False):
            return

        port_text = self._conn_port.text().strip()
        if not is_valid_port_text(port_text):
            QMessageBox.warning(self, "参数错误", "端口号必须是 1 到 65535 之间的数字")
            return

        ip = self._conn_ip.text().strip()
        if not ip or ip == "--":
            QMessageBox.warning(self, "参数错误", "请先选择服务器")
            return

        config = _load_json(os.path.join(CONFIG_PATH, "config.json"), {}, dict)
        apikey = str(config.get("apikey", "")).strip()
        if not apikey:
            QMessageBox.warning(self, "参数错误", "未找到 apikey，请重启程序后重试")
            return

        self._set_creating_state(True)
        self._room_create_cancel = threading.Event()
        self._room_create_events = queue.Queue()
        server_name = self._conn_server.text() if self._conn_server.text() != "--" else ip
        task = RoomCreateTask(
            port_text=port_text,
            ip=ip,
            apikey=apikey,
            server_name=server_name,
            frpc_path=get_frpc_path(),
            event_queue=self._room_create_events,
            cancel_event=self._room_create_cancel,
        )
        self._room_create_thread = threading.Thread(
            target=task.run,
            name="RoomCreateWorker",
            daemon=True,
        )
        self.log.logging("正在后台创建房间")
        self._room_create_thread.start()
        self._room_create_poll_timer.start()


    def _destroy_room(self, api=True):
        self._manual_destroying = True
        self._cancel_room_creation()
        session = dict(self._room_session or {})
        proc = self._frpc_proc
        self._frpc_proc = None
        self._frpc_queue = None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        self._frpc_monitor.stop()
        self._conn_timer.stop()
        self._quality_timer.stop()
        self._stop_room_liveness_monitor()
        self._reconnect_scheduled = False
        self._reconnect_attempt = 0
        self._quality_loss_streak = 0
        self._quality_state = ""

        tunnel_id = self._tunnel_id or session.get("tunnel_id")
        ip = self._room_server_ip or session.get("ip") or self._conn_ip.text().strip()
        apikey = session.get("apikey")
        if not apikey:
            apikey = str(_load_json(os.path.join(CONFIG_PATH, "config.json"), {}, dict).get("apikey", ""))
        if api and tunnel_id:
            self.log.logging(f"正在后台销毁隧道: {tunnel_id}", owner="[NET]")
            self._delete_tunnel_async(ip, apikey, tunnel_id, reason="manual")

        self._room_created = None
        self._room_data = None
        self._room_server_ip = None
        self._tunnel_id = None
        self._room_session = None
        self._conn_btn.setText("创建房间")
        self._conn_btn.setEnabled(True)
        self._conn_port.setEnabled(True)
        self._conn_addr.setText("--")
        self._conn_uptime.setText("--")
        self._clear_tunnels()
        self.log.logging("房间已销毁")
        self._manual_destroying = False


    def _check_existing_tunnel_async(self):
        tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
        tunnels = _load_json(tunnels_file, [], list)
        if not tunnels:
            return
        saved = tunnels[-1] if isinstance(tunnels[-1], dict) else {}
        task = ExistingTunnelCheckTask(saved, self._background_events)
        self._launch_background("existing_tunnel", task.run, "ExistingTunnelCheck")


    def _handle_existing_tunnel_check(self, payload):
        self._background_jobs.discard("existing_tunnel")
        state = payload.get("state") if isinstance(payload, dict) else "invalid"
        saved = payload.get("saved", {}) if isinstance(payload, dict) else {}
        if state in ("invalid", "expired"):
            self.log.logging("发现过期隧道记录，已清理", owner="[NET]")
            self._clear_tunnels()
            return
        if state == "unreachable":
            self.log.logging("旧隧道检查暂时不可达，保留记录等待下次检查", type_="[WARN]", owner="[NET]")
            return
        if state != "active":
            return
        self.log.logging(f"发现活跃隧道 id={saved.get('tunnel_id', '')}", owner="[NET]")
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
            self._destroy_existing_tunnel(saved.get("ip", ""), saved.get("apikey", ""), saved.get("tunnel_id", ""))


    def _restore_tunnel(self, saved):
        try:
            session = {
                "token": secrets.token_hex(8),
                "tunnel_id": saved["tunnel_id"],
                "ip": saved.get("ip", ""),
                "apikey": saved["apikey"],
                "local_port": str(saved["local_port"]),
                "remote_port": saved["remote_port"],
                "server_addr": saved["server_addr"],
                "server_port": saved["server_port"],
                "server_name": saved.get("server_name", ""),
                "proxy_name": saved.get("proxy_name", ""),
                "created_at": saved.get("created_at", time.time()),
            }
        except Exception:
            self.log.logging("旧隧道记录字段不完整，已清理", type_="[WARN]", owner="[NET]")
            self._clear_tunnels()
            return
        self._tunnel_id = session["tunnel_id"]
        self._room_server_ip = session["ip"]
        self._room_session = session
        self._manual_destroying = False
        self._conn_ip.setText(session["ip"] or "--")
        self._conn_server.setText(session.get("server_name") or "--")
        self._conn_addr.setText(f"{session['server_addr']}:{session['remote_port']}")
        self._conn_port.setText(str(session["local_port"]))
        self._conn_port.setEnabled(False)
        self._conn_btn.setEnabled(False)
        self._conn_btn.setText("重连中...")
        self.log.logging(f"正在后台重连隧道: {session['server_addr']}:{session['remote_port']}", owner="[NET]")
        self._start_frpc_async(session, purpose="restore")


    def _destroy_existing_tunnel(self, ip, apikey, tunnel_id):
        self.log.logging(f"正在后台销毁旧隧道: {tunnel_id}", owner="[NET]")
        self._delete_tunnel_async(ip, apikey, tunnel_id, reason="old")
        self._clear_tunnels()


    def _clear_tunnels(self):
        tunnels_file = os.path.join(CONFIG_PATH, "tunnels.json")
        _save_json(tunnels_file, [])


    def _check_frpc(self):
        if self._frpc_proc is None:
            return
        try:
            for _ in range(60):
                if self._frpc_queue is None:
                    break
                line = self._frpc_queue.get_nowait()
                text = _decode_process_output(line).rstrip()
                if text:
                    self.log.logging(text, owner="[FRPC]")
        except queue.Empty:
            pass
        ret = self._frpc_proc.poll()
        if ret is not None:
            self._frpc_monitor.stop()
            self._frpc_proc = None
            self._frpc_queue = None
            if self._manual_destroying or self._room_session is None:
                return
            self.log.logging(f"frpc 已退出 (code={ret})，将尝试自动重连", type_="[WARN]", owner="[NET]")
            self._schedule_frpc_reconnect(f"退出代码 {ret}")


    def closeEvent(self, event):
        self._cancel_room_creation()
        try:
            if getattr(self, "_room_create_poll_timer", None) is not None:
                self._room_create_poll_timer.stop()
            if getattr(self, "_quality_timer", None) is not None:
                self._quality_timer.stop()
            if getattr(self, "_room_liveness_timer", None) is not None:
                self._room_liveness_timer.stop()
            if getattr(self, "_background_event_timer", None) is not None:
                self._background_event_timer.stop()
        except Exception:
            pass
        self._destroy_room()
        super().closeEvent(event)


    def _update_uptime(self):
        if self._room_created is not None:
            elapsed = int(time.time() - self._room_created)
            h, r = divmod(elapsed, 3600)
            m, s = divmod(r, 60)
            self._conn_uptime.setText(f"{h}:{m:02d}:{s:02d}")


    def _refresh_log(self):
        try:
            path = os.path.join(WORK_PATH, "log", "log.txt")
            st = os.stat(path)
            sig = (st.st_size, getattr(st, "st_mtime_ns", int(st.st_mtime * 1000000000)))
            if sig == getattr(self, "_log_last_sig", None):
                return
            self._log_last_sig = sig
            max_bytes = 120 * 1024
            with open(path, "rb") as f:
                if st.st_size > max_bytes:
                    f.seek(st.st_size - max_bytes)
                raw = f.read()
            content = raw.decode("utf-8", errors="replace")
            if content != self.log_text.toPlainText():
                self.log_text.setPlainText(content)
                self.log_text.verticalScrollBar().setValue(
                    self.log_text.verticalScrollBar().maximum()
                )
        except Exception:
            pass


    def _load_servers(self):
        server_file = os.path.join(CONFIG_PATH, "server.json")
        servers = safe_server_entries(_load_json(server_file, [], list))

        while self._server_layout.count():
            item = self._server_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        config = _load_json(os.path.join(CONFIG_PATH, "config.json"), {}, dict)
        selected = config.get("selected_server", "")
        self._server_card_widgets = {}

        for server in servers:
            self._server_layout.addWidget(self._build_server_card(server["name"], server["ip"], selected == server["name"]))

        add_btn = JellyButton("+ 新增服务器")
        add_btn.setObjectName("addServerBtn")
        add_btn.setMinimumHeight(58)
        add_btn.setCursor(Qt.PointingHandCursor)
        self._set_button_icon(add_btn, "plus", 18)
        add_btn.clicked.connect(self._add_server_dialog)
        self._server_layout.addWidget(add_btn)
        self._server_layout.addStretch(1)


    def _build_server_card(self, name, ip, is_selected):
        card = MotionCard()
        card.setObjectName("serverCard")
        card.setFrameShape(QFrame.StyledPanel)
        card.setMinimumHeight(132)
        card.setMaximumHeight(132)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(24, 16, 24, 15)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        name_label = QLabel(name)
        name_label.setObjectName("serverName")
        name_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        header.addWidget(name_label)

        is_recommended = name == getattr(self, "_recommended_server_name", "")
        status_text = "● 已选 · 推荐" if (is_selected and is_recommended) else ("● 已选" if is_selected else ("★ 推荐" if is_recommended else "○ 未选"))
        status_label = QLabel(status_text)
        status_label.setObjectName("statusLabel")
        header.addWidget(status_label)
        header.addStretch(1)

        ip_label = QLabel(ip)
        ip_label.setObjectName("ipLabel")
        ip_label.setMinimumWidth(150)
        ip_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(ip_label)
        outer.addLayout(header)

        footer = QHBoxLayout()
        footer.setSpacing(9)
        metric = getattr(self, "_server_metrics", {}).get(ip)
        latency_label = QLabel("延迟: " + (self._metrics_text(metric) if metric else "未检测"))
        latency_label.setObjectName("latencyLabel")
        latency_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer.addWidget(latency_label, 1)

        ping_btn = JellyButton("刷新")
        ping_btn.setObjectName("smallActionBtn")
        ping_btn.setFixedHeight(32)
        self._set_button_icon(ping_btn, "refresh", 15)
        ping_btn.clicked.connect(lambda _, target_ip=ip, label=latency_label: self._ping_server(target_ip, label))
        footer.addWidget(ping_btn)

        select_btn = JellyButton("选择")
        select_btn.setObjectName("smallActionBtn")
        select_btn.setFixedHeight(32)
        select_btn.clicked.connect(lambda _, server_name=name: self._select_server(server_name))
        footer.addWidget(select_btn)

        register_btn = JellyButton("注册")
        register_btn.setObjectName("smallActionBtn")
        register_btn.setFixedHeight(32)
        register_btn.clicked.connect(lambda _, server_name=name, target_ip=ip: self._register_server(server_name, target_ip))
        footer.addWidget(register_btn)
        outer.addLayout(footer)

        self._server_card_widgets[ip] = {"latency": latency_label, "status": status_label, "name": name}
        return card


    def _ping_server(self, ip, latency_label=None):
        if latency_label is not None:
            latency_label.setText("延迟: 检测中...")
        self._start_server_probe(ip, context="manual", count=3)


    def _add_server_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("新增服务器")
        layout = QFormLayout(dialog)
        name_input = QLineEdit()
        ip_input = QLineEdit()
        layout.addRow("地域:", name_input)
        layout.addRow("IP:", ip_input)

        btn_layout = QHBoxLayout()
        ok_btn = JellyButton("确定")
        cancel_btn = JellyButton("取消")
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
            if not is_valid_server_host(ip):
                QMessageBox.warning(self, "服务器", "请输入有效的服务器 IP 或域名")
                return
            server_file = os.path.join(CONFIG_PATH, "server.json")
            servers = safe_server_entries(_load_json(server_file, [], list))
            for s in servers:
                if s["name"] == name:
                    s["ip"] = ip
                    break
            else:
                servers.append({"name": name, "ip": ip})
            _save_json(server_file, servers)
            self.log.logging(f"新增/更新服务器: {name} {ip}")
            self._load_servers()
            QTimer.singleShot(50, lambda target_ip=ip: self._start_server_probe(target_ip, context="new_server", count=3))


    def _select_server(self, name):
        config_file = os.path.join(CONFIG_PATH, "config.json")
        config = _load_json(config_file, {}, dict)
        config["selected_server"] = name
        _save_json(config_file, config)
        self.log.logging(f"已选择服务器: {name}")
        self._load_servers()
        if self._room_created is None:
            self._refresh_connect_info()
            metric = self._server_metrics.get(self._conn_ip.text().strip())
            if metric:
                self._conn_latency.setText(self._metrics_text(metric))


    def _register_server(self, name, ip):
        config_file = os.path.join(CONFIG_PATH, "config.json")
        config = _load_json(config_file, {}, dict)
        apikey = str(config.get("apikey", "")).strip()
        if not apikey:
            QMessageBox.warning(self, "服务器", "本机密钥无效，请重启程序后重试")
            return
        job_key = f"register:{ip}"

        def worker():
            ok, reason = self._register_key_silent(name, ip, apikey)
            self._background_events.put(("server_register", {"name": name, "ip": ip, "ok": bool(ok), "reason": str(reason or "")}))

        if self._launch_background(job_key, worker, "ServerRegisterWorker"):
            self.log.logging(f"正在后台注册服务器: {name}", owner="[NET]")


    def _check_update_async(self):
        task = UpdateCheckTask(self._background_events)
        self._launch_background("update_check", task.run, "UpdateCheckWorker")


    def _handle_update_check(self, payload):
        self._background_jobs.discard("update_check")
        if not payload.get("ok"):
            self.log.logging(f"检查更新失败: {payload.get('error', '')}", type_="[WARN]", owner="[ASYNC]")
            self._ver_latest_label.setText("最新版本: 获取失败")
            return
        server_ver = str(payload.get("version", ""))
        self.log.logging(f"最新版本: {server_ver}", owner="[ASYNC]")
        self._latest_version = server_ver
        display = f"V{server_ver}" if server_ver else "未知"
        self._ver_latest_label.setText(f"最新版本: {display}")
        if server_ver and compare_versions(server_ver, VERSION) > 0:
            self.log.logging(f"发现新版本 V{server_ver}，当前 V{VERSION}", owner="[ASYNC]")
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
                subprocess.Popen([updater], creationflags=CREATE_NO_WINDOW)
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
        path = os.path.join(WORK_PATH, "log", "log.txt")
        try:
            os.startfile(path)
        except Exception:
            QMessageBox.information(self, "日志路径", path)


    def _activate(self, index):
        if hasattr(self, 'btn_group'):
            btn = self.btn_group.button(index)
            if btn:
                btn.setChecked(True)
        animate = bool(getattr(self, "_activation_ready", False) and self.isVisible())
        self.title_label.setGraphicsEffect(None)
        self.title_label.setText(self.nav_items[index])
        self.stack.setCurrentIndex(index)
        self._apply_responsive_layout()
        self._move_nav_indicator()
        page = self.stack.currentWidget()
        if page is not None:
            page.setGraphicsEffect(None)
            page.updateGeometry()
            page.update()
        self._activation_ready = True
        if animate:
            self._animate_current_page()


    def _on_nav_clicked(self, index):
        self._activate(index)

