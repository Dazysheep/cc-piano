"""手绘工作室 → 素材库。

  python handdrawn/export.py expressions [名字…]          表情库：male_* / female_* → assets/clawd/handdrawn/<male|female>/<名>.webp
  python handdrawn/export.py song <歌曲文件夹> [场景…]      这首歌的手绘画面 → assets/handdrawn/<歌>/<场景>/f0000.png… + 预览 <场景>.webp

透明场景是画在纯纸色底上的（水彩直接画在透明上会起白边），这里从画面四周把连着边的纸色抠掉；墨线是封闭的，抠得干净。
渲染走 render.mjs（无头 Edge），先拿 douyin 的渲染锁，不和整片渲染抢内存。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tracks"))
import anim_lib  # noqa: E402
import build  # noqa: E402

TMP = Path(r"D:\cc-engine\.tmp\handdrawn")
KEY = np.array([243, 235, 220], dtype=np.int16)        # = core.js 的 KEY_BG
FPS = 12
ENV = Path(r"D:\cc-engine\filmlab\env.sh")


def run_render(*args: str) -> str:
    cmd = f'. "{ENV.as_posix()}" && cd "{HERE.as_posix()}" && node render.mjs ' + " ".join(f'"{a}"' for a in args)
    r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(r.stdout[-800:] + r.stderr[-800:])
    return r.stdout


def scene_list(song: str | None = None) -> dict:
    out = run_render("--list", *( [f"--song={song}"] if song else []))
    rows = {}
    for ln in out.splitlines():
        p = ln.split("\t")
        if len(p) >= 5:
            rows[p[0]] = {"size": p[1], "dur": float(p[2].rstrip("s")), "alpha": p[3] == "透明", "zh": p[4]}
    return rows


def key_out(im: Image.Image, tol: int = 26) -> Image.Image:
    """从四周把连着边的底色抠成透明，边缘留 1 像素羽化。"""
    a = np.asarray(im.convert("RGB"), dtype=np.int16)
    near = np.abs(a - KEY).max(axis=2) < tol
    lab, _ = ndimage.label(near)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bg = np.isin(lab, edge[edge > 0])
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    soft = ndimage.uniform_filter(alpha.astype(np.float32), size=3)
    alpha = np.where(bg, 0, np.maximum(soft, 0)).astype(np.uint8)
    rgba = np.dstack([np.asarray(im.convert("RGB")), alpha])
    return Image.fromarray(rgba, "RGBA")


def frames_of(scene: str, song: str | None, out: Path) -> list[Path]:
    if out.exists():
        shutil.rmtree(out)
    lock = build.render_lock()                          # 返回打开的锁文件，关掉就释放
    try:
        run_render(f"--scene={scene}", "--frames", f"--fps={FPS}", f"--out={out.as_posix()}", *([f"--song={song}"] if song else []))
    finally:
        lock.close()
    return sorted(out.glob("f*.png"))


def expressions(names: list[str]) -> list[Path]:
    rows = scene_list()
    done = []
    for name, info in rows.items():
        if not (name.startswith("male_") or name.startswith("female_")) or (names and name not in names):
            continue
        who, short = name.split("_", 1)
        fs = frames_of(name, None, TMP / name)
        frames = [key_out(Image.open(f)) for f in fs]
        dst = ROOT / "assets" / "clawd" / "handdrawn" / who / f"{short}.webp"
        anim_lib.trimmed_webp(frames, dst, fps=FPS)
        done.append(dst)
        print(f"{name} → {dst.relative_to(ROOT)}（{len(frames)} 帧）{info['zh']}")
    idx = ROOT / "assets" / "clawd" / "handdrawn" / "index.json"
    cur = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    for name, info in rows.items():
        if name.startswith(("male_", "female_")):
            who, short = name.split("_", 1)
            cur.setdefault(who, {})[short] = info["zh"]
    idx.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    return done


def song(song: str, names: list[str]) -> list[Path]:
    rows = scene_list(song)
    base = ROOT / "assets" / "handdrawn" / song
    done = []
    for name, info in rows.items():
        if name.startswith(("male_", "female_")) or (names and name not in names):
            continue
        fs = frames_of(name, song, TMP / song / name)
        dst = base / name
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        frames = []
        for i, f in enumerate(fs):
            im = Image.open(f)
            im = key_out(im) if info["alpha"] else im.convert("RGBA")
            im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)      # 场景按 2 倍画，存 1 倍（更细）
            im.save(dst / f"f{i:04d}.png")
            frames.append(im)
        frames[0].save(base / f"{name}.webp", save_all=True, append_images=frames[1::2], duration=int(2000 / FPS), loop=0,
                       quality=80, method=4)
        done.append(dst)
        print(f"{name} → {dst.relative_to(ROOT)}（{len(frames)} 帧）{info['zh']}")
    idx = base / "index.json"
    idx.write_text(json.dumps({k: {"zh": v["zh"], "dur": v["dur"], "fps": FPS} for k, v in rows.items()
                               if not k.startswith(("male_", "female_"))}, ensure_ascii=False, indent=1), encoding="utf-8")
    return done


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("expressions", "song"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "expressions":
        expressions(sys.argv[2:])
    else:
        song(sys.argv[2], sys.argv[3:])
