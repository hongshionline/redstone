import os
import sys
import time
import threading
import zipfile
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog
import ctypes
from PIL import Image,ImageTk

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

is_admin = ctypes.windll.shell32.IsUserAnAdmin()
if not is_admin:
    exe = sys.executable
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, "", BASE_DIR, 1)
    sys.exit()

sw = ctypes.windll.user32.GetSystemMetrics(0)
sh = ctypes.windll.user32.GetSystemMetrics(1)
ratio = sw / sh
w = int(sh / 4 * ratio)
h = int(sh / 4)

root = tk.Tk()
root.title("红石联机客户端v107安装程序 - 管理员")
root.iconbitmap(os.path.join(BASE_DIR, "setup.ico"))
root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
root.resizable(False,False)

side = tk.Frame(root, bg="#000e6c")
side.place(relx=0, rely=0, relwidth=0.3, relheight=1.0)

ico_pil = Image.open(os.path.join(BASE_DIR, "setup.ico"))
ico_size = min(int(w * 0.3), h) // 2
ico_tk = ImageTk.PhotoImage(ico_pil.resize((ico_size, ico_size)))
ico_label = tk.Label(side, image=ico_tk, bg="#000e6c")
ico_label.place(relx=0.5, rely=0.5, anchor="center")

# ---- 页面1：协议 ----
page1 = tk.Frame(root)
page1.place(relx=0.3, rely=0, relwidth=0.7, relheight=1.0)

title = tk.Label(page1, text="欢迎下载红石联机客户端v107版本",
                 font=("Microsoft YaHei", 12, "bold"))
title.place(relx=0.5, rely=0.05, anchor="center")

text = tk.Text(page1, wrap="word")
text.place(relx=0.05, rely=0.12, relwidth=0.9, relheight=0.68)

text.insert("end","""红石联机客户端 最终用户许可协议（EULA）

更新日期：2026年6月27日
生效日期：2026年6月27日

欢迎使用"红石联机"客户端软件（以下简称"本软件"）。本协议是您（以下称"用户"或"您"）与红石联机团队（以下称"我们"或"本团队"）之间关于下载、安装、使用本软件及接受相关服务所订立的法律协议。

请您务必仔细阅读并充分理解本协议各条款，特别是免除或限制责任的条款。如您未满18周岁，请在法定监护人陪同下阅读本协议。您下载、安装或使用本软件，即视为您已阅读并同意受本协议约束。

1. 许可授予

本团队授予您一项个人的、非独占的、不可转让的、可撤销的权利，以安装和使用本软件。本许可仅限于您个人在符合本协议约定的范围内，为使用"红石联机"平台服务之目的而使用。

2. 使用限制

您在使用本软件时，不得进行以下行为，否则本团队有权立即终止您的使用权限并保留追究法律责任的权利：
    将本软件或其任何部分用于商业用途，包括但不限于销售、出租、转让或提供付费托管服务，除非获得本团队明确书面授权。
    对本软件进行反向工程、反编译、反汇编、破解或任何尝试获取源代码的行为。
    利用本软件进行或协助任何违法活动，包括但不限于网络攻击、传播恶意代码、侵犯他人隐私。
    以任何方式干扰或破坏"红石联机"平台服务器的正常运行。

3. 关于FRP穿透服务

本软件的核心功能是通过FRP（内网穿透）技术为您提供联机服务。您理解并同意：
    网络环境依赖：本软件的服务质量受您的本地网络环境、互联网线路及服务器节点状态影响，本团队不承诺服务绝对稳定、无中断或无延迟。
    合规使用：您承诺使用本软件穿透的端口和服务，均符合中华人民共和国法律法规及《我的世界》Mojang EULA的相关规定。
    资源占用：本软件运行时会在您的设备上创建FRP客户端进程。若该进程被Windows安全中心或其他杀毒软件拦截或删除，您需要手动将其添加至信任列表，或参阅我们的帮助文档。

4. 用户账号与安全

    您在本软件及关联网站注册的账号（如API Key）仅供您本人使用，不得出借、转让或共享。
    您需对您账号下的所有行为负责。如因您保管不善导致账号被盗用，由此产生的后果由您自行承担。

5. 服务变更与终止

    我们有权根据运营策略对"红石联机"的服务模式（如免费或收费）、功能特性、服务器节点进行调整，并会通过适当方式（如网站公告）通知您。
    如果您违反本协议的任何条款，我们有权在不另行通知的情况下，立即终止您的使用权限并删除相关数据。

6. 免责声明

    "按现状"提供：本软件是"按现状"和"按现有功能"提供的，本团队不作任何明示或暗示的保证，包括但不限于适销性、特定用途适用性和非侵权性的暗示保证。
    责任限制：在适用法律允许的最大范围内，本团队不对因使用或无法使用本软件所造成的任何间接、偶然、特殊或惩罚性损害（包括但不限于数据丢失、业务中断、游戏账号被封禁）承担责任。

7. 法律适用与争议解决

    本协议的订立、执行和解释均适用中华人民共和国法律。
    因本协议引起的任何争议，双方应首先友好协商解决；协商不成的，任何一方均有权将争议提交至被告所在地有管辖权的人民法院诉讼解决。

8. 其他

    本协议构成您与我们之间关于本软件使用的完整协议。
    我们有权不定期更新本协议，更新后的协议将在官网或软件安装界面公布。如您继续使用本软件，即视为接受更新后的协议。

联系邮箱：redstone@hongshi.site
""")
text.config(state="disabled")

agree_var = tk.IntVar()
agree_cb = ttk.Checkbutton(page1, text="我已阅读并同意上述协议", variable=agree_var)
agree_cb.place(relx=0.05, rely=0.86)

btn_next = ttk.Button(page1, text="下一步 >", state="disabled")
btn_next.place(relx=0.70, rely=0.86, anchor="center")

btn_cancel1 = ttk.Button(page1, text="取消")
btn_cancel1.place(relx=0.88, rely=0.86, anchor="center")

def on_agree_changed(*_):
    btn_next.config(state="normal" if agree_var.get() else "disabled")
agree_var.trace_add("write", on_agree_changed)

try:
    log_file = open(os.path.join(BASE_DIR, "log.txt"), "w", encoding="utf-8")
except Exception:
    log_file = None

def cancel():
    try:
        log_file.close()
    except Exception:
        pass
    root.destroy()
btn_cancel1.config(command=cancel)

# ---- 页面2：安装路径 ----
page2 = tk.Frame(root)
default_path = BASE_DIR if not getattr(sys, "frozen", False) else os.path.dirname(sys.executable)
path_var = tk.StringVar(value=default_path)

def show_page2():
    page1.place_forget()
    page2.place(relx=0.3, rely=0, relwidth=0.7, relheight=1.0)

btn_next.config(command=show_page2)

# 配置模式
cfg_frame = tk.Frame(page2)
cfg_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

path_label = tk.Label(cfg_frame, text="选择安装路径：",
                      font=("Microsoft YaHei", 10))
path_label.place(relx=0.1, rely=0.3)

path_entry = ttk.Entry(cfg_frame, textvariable=path_var, width=30)
path_entry.place(relx=0.1, rely=0.4, relwidth=0.6)

def browse_path():
    d = filedialog.askdirectory(initialdir=path_var.get())
    if d:
        path_var.set(d)

hint = tk.Label(cfg_frame, text="提示：路径中尽量不要包含中文字符，避免兼容性问题",
                fg="gray", font=("Microsoft YaHei", 8))
hint.place(relx=0.1, rely=0.48)

btn_browse = ttk.Button(cfg_frame, text="浏览...", command=browse_path)
btn_browse.place(relx=0.73, rely=0.39)

btn_install = ttk.Button(cfg_frame, text="安装")
btn_install.place(relx=0.70, rely=0.8, anchor="center")

shortcut_var = tk.IntVar(value=1)
shortcut_cb = ttk.Checkbutton(cfg_frame, text="在桌面创建快捷方式", variable=shortcut_var)
shortcut_cb.place(relx=0.1, rely=0.58)

btn_cancel2 = ttk.Button(cfg_frame, text="取消", command=cancel)
btn_cancel2.place(relx=0.88, rely=0.8, anchor="center")

# 安装模式
inst_frame = tk.Frame(page2)

prog = ttk.Progressbar(inst_frame, mode="determinate")
prog.place(relx=0.1, rely=0.15, relwidth=0.8)

log_text = tk.Text(inst_frame, wrap="word", state="disabled")
log_text.place(relx=0.1, rely=0.25, relwidth=0.8, relheight=0.5)

btn_abort = ttk.Button(inst_frame, text="中断")
btn_abort.place(relx=0.70, rely=0.85, anchor="center")

btn_finish = ttk.Button(inst_frame, text="完成", state="disabled")
btn_finish.place(relx=0.88, rely=0.85, anchor="center")

aborted = False

def log(msg):
    t = time.strftime("%H:%M:%S")
    root.after(0, lambda: (
        log_text.config(state="normal"),
        log_text.insert("end", f"[{t}] {msg}\n"),
        log_text.see("end"),
        log_text.config(state="disabled")
    ))
    if log_file is not None:
        try:
            log_file.write(f"[{t}] {msg}\n")
            log_file.flush()
        except Exception:
            pass

def set_prog(val):
    root.after(0, lambda: prog.config(value=val))

def _ps_escape_double(path):
    """转义用于 PowerShell 双引号字符串的路径（转义 " $ ` ）"""
    return path.replace('`', '``').replace('$', '`$').replace('"', '`"')

def _ps_escape_single(path):
    """转义用于 PowerShell 单引号字符串的路径（将 ' 替换为 ''）"""
    return path.replace("'", "''")

def run_powershell(cmd, log_msg, err_ok=(0x800106ba,)):
    log(log_msg)
    try:
        r = subprocess.run(["powershell", "-Command", cmd],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode != 0:
            if r.returncode in err_ok:
                log("  ↳ 忽略已知错误码")
            else:
                log(f"  ↳ 警告：{r.stderr.strip()}")
    except Exception as e:
        log(f"  ↳ 异常：{e}")

def do_install():
    global aborted
    dest = path_var.get()
    log(f"========== 红石联机客户端 v107 安装开始 ==========")
    log(f"安装路径：{dest}")
    log(f"系统版本：{sys.getwindowsversion().major}.{sys.getwindowsversion().minor}.{sys.getwindowsversion().build}")
    set_prog(5)

    # 1. 添加安装文件夹白名单
    log("--- [1/5] Windows 安全中心白名单设置 ---")
    log(f"目标目录：{dest}")
    run_powershell(f'Add-MpPreference -ExclusionPath "{_ps_escape_double(dest)}"', "正在添加安装目录到 Windows Defender 排除列表...")
    if aborted: return
    set_prog(15)

    # 2. 解压 redstone.zip
    log("--- [2/5] 解压安装包 ---")
    zip_path = os.path.join(BASE_DIR, "redstone.zip")
    log(f"安装包路径：{zip_path}")
    log(f"压缩包大小：{os.path.getsize(zip_path) / 1024 / 1024:.1f} MB" if os.path.exists(zip_path) else "压缩包不存在")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            files = z.namelist()
            log(f"压缩包内文件数：{len(files)}")
            log(f"正在解压到：{dest}")
            dest_real = os.path.realpath(dest)
            for member in z.infolist():
                member_path = os.path.realpath(os.path.join(dest_real, member.filename))
                if not member_path.startswith(dest_real + os.sep) and member_path != dest_real:
                    raise ValueError(f"非法压缩包条目（路径越界）: {member.filename}")
            z.extractall(dest)
        log("✓ 解压完成")
    except Exception as e:
        log(f"✗ 解压失败：{e}")
        return
    if aborted: return
    set_prog(40)

    # 3. 添加 frpc.exe 白名单
    log("--- [3/5] FRP 白名单设置 ---")
    frpc_path = os.path.join(dest, "redstone", "frp", "frpc.exe")
    log(f"FRPC 路径：{frpc_path}")
    if os.path.exists(frpc_path):
        log(f"FRPC 大小：{os.path.getsize(frpc_path) / 1024:.1f} KB")
    run_powershell(f'Add-MpPreference -ExclusionPath "{_ps_escape_double(frpc_path)}"', "正在添加 frpc.exe 到 Windows Defender 排除列表...")
    if aborted: return
    set_prog(60)

    # 4. 创建快捷方式
    log("--- [4/5] 桌面快捷方式 ---")
    if shortcut_var.get():
        exe_path = os.path.join(dest, "redstone", "redstone.exe")
        log(f"目标程序：{exe_path}")
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
        lnk = os.path.join(desktop, "红石联机.lnk")
        log(f"快捷方式路径：{lnk}")
        ws_ps = f'''
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{_ps_escape_single(lnk)}')
$s.TargetPath = '{_ps_escape_single(exe_path)}'
$s.WorkingDirectory = '{_ps_escape_single(os.path.dirname(exe_path))}'
$s.Save()
'''
        log("正在创建桌面快捷方式...")
        try:
            r = subprocess.run(["powershell", "-Command", ws_ps],
                               capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0:
                log("✓ 快捷方式已创建")
            else:
                log(f"✗ 创建失败：{r.stderr.strip()}")
        except Exception as e:
            log(f"✗ 异常：{e}")
    else:
        log("用户选择跳过")
    if aborted: return
    set_prog(80)

    # 5. 完成
    log("--- [5/5] 完成 ---")
    log("✓ 红石联机客户端 v107 安装成功！")
    log(f"安装位置：{dest}")
    log(f"启动程序：{os.path.join(dest, 'redstone', 'redstone.exe')}")
    set_prog(100)
    root.after(0, lambda: (
        btn_abort.config(state="disabled"),
        btn_finish.config(state="normal")
    ))

def start_install():
    global aborted
    aborted = False
    cfg_frame.place_forget()
    inst_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
    threading.Thread(target=do_install, daemon=True).start()

def abort_install():
    global aborted
    aborted = True
    log("⚠ 用户中断安装")

btn_install.config(command=start_install)
btn_abort.config(command=abort_install)
btn_finish.config(command=cancel)

root.mainloop()
