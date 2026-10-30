r"""成片保存位置（软件的「视频缓存文件夹」）：默认跟随浏览器的下载文件夹，可以在软件的设置里改。

设置存在 douyin/app_settings.json：{"storage": {"mode": "project" | "browser" | "custom", "path": "自定义文件夹"}}
  project：D:\cc-engine\douyin\待上传（默认；源码版和安装版都存这里，D 盘不能用时退回安装目录里的「待上传」）
  browser：<浏览器下载文件夹>\琴房Studio（依次看 Edge、Chrome 的下载设置；都没设过就用 Windows 的「下载」文件夹）
  custom ：用户选的文件夹（不存在又建不出来、或不能写入时退回 browser）
原来项目里的「待上传」（LEGACY）里的作品仍然会被作品集、发布台读到。
钢琴（piano/render.py）、音轨（tracks/build.py）、拨片开头（tracks/flick_render.py）和琴房服务都从这里取位置。
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "app_settings.json"
LEGACY = ROOT / "待上传"
SUB = "琴房Studio"
PROJECT_DIR = Path(r"D:\cc-engine\douyin\待上传")         # 默认的成片位置（用户指定的固定文件夹）
MODES = ("project", "browser", "custom")
DOWNLOADS_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"     # Windows「下载」文件夹


def _load() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_prefs_cache: dict = {}


def _prefs_download_dir(prefs: Path) -> str | None:
    """浏览器 Preferences 里的下载目录，按文件修改时间缓存（Edge 的 Preferences 有好几百 KB，
    剪辑页的记录线程每隔几秒就要问一次，每次都解析会一直占着服务的 CPU）。"""
    mtime = prefs.stat().st_mtime
    hit = _prefs_cache.get(prefs)
    if hit and hit[0] == mtime:
        return hit[1]
    d = json.loads(prefs.read_text(encoding="utf-8")).get("download", {}).get("default_directory")
    _prefs_cache[prefs] = (mtime, d)
    return d


def browser_download_dir() -> tuple[Path, str]:
    """(浏览器下载文件夹, 来源)。"""
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    for name, prefs in (("Edge", local / "Microsoft" / "Edge" / "User Data" / "Default" / "Preferences"),
                        ("Chrome", local / "Google" / "Chrome" / "User Data" / "Default" / "Preferences")):
        try:
            d = _prefs_download_dir(prefs)
        except (OSError, ValueError):
            continue
        if d and Path(d).is_dir():
            return Path(d), f"{name} 的下载文件夹"
    try:      # 浏览器都用默认设置：就是 Windows 的「下载」文件夹（可能被挪到了别的盘）
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            d = os.path.expandvars(winreg.QueryValueEx(k, DOWNLOADS_GUID)[0])
        if Path(d).is_dir():
            return Path(d), "浏览器默认的下载文件夹（Windows「下载」）"
    except OSError:
        pass
    return Path.home() / "Downloads", "浏览器默认的下载文件夹（Windows「下载」）"


def settings() -> dict:
    s = _load().get("storage") or {}
    return {"mode": s.get("mode") if s.get("mode") in MODES else "project", "path": s.get("path", "")}


def _usable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".qinfang_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def project_dir() -> Path:
    """「待上传」：固定的 PROJECT_DIR，不能用时退回本程序目录里的「待上传」。"""
    return PROJECT_DIR if PROJECT_DIR.is_dir() or _usable(PROJECT_DIR) else LEGACY


def deliver_dir() -> Path:
    """新生成的成片放在这里（每条一个子文件夹）。"""
    s = settings()
    if s["mode"] == "custom" and s["path"] and Path(s["path"]).is_absolute():
        p = Path(s["path"])
        if p.is_dir() or _usable(p):
            return p
    if s["mode"] == "browser":
        return browser_download_dir()[0] / SUB
    return project_dir()


def all_dirs() -> list[Path]:
    """作品集、发布台要读的所有位置：当前位置 + 「待上传」+ 本程序目录里的「待上传」+ 浏览器下载文件夹里的「琴房Studio」
    （换过保存位置后，以前的成片也还能看到）。"""
    dirs = []
    for d in (deliver_dir(), PROJECT_DIR, LEGACY, browser_download_dir()[0] / SUB):
        try:
            if d.is_dir() and all(d.resolve() != x.resolve() for x in dirs):
                dirs.append(d)
        except OSError:
            continue
    return dirs or [deliver_dir()]


def inside(p: Path) -> bool:
    """p 在某个成片位置里面（作品的视频、封面、文件夹）。"""
    try:
        rp = Path(p).resolve()
    except OSError:
        return False
    for d in all_dirs():
        try:
            rp.relative_to(d.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def info() -> dict:
    s, (bdir, src) = settings(), browser_download_dir()
    return {"mode": s["mode"], "path": s["path"], "resolved": str(deliver_dir()),
            "project": str(project_dir()),
            "browser": {"dir": str(bdir / SUB), "source": src},
            "legacy": str(LEGACY) if LEGACY.is_dir() else ""}


UI_KEYS = {"studio.ui.v1", "qinfang.tour", "studio.tab", "flick.settings", "tracks.song"}


def ui_state() -> dict:
    """网页的设置（主题、强调色、发布平台勾选、上次的页面……）在服务端的备份。
    浏览器的 localStorage 按「地址:端口」分开存，端口一变就像全新安装；存在这里就不会丢。"""
    s = _load().get("ui_state") or {}
    return {"ts": s.get("ts", 0), "keys": {k: v for k, v in (s.get("keys") or {}).items() if k in UI_KEYS}}


def set_ui_state(ts: float, keys: dict) -> dict:
    data = _load()
    clean = {k: str(v) for k, v in (keys or {}).items() if k in UI_KEYS and v is not None and len(str(v)) < 20000}
    data["ui_state"] = {"ts": float(ts or 0), "keys": clean}
    SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return ui_state()


def set_storage(mode: str, path: str = "") -> dict:
    """保存设置。自定义文件夹要是完整路径，并且能建、能写。"""
    if mode not in MODES:
        raise ValueError("未知的保存方式")
    path = (path or "").strip().strip('"')
    if mode == "custom":
        p = Path(path)
        if not path or not p.is_absolute():
            raise ValueError("请选择一个完整的文件夹路径，例如 D:\\视频\\琴房")
        if not _usable(p):
            raise ValueError(f"这个文件夹不能写入：{p}")
    data = _load()
    data["storage"] = {"mode": mode, "path": path if mode == "custom" else ""}
    SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return info()
