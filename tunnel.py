# -*- coding: utf-8 -*-
"""红石联机的 FRP 隧道、测速和后台任务。"""
from __future__ import annotations

import csv

from main import *  # 共享运行目录、Qt 兼容常量与基础依赖。
from urllib.parse import quote


def is_valid_port_text(port_text):
    if not str(port_text).isdigit():
        return False
    try:
        port = int(port_text)
    except ValueError:
        return False
    return 1 <= port <= 65535


def is_local_service_listening(port):
    """检查本机是否有服务监听端口。

    优先探测回环地址；对少数仅绑定到具体网卡 IP 的 Java 进程，
    再补充当前主机已解析到的本地 IPv4/IPv6 地址。
    """
    try:
        port = int(port)
    except Exception:
        return False
    if not (1 <= port <= 65535):
        return False

    targets = [(socket.AF_INET, ("127.0.0.1", port)), (socket.AF_INET6, ("::1", port, 0, 0))]
    try:
        for family, _kind, _proto, _canon, sockaddr in socket.getaddrinfo(socket.gethostname(), None):
            if family == socket.AF_INET and sockaddr and sockaddr[0] not in {"127.0.0.1", "0.0.0.0"}:
                targets.append((socket.AF_INET, (sockaddr[0], port)))
            elif family == socket.AF_INET6 and sockaddr and sockaddr[0] not in {"::1", "::"}:
                targets.append((socket.AF_INET6, (sockaddr[0], port, 0, 0)))
    except OSError:
        pass

    seen = set()
    for family, address in targets:
        marker = (family, address)
        if marker in seen:
            continue
        seen.add(marker)
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.45)
                if sock.connect_ex(address) == 0:
                    return True
        except OSError:
            continue
    return False


def make_proxy_name(tunnel_id, fallback=""):
    """生成仅包含安全字符的 FRP 代理名。

    每个隧道使用独立名称，避免多个客户端使用同一 apikey 时发生
    proxy-name 冲突；旧隧道恢复时仍保留其原名称。
    """
    seed = re.sub(r"[^A-Za-z0-9_-]", "", str(tunnel_id or ""))
    if not seed:
        seed = re.sub(r"[^A-Za-z0-9_-]", "", str(fallback or ""))
    if not seed:
        seed = secrets.token_hex(8)
    return f"redstone-{seed[-20:]}"


class RoomCreateTask:
    """在后台创建 FRP 房间；不直接访问 Qt 控件，避免阻塞界面线程。"""

    def __init__(self, *, port_text, ip, apikey, server_name, frpc_path, event_queue, cancel_event):
        self.port_text = str(port_text)
        self.ip = str(ip)
        self.apikey = str(apikey)
        self.server_name = str(server_name)
        self.frpc_path = str(frpc_path)
        self.events = event_queue
        self.cancel_event = cancel_event

    def _emit_log(self, content, type_="[INFO]", owner="[ROOM]"):
        self.events.put(("log", content, type_, owner))

    def _cancelled(self):
        return self.cancel_event.is_set()

    def _check_cancelled(self):
        if self._cancelled():
            raise InterruptedError("已取消创建房间")

    def _wait_or_cancel(self, seconds):
        if self.cancel_event.wait(max(0.0, float(seconds))):
            raise InterruptedError("已取消创建房间")

    @staticmethod
    def _read_json_response(response):
        raw = response.read()
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _register_key(self):
        self._check_cancelled()
        url = f"http://{self.ip}:3001/api/register-key"
        body = json.dumps({"apikey": self.apikey}).encode("utf-8")
        self._emit_log(f"注册请求 {self.server_name}({self.ip}): POST {{apikey: ***}}")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                result = self._read_json_response(resp)
            self._emit_log(f"注册响应 {self.server_name}: {json.dumps(result, ensure_ascii=False)}")
            return True, ""
        except urllib.error.HTTPError as exc:
            raw = ""
            message = f"HTTP {exc.code}"
            try:
                raw = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw) if raw else {}
                message = parsed.get("message", message) if isinstance(parsed, dict) else raw
            except Exception:
                pass
            self._emit_log(f"注册失败({self.server_name}): {raw or message}", "[ERROR]")
            low = (message + raw).lower()
            exists = exc.code in (400, 409) and any(
                word in low for word in ("already", "exist", "duplicate", "重复", "已存在", "已注册")
            )
            return (True, "") if exists else (False, message)
        except Exception as exc:
            self._emit_log(f"注册失败({self.server_name}): {exc}", "[ERROR]")
            return False, str(exc)

    def _delete_tunnel_silent(self, tunnel_id):
        if not tunnel_id:
            return
        url = f"http://{self.ip}:3001/api/tunnels/{quote(str(tunnel_id), safe='')}"
        try:
            req = urllib.request.Request(
                url,
                method="DELETE",
                headers={"Authorization": f"Bearer {self.apikey}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._read_json_response(resp)
            self._emit_log("frpc 未能启动，已清理服务器上的临时隧道", "[WARN]")
        except Exception as exc:
            self._emit_log(f"清理临时隧道失败: {exc}", "[WARN]")

    def run(self):
        result = {"ok": False, "cancelled": False, "title": "创建失败", "message": "未知错误"}
        tunnel_id = None
        try:
            self._check_cancelled()
            if not is_valid_port_text(self.port_text):
                result = {"ok": False, "title": "参数错误", "message": "端口号必须是 1 到 65535 之间的数字"}
                return
            if not os.path.isfile(self.frpc_path):
                result = {"ok": False, "title": "启动失败", "message": "未找到 frp/frpc.exe"}
                self._emit_log("未找到 frp/frpc.exe", "[ERROR]")
                return
            if not is_local_service_listening(int(self.port_text)):
                result = {
                    "ok": False,
                    "title": "未检测到局域网端口",
                    "message": "请先进入 Minecraft 世界并打开局域网，再输入游戏显示的端口。",
                }
                self._emit_log(
                    f"本地 Minecraft 局域网端口 {self.port_text} 未监听，已取消创建房间",
                    "[WARN]",
                )
                return
            self._check_cancelled()

            url = f"http://{self.ip}:3001/api/tunnels"
            data = None
            last_message = ""
            for attempt in range(6):
                self._check_cancelled()
                if attempt:
                    self._wait_or_cancel(min(0.35 + attempt * 0.28, 1.6))
                self._emit_log(f"创建房间请求: POST {url} 第 {attempt + 1} 次")
                request = urllib.request.Request(
                    url,
                    method="POST",
                    headers={"Authorization": f"Bearer {self.apikey}"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        data = self._read_json_response(response)
                    self._emit_log(f"创建房间响应: {json.dumps(data, ensure_ascii=False)}")
                    break
                except urllib.error.HTTPError as exc:
                    raw = ""
                    message = f"HTTP {exc.code}"
                    try:
                        raw = exc.read().decode("utf-8", errors="replace")
                        parsed = json.loads(raw) if raw else {}
                        message = parsed.get("message", message) if isinstance(parsed, dict) else raw
                    except Exception:
                        pass
                    self._emit_log(f"创建房间失败: {raw or message}", "[ERROR]")
                    last_message = message
                    low = (message + raw).lower()
                    if exc.code == 401 and attempt <= 1:
                        registered, register_message = self._register_key()
                        if registered:
                            continue
                        result = {"ok": False, "title": "创建失败", "message": register_message or message}
                        return
                    retryable = (
                        exc.code in (409, 429, 500, 502, 503, 504)
                        or "duplicate" in low
                        or "remote_port" in low
                        or "请求过于频繁" in low
                        or "频繁" in low
                    )
                    if retryable and attempt < 5:
                        self._emit_log("服务器临时拒绝或端口冲突，正在自动重试", "[WARN]")
                        continue
                    result = {"ok": False, "title": "创建失败", "message": message or f"HTTP {exc.code}"}
                    return
                except Exception as exc:
                    last_message = str(exc)
                    self._emit_log(f"请求失败: {exc}", "[ERROR]")
                    if attempt < 2:
                        continue
                    result = {"ok": False, "title": "请求失败", "message": str(exc)}
                    return

            self._check_cancelled()
            if not isinstance(data, dict):
                result = {
                    "ok": False,
                    "title": "创建失败",
                    "message": last_message or "服务器返回格式异常",
                }
                self._emit_log(f"创建房间失败: {result['message']}", "[ERROR]")
                return

            tunnel_id = str(data.get("id") or "").strip()
            remote_port = data.get("remote_port")
            server_addr = str(data.get("server_addr") or "").strip()
            server_port = data.get("server_port")
            try:
                remote_port = int(remote_port)
                server_port = int(server_port)
            except (TypeError, ValueError):
                remote_port = 0
                server_port = 0
            if not tunnel_id or not is_valid_port_text(remote_port) or not server_addr or not is_valid_port_text(server_port):
                result = {"ok": False, "title": "创建失败", "message": "服务器返回字段不完整"}
                self._emit_log(
                    f"创建房间失败: 返回字段不完整 {json.dumps(data, ensure_ascii=False)}",
                    "[ERROR]",
                )
                self._delete_tunnel_silent(tunnel_id)
                return

            proxy_name = make_proxy_name(tunnel_id, self.apikey[:8])
            self._emit_log(
                f"隧道信息: id={tunnel_id} remote_port={remote_port} server={server_addr}:{server_port}"
            )
            self._check_cancelled()
            frpc_args = [
                self.frpc_path,
                "tcp",
                "--proxy-name",
                proxy_name,
                "--local-port",
                self.port_text,
                "--remote-port",
                str(remote_port),
                "--server-addr",
                server_addr,
                "--server-port",
                str(server_port),
            ]
            self._emit_log(f"启动 frpc: {' '.join(frpc_args)}")
            try:
                frpc_proc = subprocess.Popen(
                    frpc_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW,
                    bufsize=0,
                )
            except Exception as exc:
                self._emit_log(f"frpc 启动失败: {exc}", "[ERROR]")
                self._delete_tunnel_silent(tunnel_id)
                result = {"ok": False, "title": "启动失败", "message": f"frpc 启动失败: {exc}"}
                return

            # frpc 可能因认证、远端端口或服务端拒绝而立刻退出。
            # 在后台短暂确认，避免界面误显示“房间已创建”。
            self._wait_or_cancel(0.55)
            exit_code = frpc_proc.poll()
            if exit_code is not None:
                details = ""
                try:
                    raw = frpc_proc.stdout.read() if frpc_proc.stdout is not None else b""
                    details = _decode_process_output(raw).strip()
                except Exception:
                    pass
                self._delete_tunnel_silent(tunnel_id)
                msg = f"frpc 启动后立即退出（code={exit_code}）"
                if details:
                    msg += f"：{details[-400:]}"
                self._emit_log(msg, "[ERROR]")
                result = {"ok": False, "title": "连接失败", "message": msg}
                return

            if self._cancelled():
                try:
                    frpc_proc.terminate()
                except Exception:
                    pass
                self._delete_tunnel_silent(tunnel_id)
                raise InterruptedError("已取消创建房间")

            result = {
                "ok": True,
                "data": data,
                "tunnel_id": tunnel_id,
                "remote_port": remote_port,
                "server_addr": server_addr,
                "server_port": server_port,
                "frpc_proc": frpc_proc,
                "ip": self.ip,
                "apikey": self.apikey,
                "port_text": self.port_text,
                "server_name": self.server_name,
                "proxy_name": proxy_name,
            }
        except InterruptedError:
            if tunnel_id:
                self._delete_tunnel_silent(tunnel_id)
            result = {"ok": False, "cancelled": True, "title": "", "message": ""}
        except Exception as exc:
            if tunnel_id:
                self._delete_tunnel_silent(tunnel_id)
            self._emit_log(f"创建房间出现未处理错误: {exc}", "[ERROR]")
            result = {"ok": False, "title": "创建失败", "message": str(exc)}
        finally:
            self.events.put(("result", result))



def _decode_process_output(value):
    if isinstance(value, bytes):
        for encoding in ("utf-8", "gbk", "mbcs"):
            try:
                return value.decode(encoding, errors="replace")
            except Exception:
                continue
        return value.decode(errors="replace")
    return str(value or "")


def _parse_ping_samples(stdout):
    """返回单次 ping 样本和未响应数量，兼容中文/英文 Windows 输出。"""
    text = stdout or ""
    samples = [int(x) for x in re.findall(r"(?:time|时间)\s*[=<]\s*(\d+)\s*ms", text, re.IGNORECASE)]
    loss = None
    m = re.search(r"(?:lost|丢失)\s*[=:]\s*(\d+)", text, re.IGNORECASE)
    if m:
        try:
            loss = int(m.group(1))
        except Exception:
            loss = None
    if loss is None:
        m = re.search(r"\(\s*(\d+)\s*%\s*(?:loss|丢失)\s*\)", text, re.IGNORECASE)
        if m:
            try:
                loss = int(round(int(m.group(1)) * 0.01 * max(1, len(samples))))
            except Exception:
                loss = None
    return samples, loss


def probe_server_quality(ip, count=3, timeout_ms=1200):
    """后台执行的服务器健康探测：Ping、抖动与 API TCP 连通性。"""
    ip = str(ip).strip()
    count = max(1, min(int(count), 5))
    timeout_ms = max(300, min(int(timeout_ms), 3000))
    stdout = ""
    ping_error = ""
    try:
        args = ["ping", "-n", str(count), "-w", str(timeout_ms), ip] if os.name == "nt" else ["ping", "-c", str(count), "-W", str(max(1, timeout_ms // 1000)), ip]
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(5, int(count * timeout_ms / 1000) + 4),
            creationflags=CREATE_NO_WINDOW,
        )
        stdout = _decode_process_output(result.stdout)
    except Exception as exc:
        ping_error = str(exc)

    samples, lost = _parse_ping_samples(stdout)
    received = len(samples)
    if lost is None:
        lost = max(0, count - received)
    lost = max(0, min(count, int(lost)))
    loss_pct = int(round(lost * 100 / max(1, count)))
    avg_ms = int(round(statistics.mean(samples))) if samples else None
    jitter_ms = int(max(samples) - min(samples)) if len(samples) >= 2 else 0

    tcp_ok = False
    tcp_ms = None
    tcp_error = ""
    try:
        begin = time.perf_counter()
        with socket.create_connection((ip, 3001), timeout=2.4):
            tcp_ok = True
        tcp_ms = int(round((time.perf_counter() - begin) * 1000))
    except Exception as exc:
        tcp_error = str(exc)

    connected = bool(samples) or tcp_ok
    base = avg_ms if avg_ms is not None else (tcp_ms if tcp_ms is not None else 9999)
    # 分数越低越好：优先低延迟，同时显著惩罚抖动、连接不稳定和控制端口不可达。
    score = float(base) + float(jitter_ms) * 1.8 + float(loss_pct) * 4.5
    if not tcp_ok:
        score += 45.0
    if not connected:
        score += 10000.0
    return {
        "ip": ip,
        "count": count,
        "samples": samples,
        "received": received,
        "lost": lost,
        "loss_pct": loss_pct,
        "avg_ms": avg_ms,
        "jitter_ms": jitter_ms,
        "tcp_ok": tcp_ok,
        "tcp_ms": tcp_ms,
        "connected": connected,
        "score": round(score, 2),
        "ping_error": ping_error,
        "tcp_error": tcp_error,
        "checked_at": time.time(),
    }


def _windows_process_name_map():
    """读取 PID -> 进程名映射；失败时返回空字典，不影响主功能。"""
    if os.name != "nt":
        return {}
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=6,
            creationflags=CREATE_NO_WINDOW,
        )
        rows = csv.reader(_decode_process_output(result.stdout).splitlines())
        out = {}
        for row in rows:
            if len(row) < 2:
                continue
            try:
                out[int(str(row[1]).replace(",", ""))] = str(row[0]).strip().lower()
            except Exception:
                continue
        return out
    except Exception:
        return {}


def _extract_endpoint_port(endpoint):
    """从 Windows netstat / Get-NetTCPConnection 的端点文本中安全取端口。"""
    text = str(endpoint or "").strip()
    if not text or ":" not in text:
        return None
    tail = text.rsplit(":", 1)[-1].strip().rstrip("]")
    try:
        port = int(tail)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _normalize_listener(port, pid, address="", process="", command_line=""):
    try:
        port = int(port)
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if not (1024 <= port <= 65535) or pid <= 0:
        return None
    return {
        "port": port,
        "pid": pid,
        "address": str(address or ""),
        "process": str(process or "").strip().lower(),
        "command_line": str(command_line or "").strip().lower(),
    }


def _powershell_listeners():
    """优先使用 Windows 原生 Get-NetTCPConnection，避免 netstat 本地化文本解析不稳定。"""
    if os.name != "nt":
        return []
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$processMap = @{}
Get-CimInstance Win32_Process | ForEach-Object {
    $processMap[[int]$_.ProcessId] = [PSCustomObject]@{
        Name = [string]$_.Name
        CommandLine = [string]$_.CommandLine
    }
}
$items = @()
Get-NetTCPConnection -State Listen | ForEach-Object {
    $pid = [int]$_.OwningProcess
    $proc = $processMap[$pid]
    $items += [PSCustomObject]@{
        Port = [int]$_.LocalPort
        PID = $pid
        Address = [string]$_.LocalAddress
        Process = if ($null -ne $proc) { [string]$proc.Name } else { '' }
        CommandLine = if ($null -ne $proc) { [string]$proc.CommandLine } else { '' }
    }
}
$items | ConvertTo-Json -Compress -Depth 3
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return []
        raw = _decode_process_output(result.stdout).strip().lstrip("\ufeff")
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []
        output = []
        for item in data:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_listener(
                item.get("Port"), item.get("PID"), item.get("Address"),
                item.get("Process"), item.get("CommandLine"),
            )
            if normalized:
                output.append(normalized)
        return output
    except Exception:
        return []


def _netstat_listeners():
    """Get-NetTCPConnection 不可用时的兼容兜底，兼容中英文 netstat 输出。"""
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=8,
            creationflags=CREATE_NO_WINDOW,
        )
        text = _decode_process_output(result.stdout)
    except Exception:
        return []

    process_names = _windows_process_name_map()
    output = []
    states = {"LISTENING", "侦听", "LISTEN"}
    for line in text.splitlines():
        parts = re.split(r"\s+", line.strip())
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        state = parts[-2].upper()
        if state not in states:
            continue
        try:
            pid = int(parts[-1])
        except (TypeError, ValueError):
            continue
        port = _extract_endpoint_port(parts[1])
        normalized = _normalize_listener(port, pid, parts[1], process_names.get(pid, ""), "")
        if normalized:
            output.append(normalized)
    return output


def _minecraft_port_score(item):
    """根据进程与命令行特征排序，优先 Java 版 Minecraft 的局域网监听端口。"""
    process = str(item.get("process", "")).lower()
    command = str(item.get("command_line", "")).lower()
    address = str(item.get("address", "")).lower()
    port = int(item.get("port", 0) or 0)
    score = 0

    if process in {"java.exe", "javaw.exe"}:
        score += 900
    elif "java" in process:
        score += 650
    if "minecraft" in process:
        score += 1100
    if any(token in command for token in ("minecraft", ".minecraft", "net.minecraft", "lwjgl")):
        score += 1600
    if any(token in command for token in ("fabric", "forge", "neoforge", "quilt")):
        score += 260
    if address in {"0.0.0.0", "::", "*", "[::]"}:
        score += 140
    if port >= 20000:
        score += 110
    elif port >= 1024:
        score += 35
    if port == 25565:
        score += 25
    return score


def detect_minecraft_lan_ports():
    """识别 Minecraft Java LAN 端口。

    优先使用 Get-NetTCPConnection + 进程命令行，兼容 Win10/Win11；
    PowerShell 查询异常时回退 netstat。返回按可靠性排序的候选列表。
    """
    listeners = _powershell_listeners()
    source = "Windows 网络接口"
    if not listeners:
        listeners = _netstat_listeners()
        source = "netstat"
    if not listeners:
        return []

    merged = {}
    for item in listeners:
        key = (int(item["port"]), int(item["pid"]))
        old = merged.get(key)
        if old is None or len(str(item.get("command_line", ""))) > len(str(old.get("command_line", ""))):
            merged[key] = item

    candidates = []
    for item in merged.values():
        process = str(item.get("process", "")).lower()
        command = str(item.get("command_line", "")).lower()
        is_java = "java" in process
        is_minecraft = "minecraft" in process or any(token in command for token in ("minecraft", ".minecraft", "net.minecraft", "lwjgl"))
        if not (is_java or is_minecraft):
            continue
        checked = dict(item)
        checked["score"] = _minecraft_port_score(checked)
        checked["source"] = source
        if not is_local_service_listening(checked["port"]):
            continue
        candidates.append(checked)

    candidates.sort(key=lambda value: (-int(value.get("score", 0)), -int(value.get("port", 0))))
    return candidates


class ServerProbeTask:
    def __init__(self, ip, context, event_queue, count=3):
        self.ip = str(ip)
        self.context = str(context)
        self.events = event_queue
        self.count = count

    def run(self):
        try:
            metrics = probe_server_quality(self.ip, count=self.count)
            self.events.put(("server_probe", {"ip": self.ip, "context": self.context, "metrics": metrics}))
        except Exception as exc:
            self.events.put(("server_probe", {"ip": self.ip, "context": self.context, "metrics": {"ip": self.ip, "connected": False, "score": 99999, "error": str(exc), "loss_pct": 100, "avg_ms": None, "jitter_ms": 0, "tcp_ok": False}}))


class UpdateCheckTask:
    def __init__(self, event_queue):
        self.events = event_queue

    def run(self):
        url = "http://43.139.34.232:3000/api/version"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            version = data.get("version", "") if isinstance(data, dict) else ""
            self.events.put(("update_check", {"ok": True, "version": str(version)}))
        except Exception as exc:
            self.events.put(("update_check", {"ok": False, "error": str(exc)}))


class ExistingTunnelCheckTask:
    def __init__(self, saved, event_queue):
        self.saved = dict(saved or {})
        self.events = event_queue

    def run(self):
        ip = self.saved.get("ip")
        apikey = self.saved.get("apikey")
        tunnel_id = self.saved.get("tunnel_id")
        if not ip or not apikey or not tunnel_id:
            self.events.put(("existing_tunnel", {"state": "invalid", "saved": self.saved}))
            return
        url = f"http://{ip}:3001/api/auth/info"
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {apikey}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            tunnel = data.get("tunnel") if isinstance(data, dict) else None
            active = isinstance(tunnel, dict) and tunnel.get("status") == "active"
            response_id = str(tunnel.get("id") or tunnel.get("tunnel_id") or "") if isinstance(tunnel, dict) else ""
            if response_id and response_id != str(tunnel_id):
                active = False
            state = "active" if active else "expired"
            self.events.put(("existing_tunnel", {"state": state, "saved": self.saved, "data": data}))
        except Exception as exc:
            self.events.put(("existing_tunnel", {"state": "unreachable", "saved": self.saved, "error": str(exc)}))


class FrpcStartTask:
    """后台重启 frpc；启动后短暂确认进程没有立即退出。"""

    def __init__(self, session, event_queue):
        self.session = dict(session or {})
        self.events = event_queue

    def run(self):
        proc = None
        try:
            local_port = str(self.session.get("local_port", ""))
            remote_port = str(self.session.get("remote_port", ""))
            server_port = str(self.session.get("server_port", ""))
            server_addr = str(self.session.get("server_addr", "")).strip()
            if not (is_valid_port_text(local_port) and is_valid_port_text(remote_port) and is_valid_port_text(server_port) and server_addr):
                raise RuntimeError("隧道记录不完整")
            frpc_path = get_frpc_path()
            if not os.path.isfile(frpc_path):
                raise RuntimeError("未找到 frp/frpc.exe")
            api_key = str(self.session.get("apikey", ""))
            proxy_name = str(self.session.get("proxy_name", "")).strip() or make_proxy_name(self.session.get("tunnel_id"), api_key[:8])
            args = [
                frpc_path, "tcp", "--proxy-name", proxy_name,
                "--local-port", local_port,
                "--remote-port", remote_port,
                "--server-addr", server_addr,
                "--server-port", server_port,
            ]
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
                bufsize=0,
            )
            time.sleep(0.45)
            exit_code = proc.poll()
            if exit_code is not None:
                output = b""
                try:
                    output = proc.stdout.read() if proc.stdout is not None else b""
                except Exception:
                    pass
                detail = _decode_process_output(output).strip()
                raise RuntimeError(f"frpc 启动后立即退出（code={exit_code}）{('：' + detail[-260:]) if detail else ''}")
            self.events.put(("frpc_start", {"ok": True, "session": self.session, "proc": proc}))
        except Exception as exc:
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.events.put(("frpc_start", {"ok": False, "session": self.session, "error": str(exc)}))


class PortDetectTask:
    def __init__(self, event_queue, force=False):
        self.events = event_queue
        self.force = bool(force)

    def run(self):
        try:
            candidates = detect_minecraft_lan_ports()
            self.events.put(("port_detect", {"candidates": candidates, "force": self.force}))
        except Exception as exc:
            self.events.put(("port_detect", {"candidates": [], "force": self.force, "error": str(exc)}))


class LocalPortLivenessTask:
    """后台检测本机 Minecraft 局域网端口，绝不阻塞 Qt 主线程。"""

    def __init__(self, port, token, event_queue):
        self.port = str(port)
        self.token = str(token)
        self.events = event_queue

    def run(self):
        alive = False
        error = ""
        try:
            if not is_valid_port_text(self.port):
                raise ValueError("端口格式无效")
            alive = bool(is_local_service_listening(int(self.port)))
        except Exception as exc:
            error = str(exc)
        self.events.put((
            "room_liveness",
            {
                "port": self.port,
                "token": self.token,
                "alive": alive,
                "error": error,
                "checked_at": time.time(),
            },
        ))


class TunnelDeleteTask:
    def __init__(self, ip, apikey, tunnel_id, event_queue, reason=""):
        self.ip, self.apikey, self.tunnel_id = str(ip), str(apikey), str(tunnel_id)
        self.events, self.reason = event_queue, str(reason)

    def run(self):
        url = f"http://{self.ip}:3001/api/tunnels/{quote(self.tunnel_id, safe='')}"
        try:
            req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {self.apikey}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            self.events.put(("tunnel_delete", {"ok": True, "tunnel_id": self.tunnel_id, "reason": self.reason, "raw": raw}))
        except Exception as exc:
            self.events.put(("tunnel_delete", {"ok": False, "tunnel_id": self.tunnel_id, "reason": self.reason, "error": str(exc)}))




