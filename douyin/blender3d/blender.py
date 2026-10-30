"""Blender（3D 建模）的启动器：照 editor/studio.py（OpenFilm）的做法，程序和数据都放在 douyin 下面，不写 C 盘。

- Blender 本体：douyin/tools/blender/blender-<版本>-windows-x64/（官方便携版，用 glob 找最新的）。
- 它的配置、插件、临时文件：douyin/blender3d/home/、D:\\cc-engine\\.tmp\\blender（BLENDER_USER_* / TEMP 环境变量）。
- blender-mcp（MCP for Blender）：Python 端装在 douyin/.venv（D:\\cc-engine\\.mcp.json 里登记给 Claude Code 用），
  Blender 端的插件 addon.py 和它同一版本，装进上面的插件目录；遥测、轨迹上传、自动更新检查都用环境变量关掉。
- 两种用法：
  run_background(script, args)：后台 Blender（-b，没有窗口）跑一个脚本，做完就退出；和视频渲染共用
    output/.render.lock，同一时间只跑一个（同时跑会抢内存，2026-10-27 整片渲染就因为内存不够中断过）。
  open_gui(blend)：打开带界面的 Blender，并自动开启 MCP 连接（端口 9876），Claude Code 可以直接操作它。
用法：..\\.venv\\Scripts\\python blender3d\\blender.py --status | --gui [文件.blend] | --install-addon
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOME = HERE / "home"
ADDONS = HOME / "scripts" / "addons"
ADDON_NAME = "blender_mcp_addon"
TMP = ROOT.parent / ".tmp" / "blender"
MCP_PORT = int(os.environ.get("BLENDER_PORT", 9876))
NO_WINDOW = 0x08000000
BELOW_NORMAL = 0x00004000                     # 后台 Blender 用「低于正常」优先级：界面始终优先，生成只是慢一点


def find_blender() -> Path | None:
    """项目里最新的便携版 Blender。"""
    cands = sorted((ROOT / "tools" / "blender").glob("blender-*-windows-x64/blender.exe"),
                   key=lambda p: [int(x) if x.isdigit() else 0 for x in p.parent.name.split("-")[1].split(".")])
    return cands[-1] if cands else None


def version() -> str | None:
    b = find_blender()
    return b.parent.name.split("-")[1] if b else None


def env() -> dict:
    e = dict(os.environ)
    for d in (HOME / "config", HOME / "scripts", HOME / "datafiles", TMP):
        d.mkdir(parents=True, exist_ok=True)
    e.update(
        BLENDER_USER_CONFIG=str(HOME / "config"),        # 偏好设置、最近打开的文件
        BLENDER_USER_SCRIPTS=str(HOME / "scripts"),      # 插件（blender-mcp 的 addon 在这里）
        BLENDER_USER_DATAFILES=str(HOME / "datafiles"),
        TEMP=str(TMP), TMP=str(TMP),                     # Blender 的临时文件不放 C 盘
        BLENDER_MCP_DISABLE_TELEMETRY="1", DISABLE_TELEMETRY="1",   # blender-mcp 的匿名统计、轨迹上传
        BLENDERMCP_NO_UPDATE_CHECK="1",                  # 插件启动时联网检查更新
    )
    return e


def addon_source() -> Path:
    """pip 装的 blender-mcp 自带的、同一版本的 Blender 插件。"""
    import blender_mcp
    return Path(blender_mcp.__file__).resolve().parent / "bundled" / "addon.py"


def install_addon() -> Path:
    """把 blender-mcp 的插件放进项目自己的 Blender 插件目录（版本不同才复制）。"""
    ADDONS.mkdir(parents=True, exist_ok=True)
    dst = ADDONS / f"{ADDON_NAME}.py"
    src = addon_source()
    if not dst.exists() or dst.read_bytes() != src.read_bytes():
        shutil.copy(src, dst)
    return dst


def _lock():
    """和视频渲染（tracks/build.py 的 render_lock）同一把锁。"""
    sys.path.insert(0, str(ROOT / "tracks"))
    import msvcrt
    path = ROOT / "output" / ".render.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    while True:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            time.sleep(3)


def run_background(script: Path, args: list[str], timeout: int = 1800, log: Path | None = None) -> str:
    """后台 Blender 跑 script（脚本参数放在 -- 后面），返回输出；失败抛 RuntimeError。"""
    blender = find_blender()
    if not blender:
        raise RuntimeError("没有找到 Blender（douyin\\tools\\blender）")
    install_addon()
    lock = _lock()
    try:
        r = subprocess.run([str(blender), "-b", "--factory-startup", "--python-exit-code", "3", "--python", str(script),
                            "--", *[str(a) for a in args]], env=env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW | BELOW_NORMAL)
    finally:
        lock.close()
    out = (r.stdout or "") + (r.stderr or "")
    if log:
        log.write_text(out, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("Blender 出错：" + out[-600:])
    return out


def mcp_running() -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", MCP_PORT)) == 0


def open_gui(blend: Path | None = None) -> dict:
    """打开带界面的 Blender（可以带一个 .blend），自动开启 MCP 连接，给 Claude Code 或手动编辑用。"""
    blender = find_blender()
    if not blender:
        raise RuntimeError("没有找到 Blender（douyin\\tools\\blender）")
    install_addon()
    cmd = [str(blender)] + ([str(blend)] if blend else []) + ["--python", str(HERE / "startup_mcp.py")]
    subprocess.Popen(cmd, env=env(), cwd=str(HOME))
    return {"started": True, "port": MCP_PORT}


def status() -> dict:
    return {"blender": version(), "path": str(find_blender() or ""), "mcp_port": MCP_PORT, "mcp_running": mcp_running(),
            "addon": (ADDONS / f"{ADDON_NAME}.py").exists()}


if __name__ == "__main__":
    if "--install-addon" in sys.argv:
        print(install_addon())
    elif "--gui" in sys.argv:
        rest = [a for a in sys.argv[1:] if a != "--gui"]
        print(open_gui(Path(rest[0]) if rest else None))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=1))
