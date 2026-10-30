"""手绘片 → 分层素材 + OpenFilm 分轨工程（剪辑页里按人物 / 背景 / 道具 / 字幕 / 转场 / 人声 / 伴奏分轨剪）。

  python handdrawn/layers.py render <歌曲文件夹>        渲染各层逐帧（可续跑，已有的帧跳过）
  python handdrawn/layers.py build <歌曲文件夹> <作品文件夹>   抠像 + 编码各层，写 <作品文件夹>/film/film.html

分层规则在 engine/core.js（layer=… 只画带这个标签的东西）：
  bg      背景（没有标签的一切）           → assets/bg.mp4（不透明）
  male    男主 CC（默认橙色的 clawd）       → assets/male.webm（透明）
  others  其他角色（女主、路人、妈妈、猫…）  → assets/others.webm
  props   道具（纸飞机、对话气泡、单独的表情符号） → assets/props.webm
  字幕：不渲染成视频层，每句歌词是一个可编辑的网页片段 pages/sub_NN.html（editor_pages/subtitle.*，手写体逐字亮起，剪辑器里能改字）
  trans   转场                              → assets/trans.webm
前景层各渲一遍黑底、一遍白底，两张相减得到透明度（alpha = 1 − (白 − 黑)），颜色 = 黑底 / alpha。
声音：tracks 准备好的分轨 → 人声（vocals）和伴奏（其余各轨相加），各按段落切成片段（不放歌词 .vtt：剪辑器会再显示一遍，和字幕重复）。
轨道里的片段：背景 / 人物 / 道具按镜头切，字幕按歌词句切，转场按剪切点切，都指向同一个素材文件的不同时间段。
"""
import html
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tracks"))
import build  # noqa: E402

FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
TMP = Path(r"D:\cc-engine\.tmp\handdrawn\layers")
FPS = 12
FG = ["male", "others", "props", "trans"]
ZH = {"bg": "背景", "male": "人物 · 男主 CC", "others": "人物 · 其他角色（女主 / 路人 / 妈妈 / 猫）", "props": "道具（纸飞机 / 对话气泡 / 符号）",
      "subs": "字幕（歌词逐字）", "trans": "转场动画", "vocals": "人声", "accomp": "伴奏"}


def film_data(song: str) -> dict:
    s = (HERE / "songs" / song / "film_data.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("{"): s.rindex("}") + 1])


# ---------------------------------------------------------------- 渲染
def jobs(song: str, dur: float) -> list[list[str]]:
    """每个渲染任务：(层, 底色, 起, 止)。背景最重，切三段；前景层各两遍。"""
    out = []
    for a, b in ((0, 90), (90, 180), (180, dur + .1)):
        out.append(["bg", "", str(a), str(b)])
    for layer in FG:
        for matte in ("black", "white"):
            out.append([layer, matte, "0", str(dur + .1)])
    return out


def render(song: str, parallel: int = 4) -> None:
    d = film_data(song)
    queue, running = jobs(song, d["dur"]), []
    env_sh = Path(r"D:\cc-engine\filmlab\env.sh").as_posix()
    while queue or running:
        while queue and len(running) < parallel:
            layer, matte, a, b = queue.pop(0)
            name = layer + (f"_{matte}" if matte else "")
            out = TMP / song / name
            out.mkdir(parents=True, exist_ok=True)
            fmt = "--jpg" if layer == "bg" else ""
            cmd = (f'. "{env_sh}" && cd "{HERE.as_posix()}" && node render.mjs --song="{song}" --scene=film --frames --fps={FPS} {fmt} '
                   f'--layer={layer} {"--matte=" + matte if matte else ""} --from={a} --to={b} --out="{out.as_posix()}"')
            log = open(TMP / song / f"{name}_{a}.log", "w", encoding="utf-8")
            running.append((name, subprocess.Popen(["bash", "-lc", cmd], stdout=log, stderr=subprocess.STDOUT)))
            print("开始", name, a, b, flush=True)
        time.sleep(5)
        for item in running[:]:
            if item[1].poll() is not None:
                running.remove(item)
                print("完成", item[0], "退出码", item[1].returncode, flush=True)


# ---------------------------------------------------------------- 抠像 + 编码
def _ffmpeg(args: list[str], stdin=None):
    return subprocess.Popen([str(FF), "-y", "-loglevel", "error", *args], stdin=stdin)


def encode_matte(song: str, layer: str, n: int, dst: Path) -> None:
    """黑底 / 白底两套 PNG → RGBA → VP9 透明 webm（逐帧通过管道，不落中间文件）。"""
    b_dir, w_dir = TMP / song / f"{layer}_black", TMP / song / f"{layer}_white"
    p = _ffmpeg(["-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1920x1080", "-r", str(FPS), "-i", "-",
                 "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32", "-row-mt", "1", "-deadline", "good",
                 "-cpu-used", "4", "-auto-alt-ref", "0", str(dst)], stdin=subprocess.PIPE)
    empty = np.zeros((1080, 1920, 4), np.uint8).tobytes()
    for i in range(n):
        fb, fw = b_dir / f"f{i:04d}.png", w_dir / f"f{i:04d}.png"
        if not (fb.exists() and fw.exists()):
            p.stdin.write(empty)
            continue
        bk = np.asarray(Image.open(fb).convert("RGB"), np.float32)
        wh = np.asarray(Image.open(fw).convert("RGB"), np.float32)
        a = np.clip(1 - (wh - bk).mean(axis=2) / 255, 0, 1)
        a[a < .02] = 0
        rgb = np.clip(bk / np.maximum(a, 1e-3)[..., None], 0, 255)
        p.stdin.write(np.dstack([rgb, a * 255]).astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"编码 {layer} 失败")


def encode_bg(song: str, dst: Path) -> None:
    run = subprocess.run([str(FF), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(TMP / song / "bg" / "f%04d.jpg"),
                          "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", str(dst)],
                         capture_output=True, text=True, errors="replace")
    if run.returncode:
        raise RuntimeError(run.stderr[-800:])


def audio(work: Path, assets: Path, dur: float) -> None:
    stems = work / "stems"
    run = subprocess.run([str(FF), "-y", "-loglevel", "error", "-i", str(stems / "vocals.wav"), "-t", str(dur), "-ar", "48000", str(assets / "vocals.wav")],
                         capture_output=True, text=True, errors="replace")
    if run.returncode:
        raise RuntimeError(run.stderr[-500:])
    others = [p for p in sorted(stems.glob("*.wav")) if p.stem != "vocals"]
    args = [x for p in others for x in ("-i", str(p))]
    run = subprocess.run([str(FF), "-y", "-loglevel", "error", *args, "-filter_complex",
                          f"amix=inputs={len(others)}:normalize=0", "-t", str(dur), "-ar", "48000", str(assets / "accomp.wav")],
                         capture_output=True, text=True, errors="replace")
    if run.returncode:
        raise RuntimeError(run.stderr[-500:])


# ---------------------------------------------------------------- 字幕：剪辑器里可编辑的手绘字幕片段（一句一个网页片段）
PAGES = HERE / "editor_pages"
BOX_W, BOX_H = 1600, 220
SUB_BOX = {"top": (160, 30, ""), "bottom": (160, 830, ""), "center": (160, 430, ""), "left": (40, 430, "left"), "right": (280, 430, "right"),
           "top_left": (40, 30, "left"), "top_right": (280, 30, "right"), "bottom_left": (40, 830, "left"), "bottom_right": (280, 830, "right")}


def subtitle_pages(film_dir: Path, d: dict, cap: float) -> list[dict]:
    """每句歌词写一个 pages/sub_NN.html（文字可在剪辑器里改，逐字亮起的时间写在 data-times），返回片段信息。"""
    pages = film_dir / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    for f in ("subtitle.js", "subtitle.css"):
        shutil.copy(PAGES / f, pages / f)
    for f in ("ZCOOLKuaiLe-Regular.ttf", "OFL.txt"):
        shutil.copy(HERE / "fonts" / f, pages / f)
    for old in pages.glob("sub_*.html"):
        old.unlink()
    shots, lines, out = d["shots"], d["lines"], []
    for i, ln in enumerate(lines):
        nxt = next((m for m in lines[i + 1:] if m["s"] > ln["s"] + .01), None)
        a = max(0.0, ln["s"] - .12)
        b = min(cap, min(ln["e"] + .5, nxt["s"] - .02) if nxt else ln["e"] + .5)
        if b - a < .2:
            continue
        same = [m for m in lines[i + 1:] if abs(m["s"] - ln["s"]) <= .01]          # 同时出现的两句（I pray for you / 我为你祈祷）
        if out and abs(out[-1]["a"] - a) < .01:
            continue
        shot = next((s for s in reversed(shots) if s["from"] <= ln["s"] + .05), shots[0])
        x, y, cls = SUB_BOX.get(shot["sub"], SUB_BOX["bottom"])
        texts = [ln["text"]] + [m["text"] for m in same]
        times = [round(w[1] - a, 3) for w in ln["w"]] if ln["w"] else []
        body = "<br>".join(html.escape(p) for t in texts for p in t.split("，"))
        k = len(out)
        doc = "\n".join([
            '<!doctype html>', '<html lang="zh-CN">', '<head>', '<meta charset="utf-8">', f'<title>{html.escape(texts[0])}</title>',
            '<link rel="stylesheet" href="subtitle.css">', '</head>', f'<body class="{cls}">', '<div id="wrap">',
            f'<p id="line" data-times="{json.dumps(times)}" data-dur="{round(ln["e"] - a, 3)}" data-len="{round(b - a, 3)}" data-size="64">{body}</p>',
            '<p id="hi" aria-hidden="true"></p>', '</div>', '<script src="subtitle.js"></script>', '</body>', '</html>', ''])
        (pages / f"sub_{k:02d}.html").write_text(doc, encoding="utf-8")
        out.append({"id": f"sub_{k:02d}", "src": f"pages/sub_{k:02d}.html", "a": round(a, 3), "b": round(b, 3), "x": x, "y": y, "text": " / ".join(texts)})
    return out


# ---------------------------------------------------------------- 工程
def clip(tag: str, cid: str, src: str, a: float, b: float, title: str = "") -> str:
    t = f' title="{html.escape(title)}"' if title else ""
    return f'  <{tag} id="{cid}" src="{src}#t={a:.3f},{b:.3f}" at="{a:.3f}"{t}></{tag}>'


def film_html(song: str, title: str, d: dict, dur: float, sub_pages: list[dict]) -> str:
    shots = d["shots"]
    end = lambda x: min(x, dur - .002)   # noqa: E731
    per_shot = lambda layer, tag="video", ext="webm": [clip(tag, f"{layer}_{i:02d}", f"assets/{layer}.{ext}", s["from"], end(s["to"]), s["zh"])   # noqa: E731
                                                     for i, s in enumerate(shots)]
    subs = [f'  <iframe id="{p["id"]}" src="{p["src"]}#t=0,{p["b"] - p["a"]:.3f}" at="{p["a"]:.3f}" title="{html.escape(p["text"])}" '
            f'style="left: {p["x"]}px; top: {p["y"]}px; width: {BOX_W}px; height: {BOX_H}px"></iframe>' for p in sub_pages]
    trans = [clip("video", f"trans_{i:02d}", "assets/trans.webm", max(0, s["from"] - .2), end(s["from"] + .2), s["tr"])
             for i, s in enumerate(shots) if i > 0]
    secs = [0.0] + [s["from"] for s in shots if s["lines"][0] in (1, 26, 34, 50, 58, 81, 999)] + [dur]
    secs = sorted(set(round(x, 3) for x in secs))
    audio_clips = lambda name: [clip("audio", f"{name}_{i}", f"assets/{name}.wav", a, end(b)) for i, (a, b) in enumerate(zip(secs, secs[1:])) if b - a > .3]   # noqa: E731
    tracks = [("trans", trans), ("subs", subs), ("props", per_shot("props")), ("male", per_shot("male")),
              ("others", per_shot("others")), ("bg", per_shot("bg", ext="mp4")), ("vocals", audio_clips("vocals")), ("accomp", audio_clips("accomp"))]
    body = "\n".join(f'<section title="{html.escape(ZH[name])}" data-layer="{name}">\n' + "\n".join(cl) + "\n</section>" for name, cl in tracks)
    return (f'<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=1920, height=1080">\n'
            f'<title>{html.escape(title)}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n')


def build_project(song: str, work_folder: Path, title: str, work: Path) -> Path:
    d = film_data(song)
    dur = d["dur"]
    n = round(dur * FPS)
    assets = work_folder / "film" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    lock = build.render_lock()
    try:
        encode_bg(song, assets / "bg.mp4")
        print("背景 ok", flush=True)
        for layer in FG:
            encode_matte(song, layer, n, assets / f"{layer}.webm")
            print(layer, "ok", flush=True)
        audio(work, assets, dur)
    finally:
        lock.close()
    return write_project(song, work_folder, title)


def write_project(song: str, work_folder: Path, title: str) -> Path:
    """只重写字幕页面和 film.html（素材已经编码好时用）。"""
    d = film_data(song)
    n = round(d["dur"] * FPS)
    film = work_folder / "film"
    for old in (film / "assets" / "subs.webm", film / "assets" / "vocals.vtt"):     # 字幕不再烧成视频层、不放歌词 .vtt（剪辑器会再显示一遍，重复）
        old.unlink(missing_ok=True)
    cap = min(d["dur"], n / FPS) - .002                          # 片段不能超过素材的实际长度（帧数取整）
    doc = film_html(song, title, d, cap + .002, subtitle_pages(film, d, cap))
    (film / "film.html").write_text(doc, encoding="utf-8")
    return film / "film.html"


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "render":
        render(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "build":
        wf = Path(sys.argv[3])
        work_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / "output" / "tracks_你有多久没有抬起头认真的数过星星" / "work"
        print(build_project(sys.argv[2], wf, sys.argv[5] if len(sys.argv) > 5 else wf.name, work_dir))
    elif len(sys.argv) >= 4 and sys.argv[1] == "project":       # 只重写字幕页面 + film.html：layers.py project <歌> <作品文件夹> [标题]
        wf = Path(sys.argv[3])
        print(write_project(sys.argv[2], wf, sys.argv[4] if len(sys.argv) > 4 else wf.name))
    else:
        print(__doc__)
