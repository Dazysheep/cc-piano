"""图片 → 3D（本地）：抠图 + 估深度（onnxruntime，模型在 douyin/tools/models），再交给后台 Blender（relief.py）
做成有厚度的立体浮雕，导出到 3D 建模库：

  <库>/<名字>/source.png   原图
              cutout.png   抠出来的主体（透明背景，裁到主体范围）
              depth.png    深度图（16 位灰度，越亮越近）
              model.glb    模型（贴图内嵌，网页预览和别的软件都能用）
              model.blend  Blender 工程（可以在 Blender 里继续改）
              thumb.png    缩略图
              meta.json    参数和来源

抠图：isnet-general-use（和 rembg 同一个模型，这里直接用 onnxruntime 跑，不装 rembg 那一大堆依赖）。
深度：Depth Anything V2 Small（ONNX）。图片本来就有透明背景（PNG）时直接用它的透明度，不再抠。
正面是立体的，背面是平的（单张图看不到背面）；要前后都完整的模型用云端（cloud3d.py）。
用法：python blender3d/image2mesh.py <图片> [--name 名字] [--lib 库文件夹] [--strength 0.35] [--thickness 0.04] [--smooth 2]
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODELS = ROOT / "tools" / "models"
ISNET = MODELS / "rembg" / "isnet-general-use.onnx"
DEPTH = MODELS / "depth" / "depth-anything-v2-small.onnx"
_sessions: dict = {}


def _session(path: Path):
    import onnxruntime as ort
    if path not in _sessions:
        if not path.exists():
            raise FileNotFoundError(f"缺少模型文件：{path}")
        so = ort.SessionOptions()                           # 最多用一半 CPU 核心：生成时界面不卡
        so.intra_op_num_threads = max(2, (os.cpu_count() or 4) // 2)
        _sessions[path] = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
    return _sessions[path]


def cutout(img: Image.Image) -> Image.Image:
    """主体抠出来（RGBA）。图片自带透明度时直接用。"""
    img = img.convert("RGBA")
    a = np.asarray(img)[..., 3]
    if a.min() < 250 and (a < 128).mean() > 0.02:          # 本来就是透明背景的图
        return img
    rgb = img.convert("RGB")
    x = np.asarray(rgb.resize((1024, 1024), Image.LANCZOS), np.float32)
    x = x / max(float(x.max()), 1e-6)
    x = (x - 0.5) / 1.0                                     # isnet-general-use：mean 0.5、std 1.0（和 rembg 一样）
    sess = _session(ISNET)
    pred = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    pred = (pred - pred.min()) / max(float(pred.max() - pred.min()), 1e-6)
    pred = np.clip((pred - 0.12) / 0.45, 0, 1)              # 边界放宽、透明度变「硬」：深色衣服这类低置信的部分也留下
    mask = Image.fromarray((pred * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS)
    out = rgb.copy()
    out.putalpha(mask)
    return out


def crop_subject(im: Image.Image, pad: float = 0.04) -> Image.Image:
    """裁到主体范围（四周留一点边）。"""
    a = np.asarray(im)[..., 3]
    ys, xs = np.where(a > 24)
    if not len(xs):
        raise ValueError("没有抠出主体：换一张主体更清楚的图片试试")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    p = int(max(x1 - x0, y1 - y0) * pad)
    return im.crop((max(0, x0 - p), max(0, y0 - p), min(im.width, x1 + p + 1), min(im.height, y1 + p + 1)))


def depth_map(im: Image.Image, smooth: float) -> Image.Image:
    """相对深度（越近越亮，0~65535），只在主体范围里归一化，再按 smooth 平滑。"""
    rgb = im.convert("RGB")
    x = np.asarray(rgb.resize((518, 518), Image.BICUBIC), np.float32) / 255.0
    x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    sess = _session(DEPTH)
    d = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0]
    d = np.asarray(d).reshape(d.shape[-2], d.shape[-1])
    d = np.asarray(Image.fromarray(d.astype(np.float32), "F").resize(im.size, Image.BICUBIC))
    a = np.asarray(im)[..., 3] > 128
    lo, hi = np.percentile(d[a], 2), np.percentile(d[a], 98)
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    d[~a] = 0
    img = Image.fromarray((d * 255).astype(np.uint8))
    if smooth > 0:
        img = img.filter(ImageFilter.GaussianBlur(smooth))
    d16 = (np.asarray(img, np.float32) / 255.0 * 65535).astype(np.uint16)
    return Image.fromarray(d16, "I;16")


def slug(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|\s]+", "_", s).strip("_")
    return s[:40] or "model"


def make(src: Path, lib: Path, name: str | None = None, strength: float = 0.35, thickness: float = 0.04,
         smooth: float = 2.0, progress=None) -> Path:
    """一张图 → 建模库里的一个模型文件夹，返回文件夹。"""
    import blender as bl
    say = progress or (lambda u, m: None)
    t0 = time.time()
    lib, src = Path(lib).resolve(), Path(src).resolve()     # 交给 Blender 的路径必须是绝对路径（它的工作目录不一样）
    name = slug(name or src.stem)
    out = lib / name
    n = 2
    while out.exists():
        out = lib / f"{name}_{n}"
        n += 1
    out.mkdir(parents=True)
    img = Image.open(src)
    img.load()
    if max(img.size) > 1400:                                # 太大的图先缩小（模型网格和贴图都用不了那么大）
        img.thumbnail((1400, 1400), Image.LANCZOS)
    img.save(out / "source.png")
    say(0.1, "抠图")
    cut = crop_subject(cutout(img))
    cut.save(out / "cutout.png")
    say(0.35, "估算深度")
    depth_map(cut, smooth).save(out / "depth.png")
    say(0.55, "Blender 建模（后台）")
    bl.run_background(HERE / "relief.py", ["--dir", out, "--strength", strength, "--thickness", thickness],
                      log=out / "blender.log")
    if not (out / "model.glb").exists():
        raise RuntimeError("Blender 没有导出模型，详见 " + str(out / "blender.log"))
    meta = {"name": out.name, "source": str(src), "kind": "relief", "created": datetime.now().isoformat(timespec="seconds"),
            "strength": strength, "thickness": thickness, "smooth": smooth, "blender": bl.version(),
            "seconds": round(time.time() - t0, 1), "size": list(cut.size)}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    say(1.0, "完成")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="图片 → 3D 立体浮雕（本地）")
    ap.add_argument("image", type=Path)
    ap.add_argument("--name")
    ap.add_argument("--lib", type=Path, default=ROOT / "models3d")
    ap.add_argument("--strength", type=float, default=0.35)
    ap.add_argument("--thickness", type=float, default=0.04)
    ap.add_argument("--smooth", type=float, default=2.0)
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    print(make(a.image, a.lib, a.name, a.strength, a.thickness, a.smooth, lambda u, m: print(f"{int(u * 100)}% {m}")))
