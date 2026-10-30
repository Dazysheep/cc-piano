"""剪辑页「导入文件夹」（用户 2026-10-30：不只剪整条成片，也能导入一个文件夹，读文件夹名和里面的视频来分轨剪辑）。

文件复制进 <成片位置>/导入_<文件夹名>/film/assets/（原文件夹挪走、删掉都不影响），工程名 = 文件夹名，写 film/film.html：
- 每个子文件夹一组轨道（轨道名带文件夹名），文件按「自然顺序」（1、2、10）排，组和组首尾相接；
- 视频：画面一轨（静音，长视频按画面切换点切成几个片段，方便删改重排）+ 原声单独一轨（抽成 m4a，整段一个片段）；
- 图片：图片一轨，每张 3 秒，和视频按文件名顺序接在同一条时间线上；
- 音频（mp3 / wav / m4a / flac …）：音频一轨，从这组开头依次排；
- 字幕（.srt / .vtt）：每条字幕一个可以直接改字的网页片段（和手绘动画同一套手写字幕页），同名视频的字幕跟着那个视频的开始时间；
  不放 .vtt 文件（剪辑器会自己再显示一遍，重复）。
画布尺寸取第一个视频（没有视频取第一张图）的分辨率。job.json 写 {kind: "import", title, source}。

  python editor/importer.py <文件夹> [--json-progress]
"""
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.append(str(ROOT / "piano"))
FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
FP = FF.with_name("ffprobe.exe")
SUB_PAGES = ROOT / "handdrawn" / "editor_pages"
FONT = ROOT / "handdrawn" / "fonts"
VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".flv", ".wmv", ".mpg", ".mpeg", ".ts"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
SUBS = {".srt", ".vtt"}
IMG_SECONDS = 3.0
SCENE_MIN = 1.5                      # 切出来的片段至少这么长
JSON_PROGRESS = False


def emit(msg: str, pct: float | None = None, progress=None, **extra) -> None:
    if progress:
        progress(pct or 0, msg)
    elif JSON_PROGRESS:
        print("@@" + json.dumps({"stage": extra.pop("stage", "import"), "msg": msg, "pct": pct, **extra}, ensure_ascii=False), flush=True)
    else:
        print(msg, flush=True)


def natural(p: Path | str):
    """自然顺序：「2 秋千」排在「10 卧室」前面（拆开后偶数位是文字、奇数位是数字，比较时不会混）。"""
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", getattr(p, "name", p))]


def probe(p: Path) -> dict:
    """dur = 画面流自己的时长（没有画面时用音频流 / 整个文件的）：片段的 #t 不能超过素材实际长度，不然剪辑器画不出来。"""
    r = subprocess.run([str(FP), "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,duration:format=duration", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})

    def f(x):
        try:
            return float(x or 0)
        except ValueError:
            return 0.0
    dur = f(v.get("duration")) or f(a.get("duration")) or f(d.get("format", {}).get("duration"))
    return {"w": v.get("width"), "h": v.get("height"), "dur": dur, "audio": a.get("codec_name")}


def scene_cuts(p: Path, dur: float) -> list[float]:
    """画面切换点（ffmpeg 场景检测），去掉离得太近的。"""
    if dur < SCENE_MIN * 2:
        return []
    r = subprocess.run([str(FF), "-hide_banner", "-i", str(p), "-vf", "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = []
    for t in sorted(float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)):
        if t - (out[-1] if out else 0) >= SCENE_MIN and dur - t >= SCENE_MIN:
            out.append(round(t, 3))
    return out


def parse_subs(p: Path) -> list[tuple[float, float, str]]:
    text = p.read_text(encoding="utf-8-sig", errors="replace").replace("\r", "")
    ts = lambda s: sum(float(x) * m for x, m in zip(reversed(s.replace(",", ".").split(":")), (1, 60, 3600)))   # noqa: E731
    cues = []
    for block in re.split(r"\n\s*\n", text):
        m = re.search(r"(\d+:\d+(?::\d+)?[.,]\d+)\s*-->\s*(\d+:\d+(?::\d+)?[.,]\d+)", block)
        if not m:
            continue
        body = block[m.end():].strip()
        body = re.sub(r"<[^>]+>", "", body).strip()
        if body:
            cues.append((ts(m.group(1)), ts(m.group(2)), body))
    return cues


def src(rel: str, a: float, b: float) -> str:
    return urllib.parse.quote(rel, safe="/") + f"#t={a:.3f},{b:.3f}"


def target_folder(name: str) -> Path:
    import storage
    slug = re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "导入"
    d = storage.deliver_dir() / f"导入_{slug}"
    k = 2
    while d.exists():
        d = storage.deliver_dir() / f"导入_{slug}_{k}"
        k += 1
    return d


def import_folder(src_dir: Path, progress=None) -> dict:
    src_dir = Path(src_dir).resolve()
    if not src_dir.is_dir():
        raise FileNotFoundError(f"没有这个文件夹：{src_dir}")
    files = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO | IMAGE | AUDIO | SUBS]
    if not files:
        raise ValueError("这个文件夹里没有视频、图片、音频或字幕文件")
    dest = target_folder(src_dir.name)
    assets = dest / "film" / "assets"
    assets.mkdir(parents=True)
    total = sum(p.stat().st_size for p in files) or 1
    done = 0
    for p in files:                                                  # 复制进项目（原文件夹挪走也不影响）
        rel = p.relative_to(src_dir)
        (assets / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, assets / rel)
        done += p.stat().st_size
        emit(f"复制 {rel}", .4 * done / total, progress)
    (dest / "job.json").write_text(json.dumps({"kind": "import", "title": src_dir.name, "source": str(src_dir),
                                               "time": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=1), encoding="utf-8")
    film = build_project(dest, src_dir.name, lambda q, m="": emit(m, .4 + .6 * q, progress))
    return {"folder": str(dest), "project": str(film), "title": src_dir.name}


def build_project(dest: Path, title: str, progress=None) -> Path:
    """按 dest/film/assets 里的文件重写 film/film.html（可以重复运行）。"""
    film = dest / "film"
    assets = film / "assets"
    prog = progress or (lambda *_: None)
    files = sorted((p for p in assets.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO | IMAGE | AUDIO | SUBS
                    and "_audio" not in p.relative_to(assets).parts), key=lambda p: [natural(x) for x in p.relative_to(assets).parts])
    groups: dict[str, list[Path]] = {}
    for p in files:
        g = str(p.relative_to(assets).parent)
        groups.setdefault("" if g == "." else g, []).append(p)
    info = {}
    for i, p in enumerate(f for f in files if f.suffix.lower() in VIDEO | IMAGE | AUDIO):
        info[p] = probe(p)
        prog(.15 * i / max(1, len(files)), f"读取 {p.name}")
    first = next((info[p] for p in files if p.suffix.lower() in VIDEO and info[p]["w"]), None) or \
        next((info[p] for p in files if p.suffix.lower() in IMAGE and info[p]["w"]), None) or {"w": 1920, "h": 1080}
    W, H = int(first["w"]) // 2 * 2, int(first["h"]) // 2 * 2
    sections, cursor, n_clip, sub_k = [], 0.0, 0, 0
    pages = film / "pages"
    pages.mkdir(exist_ok=True)
    for f in ("subtitle.js", "subtitle.css"):
        shutil.copy2(SUB_PAGES / f, pages / f)
    for f in ("ZCOOLKuaiLe-Regular.ttf", "OFL.txt"):
        shutil.copy2(FONT / f, pages / f)
    for old in pages.glob("sub_*.html"):
        old.unlink()
    nvid = sum(1 for p in files if p.suffix.lower() in VIDEO)
    vk = 0
    for g, items in groups.items():
        label = g.replace("\\", " / ") if g else title
        pic, snd, img, aud, sub = [], [], [], [], []
        t = cursor
        starts = {}
        for p in items:                                              # 视频和图片按文件名顺序接在同一条时间线上
            ext = p.suffix.lower()
            rel = p.relative_to(assets).as_posix()
            if ext in VIDEO and info[p]["dur"] > 0:
                d = info[p]["dur"]
                vk += 1
                prog(.15 + .75 * vk / max(1, nvid), f"切镜头 {p.name}")
                cuts = [0.0, *scene_cuts(p, d), d]
                for a, b in zip(cuts, cuts[1:]):
                    n_clip += 1
                    pic.append(f'  <video id="v{n_clip}" src="assets/{src(rel, a, b - .001)}" at="{t + a:.3f}" volume="0" '
                               f'title="{html.escape(p.stem)}{f" · 镜头 {cuts.index(a) + 1}" if len(cuts) > 2 else ""}"></video>')
                if info[p]["audio"]:                                 # 原声单独一轨：抽成 m4a
                    au = assets / "_audio" / (p.relative_to(assets).with_suffix(".m4a"))
                    au.parent.mkdir(parents=True, exist_ok=True)
                    if not au.exists():
                        codec = ["-c:a", "copy"] if info[p]["audio"] == "aac" else ["-c:a", "aac", "-b:a", "192k"]
                        subprocess.run([str(FF), "-y", "-loglevel", "error", "-i", str(p), "-vn", *codec, str(au)], check=False)
                    if au.exists():
                        n_clip += 1
                        ad = min(d, probe(au)["dur"] or d)               # 抽出来的声音可能比画面短一点
                        snd.append(f'  <audio id="a{n_clip}" src="assets/{src(au.relative_to(assets).as_posix(), 0, ad - .001)}" at="{t:.3f}" '
                                   f'title="{html.escape(p.stem)} · 原声"></audio>')
                starts[p.stem] = t
                t += d
            elif ext in IMAGE:
                n_clip += 1
                img.append(f'  <img id="i{n_clip}" src="assets/{src(rel, 0, IMG_SECONDS)}" at="{t:.3f}" title="{html.escape(p.stem)}">')
                starts[p.stem] = t
                t += IMG_SECONDS
        # 音频：从这组开头依次排；最外层文件夹里的音频（通常是整段配乐）从第 0 秒开始
        at = 0.0 if not g and not (pic or img) else cursor
        for p in items:
            if p.suffix.lower() in AUDIO and info[p]["dur"] > 0:
                n_clip += 1
                aud.append(f'  <audio id="m{n_clip}" src="assets/{src(p.relative_to(assets).as_posix(), 0, info[p]["dur"] - .001)}" '
                           f'at="{at:.3f}" title="{html.escape(p.stem)}"></audio>')
                at += info[p]["dur"]
        for p in items:                                              # 字幕：同名视频的字幕跟着那个视频
            if p.suffix.lower() in SUBS:
                base = starts.get(p.stem, cursor)
                last = -1.0
                for a, b, text in parse_subs(p):
                    a, b = base + a, base + b
                    if a < last or b - a < .2:
                        continue
                    last = b
                    sid = f"sub_{sub_k:03d}"
                    sub_k += 1
                    rows = "<br>".join(html.escape(r) for r in text.split("\n"))
                    (pages / f"{sid}.html").write_text("\n".join([
                        '<!doctype html>', '<html lang="zh-CN">', '<head>', '<meta charset="utf-8">', f'<title>{html.escape(text[:40])}</title>',
                        '<link rel="stylesheet" href="subtitle.css">', '</head>', '<body>', '<div id="wrap">',
                        f'<p id="line" data-times="[]" data-dur="9999" data-len="{b - a:.3f}" data-size="{max(28, min(64, H // 18))}">{rows}</p>',
                        '<p id="hi" aria-hidden="true"></p>', '</div>', '<script src="subtitle.js"></script>', '</body>', '</html>', '']), encoding="utf-8")
                    bw, bh = int(W * .84), max(120, int(H * .2))
                    sub.append(f'  <iframe id="{sid}" src="pages/{sid}.html#t=0,{b - a:.3f}" at="{a:.3f}" title="{html.escape(text[:40])}" '
                               f'style="left: {(W - bw) // 2}px; top: {H - bh - int(H * .04)}px; width: {bw}px; height: {bh}px"></iframe>')
        for name, clips in (("字幕", sub), ("图片", img), ("画面", pic), ("原声", snd), ("音频", aud)):
            if clips:
                sections.append((f"{label} · {name}", clips))
        cursor = max(t, at if (pic or img or g) else cursor)
    if not sections:
        raise ValueError("没有能放进时间线的文件（视频 / 图片 / 音频都读不出时长）")
    order = {"字幕": 0, "图片": 1, "画面": 2, "原声": 3, "音频": 4}                # 字幕在最上面，声音在最下面
    sections.sort(key=lambda s: order[s[0].rsplit(" · ", 1)[1]])
    body = "\n".join(f'<section title="{html.escape(t)}">\n' + "\n".join(c) + "\n</section>" for t, c in sections)
    doc = (f'<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width={W}, height={H}">\n'
           f'<title>{html.escape(title)}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n')
    (film / "film.html").write_text(doc, encoding="utf-8")
    cover = dest / "cover.jpg"                                       # 封面：第一个视频的第一帧，或第一张图
    v0 = next((p for p in files if p.suffix.lower() in VIDEO), None)
    i0 = next((p for p in files if p.suffix.lower() in IMAGE), None)
    if v0 or i0:
        subprocess.run([str(FF), "-y", "-loglevel", "error", "-i", str(v0 or i0), "-frames:v", "1", "-vf", "scale=480:-2", str(cover)], check=False)
    prog(1.0, "工程好了")
    return film / "film.html"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="剪辑页导入文件夹")
    ap.add_argument("folder")
    ap.add_argument("--json-progress", action="store_true")
    a = ap.parse_args()
    JSON_PROGRESS = a.json_progress
    r = import_folder(Path(a.folder))
    emit("导入完成", 1.0, stage="done", result=r)
