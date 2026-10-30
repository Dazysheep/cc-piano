"""图片 → 3D（云端）：blender-mcp 插件里的 Hyper3D Rodin，生成前后都完整的模型（要 Hyper3D 的密钥，按次计费）。
在后台 Blender 里跑 cloud3d_blender.py；密钥只从用户环境变量 BLENDERMCP_HYPER3D_API_KEY 读，不写文件。
输出和本地浮雕一样放进 3D 建模库：source.png、model.glb、model.blend、thumb.png、meta.json。
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

import blender as bl
import image2mesh
import model3d_lib

HERE = Path(__file__).resolve().parent


def make(src: Path, lib: Path, name: str | None = None, progress=None) -> Path:
    say = progress or (lambda u, m: None)
    if not model3d_lib.cloud_ready():
        raise PermissionError("还没有 Hyper3D 的密钥：在 Windows 用户环境变量里添加 BLENDERMCP_HYPER3D_API_KEY 后重启琴房")
    if not os.environ.get(model3d_lib.CLOUD_KEY_ENV):          # 刚设的用户环境变量：从注册表读给后台 Blender
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            os.environ[model3d_lib.CLOUD_KEY_ENV] = winreg.QueryValueEx(k, model3d_lib.CLOUD_KEY_ENV)[0]
    t0 = time.time()
    lib, src = Path(lib).resolve(), Path(src).resolve()
    base = image2mesh.slug(name or src.stem)
    out, n = lib / base, 2
    while out.exists():
        out, n = lib / f"{base}_{n}", n + 1
    out.mkdir(parents=True)
    img = Image.open(src)
    img.load()
    img.thumbnail((1400, 1400), Image.LANCZOS)
    img.convert("RGBA").save(out / "source.png")
    say(0.1, "上传到 Hyper3D，云端生成中（通常 1~3 分钟）")
    bl.run_background(HERE / "cloud3d_blender.py", ["--dir", out, "--image", out / "source.png"], timeout=1200,
                      log=out / "blender.log")
    if not (out / "model.glb").exists():
        raise RuntimeError("没有拿到模型，详见 " + str(out / "blender.log"))
    (out / "meta.json").write_text(json.dumps({"name": out.name, "source": str(src), "kind": "cloud:hyper3d",
                                               "created": datetime.now().isoformat(timespec="seconds"),
                                               "blender": bl.version(), "seconds": round(time.time() - t0, 1)},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    say(1.0, "完成")
    return out
