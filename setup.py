# -*- coding: utf-8 -*-
"""红石联机安装工具。"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

APP_NAME = "红石联机"
APP_VERSION = "108"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ROOT = Path(__file__).resolve().parent


def trace_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    path = base / "RedstoneLink"
    path.mkdir(parents=True, exist_ok=True)
    return path


def trace(event: str, **fields) -> None:
    row = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event}
    row.update({key: str(value) for key, value in fields.items() if value is not None})
    try:
        with open(trace_root() / "installer_trace.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def desktop_dir() -> Path:
    if os.name == "nt":
        try:
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except Exception:
            pass
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    return Path.home() / "Desktop"


def is_app_folder(path: Path) -> bool:
    """确认目标仍是本程序目录，但不依赖 frpc.exe 是否存在。

    某些安全软件可能单独隔离 frpc.exe；安装更新仍应可识别现有程序目录。
    """
    try:
        folder = path.expanduser().resolve()
        if not (folder / "main.py").is_file() or not (folder / "setup.py").is_file():
            return False
        core_names = ("tunnel.py", "layout.py", "window.py")
        has_core_files = sum((folder / name).is_file() for name in core_names) >= 1
        state_file = folder / "config" / "install_state.json"
        has_state = False
        if state_file.is_file():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                has_state = str(data.get("app", "")).strip() == APP_NAME
            except Exception:
                has_state = False
        return has_core_files or has_state
    except Exception:
        return False


def safe_target(path: Path) -> bool:
    try:
        folder = path.expanduser().resolve()
        home = Path.home().resolve()
        blocked = {Path(folder.anchor), home, desktop_dir().resolve(), (home / "Documents").resolve(), (home / "Downloads").resolve()}
        return folder not in blocked and len(folder.parts) >= 2 and is_app_folder(folder)
    except Exception:
        return False


def should_skip(path: Path) -> bool:
    name = path.name.lower()
    if name in {".venv", "__pycache__", ".idea", ".git", "log", "build", "dist", "release", "安装器.py", "新电脑安装引导.cmd", "setup.py"}:
        return True
    if name.endswith((".pyc", ".pyo")):
        return True
    return False


def copy_project(destination: Path) -> None:
    """复制当前完整项目，保留用户已有的 config 与 log。"""
    for item in ROOT.iterdir():
        if should_skip(item):
            continue
        target = destination / item.name
        if item.is_dir():
            if item.name == "config" and target.exists():
                # 保留已有用户配置，同时补齐缺少的默认文件。
                target.mkdir(parents=True, exist_ok=True)
                for child in item.iterdir():
                    if not (target / child.name).exists():
                        shutil.copy2(child, target / child.name)
                continue
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(item, target)
        else:
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def create_shortcut(target: Path) -> None:
    if os.name != "nt":
        return
    shortcut = desktop_dir() / "红石联机.lnk"
    launcher = target / "启动红石联机.bat"
    command = (
        "$W=New-Object -ComObject WScript.Shell; "
        f"$S=$W.CreateShortcut('{str(shortcut).replace("'", "''")}'); "
        f"$S.TargetPath='{str(launcher).replace("'", "''")}'; "
        f"$S.WorkingDirectory='{str(target).replace("'", "''")}'; "
        f"$S.IconLocation='{str(target / 'icon.ico').replace("'", "''")}'; $S.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False, timeout=15, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass


def install_runtime(target: Path, report) -> None:
    python = sys.executable
    venv_python = target / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        report("创建运行环境...")
        subprocess.run([python, "-m", "venv", str(target / ".venv")], check=True, cwd=str(target), creationflags=CREATE_NO_WINDOW)
    report("安装运行依赖...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True, cwd=str(target), creationflags=CREATE_NO_WINDOW)
    subprocess.run([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], check=True, cwd=str(target), creationflags=CREATE_NO_WINDOW)


def install_to(target: Path, report) -> None:
    source = ROOT.resolve()
    target = target.expanduser().resolve()
    if target == source:
        raise RuntimeError("安装目录不能与当前项目目录相同")
    report("复制程序文件...")
    target.mkdir(parents=True, exist_ok=True)
    copy_project(target)
    report("配置运行环境...")
    install_runtime(target, report)
    create_shortcut(target)
    state = target / "config" / "install_state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"app": APP_NAME, "version": APP_VERSION, "status": "installed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    trace("install_completed", target=target)
    report("安装完成")



class Installer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} 安装")
        self.geometry("660x420")
        self.minsize(620, 390)
        self.configure(bg="#ffffff")
        self.path_value = tk.StringVar(value=str(desktop_dir() / "RedstoneLink"))
        self.status_value = tk.StringVar(value="准备安装")
        self._busy = False
        self._build()

    def _build(self):
        tk.Frame(self, bg="#111111", width=12).pack(side="left", fill="y")
        content = tk.Frame(self, bg="#ffffff", padx=36, pady=30)
        content.pack(fill="both", expand=True)
        tk.Label(content, text=APP_NAME, bg="#ffffff", fg="#111111", font=("Microsoft YaHei", 22, "bold")).pack(anchor="w")
        tk.Label(content, text=f"V{APP_VERSION}", bg="#ffffff", fg="#666666", font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(2, 26))
        tk.Label(content, text="安装位置", bg="#ffffff", fg="#111111", font=("Microsoft YaHei", 11, "bold")).pack(anchor="w")
        row = tk.Frame(content, bg="#ffffff")
        row.pack(fill="x", pady=(8, 16))
        tk.Entry(row, textvariable=self.path_value, font=("Consolas", 10), relief="solid", bd=1).pack(side="left", fill="x", expand=True, ipady=8)
        tk.Button(row, text="浏览", command=self._browse, bg="#ffffff", fg="#111111", relief="solid", bd=1, padx=16).pack(side="left", padx=(10, 0), ipady=7)
        self.log_box = tk.Text(content, height=8, bg="#f5f5f5", fg="#222222", relief="flat", font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(4, 14))
        bottom = tk.Frame(content, bg="#ffffff")
        bottom.pack(fill="x")
        tk.Label(bottom, textvariable=self.status_value, bg="#ffffff", fg="#666666", font=("Microsoft YaHei", 10)).pack(side="left")
        self.install_button = tk.Button(bottom, text="开始安装", command=self._start, bg="#111111", fg="#ffffff", relief="flat", padx=26, pady=10, font=("Microsoft YaHei", 10, "bold"))
        self.install_button.pack(side="right")

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self.path_value.get() or str(desktop_dir()), parent=self)
        if folder:
            self.path_value.set(folder)

    def _append(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{time.strftime('%H:%M:%S')}  {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _report(self, message: str):
        self.after(0, lambda: (self.status_value.set(message), self._append(message)))

    def _start(self):
        if self._busy:
            return
        target = Path(self.path_value.get().strip())
        if not str(target):
            return
        if target.exists() and any(target.iterdir()):
            if not messagebox.askyesno("覆盖安装", "目标目录已有文件，将更新程序并保留配置。继续吗？", parent=self):
                return
        self._busy = True
        self.install_button.configure(state="disabled")
        self._append("开始安装")
        thread = threading.Thread(target=self._install_worker, args=(target,), daemon=True)
        thread.start()

    def _install_worker(self, target: Path):
        try:
            trace("install_started", target=target)
            install_to(target, self._report)
            self.after(0, lambda: messagebox.showinfo("安装完成", f"已安装到：\n{target}", parent=self))
        except Exception as exc:
            trace("install_failed", target=target, error=exc)
            self._report(f"安装失败：{exc}")
            self.after(0, lambda: messagebox.showerror("安装失败", str(exc), parent=self))
        finally:
            self.after(0, self._finish)

    def _finish(self):
        self._busy = False
        self.install_button.configure(state="normal")



def main() -> int:
    app = Installer()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
