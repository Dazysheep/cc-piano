"""OpenFilm Studio（剪辑器）的启动器：所有数据都放在 douyin\\editor\\ 下（不写 C 盘），ffmpeg/ffprobe 用项目自带的。

用法:  ..\\.venv\\Scripts\\python editor\\studio.py [工程文件夹]     打开某个工程（含 film.html 的文件夹）
       ..\\.venv\\Scripts\\python editor\\studio.py --status          看 Studio 有没有在运行、地址是什么
琴房服务（web/server.py）的「剪辑」页通过 address() 拿到 Studio 的地址，嵌在页面里。
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPENFILM = HERE / "node_modules" / ".bin" / ("openfilm.cmd" if os.name == "nt" else "openfilm")
FFMPEG_BIN = next((p for p in (HERE.parent / "tools" / "ffmpeg").glob("ffmpeg-*/bin")), None)
PORT = int(os.environ.get("CC_STUDIO_PORT", 8790))


def env() -> dict:
    e = dict(os.environ)
    e.update(
        OPENFILM_HOME=str(HERE / "home"),              # Studio 自己的设置、密钥、日志
        OPENFILM_LIBRARY=str(HERE / "projects"),       # 在 Studio 里新建的工程
        OPENFILM_EXPORTS=str(HERE / "exports"),        # 导出文件
        OPENFILM_TRASH_DIR=str(HERE / "trash"),
        PLAYWRIGHT_BROWSERS_PATH=str(HERE / "browsers"),   # 渲染用的无头浏览器（约 100MB，第一次自动下载）
        OPENFILM_STUDIO_PORT=str(PORT),
        OPENFILM_NO_BROWSER="1",                       # 不自己弹浏览器：由琴房的「剪辑」页嵌入
        OPENFILM_NO_UPDATE_CHECK="1",
    )
    if FFMPEG_BIN:
        e["PATH"] = str(FFMPEG_BIN) + os.pathsep + e.get("PATH", "")
    for k in [k for k in e if k.startswith("CLAUDE")]:    # 别让它以为自己是被编程助手调用的
        e.pop(k)
    return e


def address() -> str | None:
    """Studio 在运行时返回它的地址。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1.5) as r:
            return f"http://127.0.0.1:{PORT}/" if r.status < 500 else None
    except OSError:
        return None


def exports_for(title: str, since: float = 0.0) -> list[Path]:
    """Studio 导出的成片里属于这个工程的（文件名以工程标题开头，比 since 新），新的在前。
    Studio 导出时按工程标题起名、不覆盖旧文件（rifle.mp4、rifle 2.mp4 …）。"""
    root = HERE / "exports"
    if not root.is_dir():
        return []
    found = [p for p in root.rglob("*.mp4") if p.stem.lower().startswith(title.lower()) and p.stat().st_mtime > since]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def open_project(folder: Path | None = None) -> str:
    """启动 Studio（没在运行时）并打开工程，返回 openfilm 打印的信息。"""
    args = [str(OPENFILM), "open"] + ([str(folder)] if folder else [])
    r = subprocess.run(args, env=env(), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=600, shell=os.name == "nt")
    return (r.stdout + r.stderr).strip()


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(json.dumps({"address": address(), "port": PORT, "ffmpeg": str(FFMPEG_BIN)}, ensure_ascii=False))
    else:
        target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
        print(open_project(target))
