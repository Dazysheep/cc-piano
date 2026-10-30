"""cc-piano「3D 建模」的后台：是否启用、3D 建模库文件夹（douyin/model3d.json）、库里的模型列表、生成、删除。

- 没启用时什么都不读：库文件夹不加进网页可读的范围，左侧功能栏也没有「3D 建模」。
- 库文件夹默认 douyin/models3d，可以在设置里换成任意文件夹（比如自己的素材盘）。
- 生成：本地（image2mesh.py：抠图 + 深度 → 后台 Blender 做立体浮雕）或云端（cloud3d.py：blender-mcp 插件里的
  Hyper3D Rodin，前后都完整；密钥只放用户环境变量 BLENDERMCP_HYPER3D_API_KEY）。
"""
import json
import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = ROOT / "model3d.json"
DEFAULT_DIR = ROOT / "models3d"
CLOUD_KEY_ENV = "BLENDERMCP_HYPER3D_API_KEY"


def config() -> dict:
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        c = {}
    custom = (c.get("dir") or "").strip()
    return {"enabled": bool(c.get("enabled")), "dir": custom or str(DEFAULT_DIR), "custom": bool(custom)}


def set_config(enabled: bool | None = None, folder: str | None = None) -> dict:
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        c = {}
    if enabled is not None:
        c["enabled"] = bool(enabled)
    if folder is not None:
        folder = folder.strip().strip('"')
        if folder:
            p = Path(folder)
            if not p.is_absolute():
                raise ValueError("请填完整的文件夹路径，例如 D:\\3D模型库")
            p.mkdir(parents=True, exist_ok=True)
        c["dir"] = folder
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    out = config()
    if out["enabled"]:
        Path(out["dir"]).mkdir(parents=True, exist_ok=True)
    return out


def library_dir() -> Path | None:
    """启用时返回建模库文件夹；没启用返回 None（网页不能读、也不列出）。"""
    c = config()
    return Path(c["dir"]) if c["enabled"] else None


def inside_library(p: Path) -> bool:
    lib = library_dir()
    if not lib:
        return False
    try:
        Path(p).resolve().relative_to(lib.resolve())
        return True
    except ValueError:
        return False


def blocked(p: Path) -> bool:
    """没启用时，建模库里的文件（默认库在项目目录里，项目目录本来是整体可读的）也不给网页读。"""
    c = config()
    if c["enabled"]:
        return False
    for d in {Path(c["dir"]), DEFAULT_DIR}:
        try:
            Path(p).resolve().relative_to(d.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def models() -> list[dict]:
    """库里的模型（有 model.glb 的子文件夹），新的在前。"""
    lib = library_dir()
    if not lib or not lib.is_dir():
        return []
    out = []
    for d in sorted((p for p in lib.iterdir() if p.is_dir() and (p / "model.glb").exists()),
                    key=lambda p: (p / "model.glb").stat().st_mtime, reverse=True):
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        out.append({"name": d.name, "dir": str(d), "glb": str(d / "model.glb"),
                    "thumb": str(d / "thumb.png") if (d / "thumb.png").exists() else None,
                    "blend": str(d / "model.blend") if (d / "model.blend").exists() else None,
                    "kind": meta.get("kind", ""), "created": meta.get("created", ""),
                    "size_mb": round((d / "model.glb").stat().st_size / 1e6, 2)})
    return out


def model_dir(name: str) -> Path:
    lib = library_dir()
    if not lib:
        raise ValueError("3D 建模还没有启用")
    d = (lib / name).resolve()
    if d.parent != lib.resolve() or not d.is_dir():
        raise FileNotFoundError(f"没有这个模型：{name}")
    return d


def delete(name: str) -> None:
    shutil.rmtree(model_dir(name))


def cloud_ready() -> bool:
    key = os.environ.get(CLOUD_KEY_ENV, "")
    if not key and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, CLOUD_KEY_ENV)[0]
        except OSError:
            key = ""
    return bool(key)


def generate(image: Path, name: str = "", mode: str = "local", strength: float = 0.35, thickness: float = 0.04,
             smooth: float = 2.0, progress=None) -> dict:
    lib = library_dir()
    if not lib:
        raise ValueError("3D 建模还没有启用：在「设置 → 3D 建模」里打开")
    import sys
    sys.path.insert(0, str(HERE))
    if mode == "cloud":
        import cloud3d
        out = cloud3d.make(Path(image), lib, name or None, progress=progress)
    else:                    # 本地：单独的低优先级子进程跑抠图、深度和 Blender（不占琴房服务进程，界面不卡）
        import re
        import subprocess
        cmd = [sys.executable, str(HERE / "image2mesh.py"), str(image), "--lib", str(lib),
               "--strength", str(max(0.05, min(1.0, strength))), "--thickness", str(max(0.005, min(0.2, thickness))),
               "--smooth", str(max(0.0, min(8.0, smooth)))] + (["--name", name] if name else [])
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                creationflags=0x08000000 | 0x00004000)
        tail, last = [], None
        for line in proc.stdout:
            line = line.strip()
            m = re.match(r"^(\d+)% (.+)$", line)
            if m and progress:
                progress(int(m.group(1)) / 100, m.group(2))
            elif line:
                tail = (tail + [line])[-6:]
                last = line
        proc.wait()
        if proc.returncode != 0 or not last or not Path(last).is_dir():
            raise RuntimeError("生成失败：" + " / ".join(tail[-3:]))
        out = Path(last)
    return {"name": out.name, "dir": str(out)}
