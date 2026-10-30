"""拨片开头的分层素材（给剪辑页用，用户 2026-10-30：开头也要细分图层）：
背景一层（模糊背景随卡片切换）、每张专辑卡片一层（透明，带自己的阴影，只在它出现的那段时间里有画面）、
标题 / 歌手做成剪辑器里能改字的网页片段、拨片音效一轨。画法和 flick_intro.Flick 完全一样（同一套位置 / 缩放 / 淡出曲线），
只是把一帧拆开来画；原来的 flick_intro.render 不受影响。
"""
import html
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

import flick_intro

ROOT = Path(__file__).resolve().parents[2]
FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
PAGES = Path(__file__).resolve().parent / "pages"


class FlickLayers(flick_intro.Flick):
    def bg(self, t: float, pos: float) -> np.ndarray:
        i0 = math.floor(pos)
        frac = pos - i0
        return self.bgs[min(i0, self.n - 1)] * (1 - frac) + self.bgs[min(i0 + 1, self.n - 1)] * frac

    def card_alpha(self, t: float, pos: float, i: int) -> float:
        dlt = pos - i
        if abs(dlt) > 2.2:
            return 0.0
        d = min(abs(dlt), 1.6)
        settle = min(1.0, max(0.0, (t - self.t_done) / 0.6))
        return (1 - 0.55 * d / 1.6) * (1 - settle if i != self.n - 1 else 1)

    def card(self, t: float, pos: float, i: int):
        """第 i 张卡片（连阴影）单独画在透明底上：(x0, y0, RGBA float 小图)，没出现时 None。
        只画卡片和阴影占的那一块（整帧合成太慢），由调用方贴回整帧。"""
        alpha = self.card_alpha(t, pos, i)
        if alpha <= 0.01:
            return None
        dlt = pos - i
        d = min(abs(dlt), 1.6)
        scale = (1 - 0.16 * d) * (self.breathe(t) if abs(dlt) < 0.5 else 1)
        sz = max(8, int(self.size * scale))
        y = self.cy + dlt * self.spacing
        card = self.cards[i].resize((sz, sz), Image.BILINEAR)
        if alpha < 1:
            card.putalpha(card.getchannel("A").point(lambda v, a=alpha: int(v * a)))
        x0, y0 = int(self.cx - sz / 2), int(y - sz / 2)
        sh = self.shadow.resize((int(self.shadow.width * scale), int(self.shadow.height * scale)), Image.BILINEAR)
        off, dy = int(60 * scale), int(18 * scale)
        bx, by = x0 - off, y0 - off + dy                               # 小图左上角 = 阴影左上角（阴影比卡片大一圈）
        bw, bh = max(sh.width, off + sz), max(sh.height, off - dy + sz)
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        img.paste((0, 0, 0, 255), (0, 0), sh.point(lambda v, a=alpha: int(v * a)))
        top = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        top.paste(card, (x0 - bx, y0 - by))
        return bx, by, np.asarray(Image.alpha_composite(img, top), dtype=np.float32)

    def samples(self, f: int, cap: int = 48) -> list[tuple[float, float]]:
        """和 Flick.frame 一样的运动模糊采样点 [(t, pos)]（分层渲染时 cap 调小，拖影几乎看不出差别）。"""
        t = f / self.fps
        p0, p1 = self.pos(t), self.pos(t + 1 / self.fps)
        k = int(min(cap, max(1, math.ceil(abs(p1 - p0) * self.spacing / 4))))
        return [(t + j / (k * self.fps), self.pos(t + j / (k * self.fps))) for j in range(k)]

    def fade(self, f: int) -> float:
        return min(1.0, (f / self.fps) / 0.35) if self.fade_in else 1.0


def _pipe(out: Path, w: int, h: int, fps: int, alpha: bool):
    args = [str(FF), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba" if alpha else "rgb24", "-s", f"{w}x{h}",
            "-r", str(fps), "-i", "-"]
    args += (["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30", "-row-mt", "1", "-deadline", "good",
              "-cpu-used", "4", "-auto-alt-ref", "0"] if alpha else ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"])
    return subprocess.Popen(args + [str(out)], stdin=subprocess.PIPE)


def render_layers(final: Path, images: list[Path], dest: Path, w: int, h: int, fps: int, seconds: float, title: str, artist: str,
                  names: list[str], sfx_wav: Path, progress=None, slots: int = 6) -> Path:
    """dest/film/assets：bg.mp4、card_NN.webm；dest/film/pages：标题页；dest/film/film.html。返回 film.html。"""
    main = Image.open(final)
    others = [Image.open(p) for p in images]
    names = list(names)
    while len(others) < slots - 1:                                 # 和 flick_intro.render 一样：图不够时用主图的不同取景补
        others.append(flick_intro.variant(main, len(others)))
        names.insert(len(others) - 1, names[-1] if names else "")
    cards = others[: max(slots - 1, len(images))] + [main]
    names = (names[: len(cards) - 1] + [names[-1] if names else ""])[: len(cards)]
    fl = FlickLayers(cards, w, h, fps, seconds, "", "")
    film = dest / "film"
    assets = film / "assets"
    if film.exists():
        shutil.rmtree(film)
    assets.mkdir(parents=True)
    n = round(seconds * fps)
    # 背景
    p = _pipe(assets / "bg.mp4", w, h, fps, False)
    for f in range(n):
        ss = fl.samples(f)
        bg = sum(fl.bg(t, pos) for t, pos in ss) / len(ss) * fl.fade(f)
        p.stdin.write(np.clip(bg, 0, 255).astype(np.uint8).tobytes())
        if progress and f % 30 == 0:
            progress(.3 * f / n, "背景层")
    p.stdin.close()
    p.wait()
    # 每张卡片：只编码它出现的那段
    spans = []
    for i in range(fl.n):
        frames = [f for f in range(n) if any(fl.card_alpha(t, pos, i) > .01 for t, pos in fl.samples(f, 16))]
        if not frames:
            continue
        a, b = frames[0], frames[-1] + 1
        out = assets / f"card_{i:02d}.webm"
        p = _pipe(out, w, h, fps, True)
        for f in range(a, b):
            acc_rgb, acc_a = np.zeros((h, w, 3), np.float32), np.zeros((h, w), np.float32)
            ss = fl.samples(f, 16)
            for t, pos in ss:
                c = fl.card(t, pos, i)
                if c is None:
                    continue
                bx, by, sm = c                                         # 小图贴回整帧（裁掉画面外的部分）
                x1, y1 = max(0, bx), max(0, by)
                x2, y2 = min(w, bx + sm.shape[1]), min(h, by + sm.shape[0])
                if x2 <= x1 or y2 <= y1:
                    continue
                part = sm[y1 - by: y2 - by, x1 - bx: x2 - bx]
                acc_rgb[y1:y2, x1:x2] += part[..., :3] * (part[..., 3:] / 255)
                acc_a[y1:y2, x1:x2] += part[..., 3]
            al = acc_a / len(ss)
            rgb = np.where(acc_a[..., None] > 0, acc_rgb / np.maximum(acc_a[..., None] / 255, 1e-3), 0) * fl.fade(f)
            p.stdin.write(np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8).tobytes())
        p.stdin.close()
        p.wait()
        spans.append((i, a / fps, b / fps, out.name))
        if progress:
            progress(.3 + .65 * (i + 1) / fl.n, f"卡片 {i + 1}/{fl.n}")
    shutil.copy2(sfx_wav, assets / "sfx.wav")
    # 标题页（剪辑器里能改字）
    pages = film / "pages"
    pages.mkdir()
    for f in ("opener_title.js", "opener_title.css"):
        shutil.copy2(PAGES / f, pages / f)
    u = min(w, h)
    ty = fl.cy + fl.size / 2 + u * .07
    t_in = fl.t_done + .4
    has_title = bool(title)
    if has_title:
        (pages / "title.html").write_text("\n".join([
            '<!doctype html>', '<html lang="zh-CN">', '<head>', '<meta charset="utf-8">', f'<title>{html.escape(title)}</title>',
            '<link rel="stylesheet" href="opener_title.css">', '</head>',
            f'<body style="--u: {u}px; --y: {ty:.0f}px">', '<div id="wrap">', f'<p id="title">{html.escape(title)}</p>',
            f'<p id="artist">{html.escape(artist)}</p>', '</div>', '<script src="opener_title.js"></script>', '</body>', '</html>', '']),
            encoding="utf-8")
    # 工程
    clip = lambda tag, cid, src, a, b, at, title="": (f'  <{tag} id="{cid}" src="{src}#t={a:.3f},{b:.3f}" at="{at:.3f}"'   # noqa: E731
                                                     + (f' title="{html.escape(title)}"' if title else "") + f'></{tag}>')
    dur = n / fps
    sections = []
    if has_title:
        sections.append(("文字 · 歌名 / 歌手（点字可改）", [f'  <iframe id="title" src="pages/title.html#t=0,{dur - t_in:.3f}" at="{t_in:.3f}" '
                                                      f'title="{html.escape(title)}" style="left: 0px; top: 0px; width: {w}px; height: {h}px"></iframe>']))
    for i, a, b, name in sorted(spans, key=lambda s: -s[0]):          # 主图（最后一张）在最上面
        label = names[i] if i < len(names) else ""
        sections.append((f"卡片 {i + 1}{' · 主图' if i == fl.n - 1 else ''}{' · ' + label if label else ''}",
                         [clip("video", f"card_{i:02d}", f"assets/{name}", 0, b - a - .001, a, label)]))
    sections.append(("背景", [clip("video", "bg", "assets/bg.mp4", 0, dur - .001, 0)]))
    sections.append(("拨片音效", [clip("audio", "sfx", "assets/sfx.wav", 0, dur - .001, 0)]))
    body = "\n".join(f'<section title="{html.escape(t)}">\n' + "\n".join(c) + "\n</section>" for t, c in sections)
    doc = (f'<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width={w}, height={h}">\n'
           f'<title>{html.escape(title or "开头")}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n')
    (film / "film.html").write_text(doc, encoding="utf-8")
    (film / "layers.json").write_text(json.dumps({"cards": [{"i": i, "from": a, "to": b, "name": names[i] if i < len(names) else ""}
                                                            for i, a, b, _ in spans], "title_at": t_in}, ensure_ascii=False), encoding="utf-8")
    if progress:
        progress(1.0, "分层完成")
    return film / "film.html"
