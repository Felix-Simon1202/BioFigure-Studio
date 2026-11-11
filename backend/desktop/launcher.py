"""Windows controller: the window and server share one process and lifetime."""

import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from backend.desktop.runtime import LocalRuntime


class InstanceLock:
    """Kernel-owned lock; a crash cannot leave a stale PID file."""

    def __init__(self, root):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel
        name = "Local\\BioFigure-" + hashlib.sha256(str(root).lower().encode()).hexdigest()[:24]
        self.handle = kernel.CreateMutexW(None, False, name)
        if not self.handle:
            raise OSError("无法创建本机启动锁。")
        self.existing = ctypes.get_last_error() == 183

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def main():
    root_path = Path(__file__).resolve().parents[2]
    window = tk.Tk()
    window.title("BioFigure Studio · 本机启动")
    window.geometry("480x250")
    window.resizable(False, False)
    lock = InstanceLock(root_path)
    if lock.existing:
        window.withdraw()
        messagebox.showinfo("BioFigure Studio", "本版本已经运行。请在已有启动窗口点击“打开绘图网页”。", parent=window)
        lock.close()
        window.destroy()
        return
    runtime = None
    closing = False
    deadline = 0.0
    status = tk.StringVar(value="正在启动本机绘图服务…")
    ttk.Label(window, text="BioFigure Studio", font=("Segoe UI", 20)).pack(pady=(22, 12))
    ttk.Label(window, textvariable=status, wraplength=440, justify="center").pack(pady=5)
    ttk.Label(window, text="关闭网页后会话仍保留。退出本窗口将清除本次数据和配置。", wraplength=440).pack(pady=8)

    def open_page():
        if runtime and not closing:
            if not webbrowser.open(runtime.launch_url):
                messagebox.showerror("无法打开浏览器", "请检查系统默认浏览器后重试。", parent=window)

    open_button = ttk.Button(window, text="打开绘图网页", command=open_page, state="disabled")
    open_button.pack(pady=5)

    def close():
        nonlocal closing, deadline
        if closing:
            return
        if runtime and not messagebox.askokcancel("退出 BioFigure Studio", "退出后，本次导入数据、配置和队列会话将结束。请先下载需要的图像。", parent=window):
            return
        closing = True
        deadline = time.monotonic() + 5
        status.set("正在停止本机服务…")
        open_button.config(state="disabled")
        if runtime:
            runtime.request_stop()
        poll_close()

    def poll_close():
        if runtime and runtime.thread.is_alive() and time.monotonic() < deadline:
            window.after(100, poll_close)
            return
        if runtime:
            runtime.socket.close()
        lock.close()
        window.destroy()
        # The only computation is in this process. Bounded exit also stops an
        # in-flight native plotting worker; no external/browser process is killed.
        if runtime and runtime.thread.is_alive():
            os._exit(0)

    ttk.Button(window, text="退出并停止服务", command=close).pack(pady=5)
    window.protocol("WM_DELETE_WINDOW", close)

    def ready():
        if closing:
            return
        if runtime.failed or not runtime.thread.is_alive():
            status.set("服务启动失败。请退出后重试；不会关闭其他程序。")
        elif runtime.server.started:
            status.set("本机服务已就绪 · 可离线使用")
            open_button.config(state="normal")
            open_page()
            monitor()
        else:
            window.after(100, ready)

    def monitor():
        if closing:
            return
        if not runtime.thread.is_alive():
            status.set("本机服务已停止，请退出后重新启动。")
            open_button.config(state="disabled")
        else:
            window.after(500, monitor)

    def start():
        nonlocal runtime
        try:
            runtime = LocalRuntime(root_path / "apps" / "web" / "dist")
            runtime.start()
            ready()
        except Exception:
            status.set("启动失败：请确认现有 Python 环境及网页构建完整，参阅 README。")

    window.after(100, start)
    try:
        window.mainloop()
    finally:
        if runtime:
            runtime.stop()
        lock.close()


if __name__ == "__main__":
    # pythonw has no standard streams. Never write data, tokens or paths to logs.
    with open(os.devnull, "w") as sink:
        sys.stdout = sys.stderr = sink
        main()
