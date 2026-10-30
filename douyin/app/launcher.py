r"""cc-piano 启动器（打包成 cc-piano.exe）。

安装目录结构：
  cc-piano.exe          本程序
  runtime\              内置 Python（官方嵌入版 + 全部依赖）
  douyin\               项目文件（网页、渲染脚本、模型、图库……）
启动：用内置 Python 在后台运行 douyin\web\server.py → 等服务就绪 → 用 Edge 应用模式打开一个独立窗口
（没有地址栏，像普通软件）；窗口关掉后服务一起退出。端口被占用时自动换一个；已经在运行时直接打开窗口。
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

BASE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
if not (BASE / "runtime").exists() and (BASE.parent / "runtime").exists():   # 开发时从 app\ 目录运行
    BASE = BASE.parent
PY = BASE / "runtime" / "pythonw.exe"
PROJECT = BASE / "douyin"
NO_WINDOW = 0x08000000


def health(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def find_edge() -> Path | None:
    for root in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if root:
            p = Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.exists():
                return p
    return None


def message(text: str) -> None:
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, text, "cc-piano", 0x40)


def main() -> int:
    if not PY.exists() or not (PROJECT / "web" / "server.py").exists():
        message(f"安装不完整：找不到 {PY if not PY.exists() else PROJECT / 'web' / 'server.py'}\n请重新安装。")
        return 1
    server = None
    port = 8765
    if health(port) is None:                      # 没有在运行：启动服务（端口被别的程序占用就换一个）
        while not free(port) and port < 8800:
            port += 1
        env = dict(os.environ, QINFANG_PORT=str(port), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        (PROJECT / "uploads").mkdir(exist_ok=True)
        with open(PROJECT / "uploads" / "server.log", "a", encoding="utf-8") as log:   # 子进程继承句柄，关掉不影响
            server = subprocess.Popen([str(PY), str(PROJECT / "web" / "server.py"), "--no-browser"], cwd=PROJECT,
                                      env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        for _ in range(240):                      # 第一次启动要加载 numpy 等，最多等 60 秒
            if health(port) is not None:
                break
            if server.poll() is not None:
                message("琴房服务启动失败，详见 douyin\\uploads\\server.log")
                return 1
            time.sleep(0.25)
    url = f"http://127.0.0.1:{port}/"
    # 软件窗口：无边框 + 左上角红黄绿三点（app/window.py，pywebview）；用不了时退回 Edge 应用窗口
    win_py = PROJECT / "app" / "window.py"
    if win_py.exists():
        started = time.time()
        win = subprocess.Popen([str(PY), str(win_py), url], cwd=PROJECT, creationflags=NO_WINDOW)
        code = win.wait()
        if code == 0 or time.time() - started > 3:   # 正常关窗口（或用了一会儿才退出）：不再开别的窗口
            if server:
                server.terminate()
            return 0
    edge = find_edge()
    if not edge:
        webbrowser.open(url)
        if server:
            server.wait()
        return 0
    profile = PROJECT / "uploads" / "edge-app"
    profile.mkdir(parents=True, exist_ok=True)
    win = subprocess.Popen([str(edge), f"--app={url}", f"--user-data-dir={profile}", "--window-size=1560,980",
                            "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
                            "--autoplay-policy=no-user-gesture-required"])   # 作品集的胶片音效不用先点一下才响
    # 独立配置目录：这个进程就是这套窗口的浏览器主进程，所有窗口都关掉后才退出
    win.wait()
    if server:
        server.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
