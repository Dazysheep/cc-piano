"""开头：拨片下滑。

一列圆角、边缘柔化的图片卡片向下快速滑过，减速并带轻微回弹，最终停在最后一张（主图）上。
用法: python tracks/flick_intro.py --final 主图.jpg [--images 其他图片...] --out intro.mp4
      [--title 歌名 --artist 歌手] [--seconds 5] [--size 1920x1080] [--fps 60]
只有主图时，其余卡片用主图的不同取景代替（之后上传别的图片即可替换）。
"""
import argparse
import math
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import sfx

FONT_TITLE = "C:/Windows/Fonts/segoeuil.ttf"   # Segoe UI Light
FONT_SUB = "C:/Windows/Fonts/segoeui.ttf"


def rounded_card(img: Image.Image, size: int, radius: float, feather: float) -> Image.Image:
    """裁成正方形 → 圆角 → 边缘柔化（羽化的 alpha）。"""
    card = ImageOps.fit(img.convert("RGB"), (size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    inset = feather * 1.2
    ImageDraw.Draw(mask).rounded_rectangle([inset, inset, size - 1 - inset, size - 1 - inset],
                                           radius=radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    card.putalpha(mask)
    return card


def variant(img: Image.Image, k: int) -> Image.Image:
    """主图的不同取景（只有一张图时充当其他卡片）。"""
    w, h = img.size
    z = 0.62 + 0.08 * (k % 3)
    cw, ch = int(w * z), int(h * z)
    fx = [0.0, 1.0, 0.5, 0.2, 0.8, 0.35][k % 6]
    fy = [0.3, 0.6, 1.0, 0.0, 0.4, 0.8][k % 6]
    x, y = int((w - cw) * fx), int((h - ch) * fy)
    return img.crop((x, y, x + cw, y + ch))


def _profile(ramp: float = 0.025, power: float = 4.0, n: int = 4001):
    """位置曲线 = 速度曲线的积分：速度在极短时间内升到峰值（快速起步），随后按幂次快速衰减，
    最后很长一段慢慢靠近终点（先快速减速、再慢速），速度全程连续，不会卡顿或回弹。"""
    u = np.linspace(0, 1, n)
    v = np.minimum(1.0, u / ramp) ** 2 * (1 - u) ** power
    p = np.concatenate([[0], np.cumsum((v[1:] + v[:-1]) / 2)])
    return u, p / p[-1]


_U, _P = _profile()


def ease(u: float) -> float:
    return float(np.interp(min(max(u, 0.0), 1.0), _U, _P))


class Flick:
    def __init__(self, cards: list[Image.Image], w: int, h: int, fps: int, seconds: float,
                 title: str, artist: str, fade_in: bool = True):
        self.w, self.h, self.fps, self.seconds = w, h, fps, seconds
        self.fade_in = fade_in
        self.n = len(cards)
        # 卡片越多滑动时间越长（6 张 2.5 秒，16 张约 3.2 秒），避免速度过快看不清
        self.move = min(3.4, max(2.5, 2.5 + 0.07 * (self.n - 6)))
        self.t_done = 0.12 + self.move * 0.72          # 视觉上已经停稳的时刻
        s = int(min(h * 0.6, w * 0.78))          # 竖屏按宽度限制，横屏不变
        self.size, self.spacing = s, s * 1.1
        self.cx, self.cy = w / 2, h * 0.455
        self.cards = [rounded_card(c, s, s * 0.07, max(3, s / 110)) for c in cards]
        # 阴影：卡片 alpha 模糊后的黑色
        sh = Image.new("L", (s + 120, s + 120), 0)
        sh.paste(self.cards[0].getchannel("A"), (60, 60))
        self.shadow = sh.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.65))
        # 背景：每张卡片模糊放大 + 压暗 + 暗角
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        vig = np.clip(1.15 - 0.55 * np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)), 0.35, 1)[..., None]
        self.bgs = []
        for c in cards:
            bg = ImageOps.fit(c.convert("RGB"), (w // 4, h // 4), Image.LANCZOS).filter(ImageFilter.GaussianBlur(14))
            bg = np.asarray(bg.resize((w, h), Image.BICUBIC), dtype=np.float32) * 0.42 * vig
            self.bgs.append(bg)
        self.text = self._text(title, artist)

    def _text(self, title: str, artist: str) -> Image.Image | None:
        if not title:
            return None
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        u = min(self.w, self.h)
        y = self.cy + self.size / 2 + u * 0.07
        d.text((self.w / 2, y), title, font=ImageFont.truetype(FONT_TITLE, int(u * 0.05)),
               fill=(255, 244, 236, 255), anchor="mm")
        if artist:
            d.text((self.w / 2, y + u * 0.055), artist, font=ImageFont.truetype(FONT_SUB, int(u * 0.026)),
                   fill=(236, 200, 186, 220), anchor="mm")
        return layer

    def breathe(self, t: float) -> float:
        """落定后主图缓慢放大一点点。"""
        start = self.t_done + 0.5
        hold = min(1.0, max(0.0, (t - start) / max(self.seconds - start, 0.1)))
        return 1 + 0.035 * (1 - (1 - hold) ** 2)

    def final_card(self):
        """开头最后一帧里主图卡片的 (贴图, 中心 x, 中心 y, 边长)，供正片转场接着飞。"""
        return self.cards[-1], self.cx, self.cy, self.size * self.breathe(self.seconds)

    def pos(self, t: float) -> float:
        """t 秒时滑动到第几张（0 → n-1）。0.12 秒后开始，先快后慢，约 0.12+move 秒完全落定。"""
        return (self.n - 1) * ease((t - 0.12) / self.move)

    def _scene(self, t: float, pos: float, skip: int | None = None) -> np.ndarray:
        i0 = math.floor(pos)
        frac = pos - i0
        bg = self.bgs[min(i0, self.n - 1)] * (1 - frac) + self.bgs[min(i0 + 1, self.n - 1)] * frac
        img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).convert("RGBA")
        breathe = self.breathe(t)
        settle = min(1.0, max(0.0, (t - self.t_done) / 0.6))   # 接近落定时其他卡片淡出，只留主图
        for i in sorted(range(self.n), key=lambda i: -abs(pos - i)):   # 远的先画，近的盖在上面
            dlt = pos - i
            if abs(dlt) > 2.2:
                continue
            d = min(abs(dlt), 1.6)
            scale = (1 - 0.16 * d) * (breathe if abs(dlt) < 0.5 else 1)
            alpha = (1 - 0.55 * d / 1.6) * (1 - settle if i != self.n - 1 else 1)
            if alpha <= 0.01:
                continue
            sz = max(8, int(self.size * scale))
            y = self.cy + dlt * self.spacing
            card = self.cards[i].resize((sz, sz), Image.BILINEAR)
            if alpha < 1:
                card.putalpha(card.getchannel("A").point(lambda v, a=alpha: int(v * a)))
            x0, y0 = int(self.cx - sz / 2), int(y - sz / 2)
            sh = self.shadow.resize((int(self.shadow.width * scale), int(self.shadow.height * scale)), Image.BILINEAR)
            off = int(60 * scale)
            img.paste((0, 0, 0, 255), (x0 - off, y0 - off + int(18 * scale)), sh.point(lambda v, a=alpha: int(v * a)))
            if i != skip:
                img.paste(card, (x0, y0), card)
        if self.text is not None:
            ta = min(1.0, max(0.0, (t - self.t_done - 0.4) / 0.7))
            if ta > 0:
                img.paste(self.text, (0, int((1 - ta) * 12)), self.text.getchannel("A").point(lambda v: int(v * ta)))
        return np.asarray(img.convert("RGB"), dtype=np.float32)

    def sound(self, tail: float = 0.0, whoosh_at: float | None = None) -> np.ndarray:
        """与画面对齐的音效：卡片每滑过中心一次一声拨片，风声跟随速度，主图落定一声闷响。"""
        ts = np.arange(0, self.seconds + 0.5, 1 / 2000)
        ps = np.array([self.pos(t) for t in ts])
        vs = np.gradient(ps, ts)
        vmax = max(vs.max(), 1e-6)
        crossings = []
        for i in range(1, self.n):
            k = int(np.searchsorted(ps, i - 0.5))
            if k < len(ts):
                crossings.append((float(ts[k]), float(vs[k] / vmax)))
        speed_at = lambda t: float(np.interp(t, ts, vs)) / vmax   # noqa: E731
        return sfx.intro_sfx(crossings, speed_at, self.seconds, self.t_done - 0.25, tail, whoosh_at)

    def frame(self, f: int) -> np.ndarray:
        t = f / self.fps
        p0, p1 = self.pos(t), self.pos(t + 1 / self.fps)
        # 运动模糊：按帧间位移每 4 像素采样一次（最多 48 次），快速滑动时是连续拖影而不是一道道残影
        travel = abs(p1 - p0) * self.spacing
        k = int(min(48, max(1, math.ceil(travel / 4))))
        if k == 1:
            out = self._scene(t, p0)
        else:
            out = sum(self._scene(t + j / (k * self.fps), self.pos(t + j / (k * self.fps))) for j in range(k)) / k
        fade = min(1.0, t / 0.35) if self.fade_in else 1.0
        return np.clip(out * fade, 0, 255).astype(np.uint8)


def render(final: Path, images: list[Path], out: Path, w=1920, h=1080, fps=60, seconds=5.0,
           title="", artist="", slots=6, progress=None, sfx_tail=0.0, whoosh_at=None, loop_start=False) -> dict:
    """progress(已完成帧数, 总帧数)：可选的进度回调。
    同时输出 <out>_sfx.wav 音效（时长 seconds + sfx_tail；whoosh_at 给出时在该时刻加转场「呼」声）。
    loop_start：第一张卡片也是主图、不从黑场淡入（成片结尾主图飞回中央，首尾相接可无限循环）；
    返回值里的 first 是第一帧的信息（背景 + 主图卡片位置），给结尾转场用。"""
    main = Image.open(final)
    others = [Image.open(p) for p in images]
    while len(others) < slots - 1:            # 没有上传其他图片时，用主图的不同取景补齐
        others.append(variant(main, len(others)))
    cards = others[: max(slots - 1, len(images))] + [main]
    if loop_start:
        cards = [main] + cards
    fl = Flick(cards, w, h, fps, seconds, title, artist, fade_in=not loop_start)
    writer = imageio_ffmpeg.write_frames(str(out), (w, h), fps=fps, codec="libx264", pix_fmt_out="yuv420p",
                                         quality=None, output_params=["-crf", "15", "-preset", "medium"],
                                         macro_block_size=1, ffmpeg_log_level="error")
    writer.send(None)
    n = round(seconds * fps)
    for f in range(n):
        writer.send(fl.frame(f).tobytes())
        if progress and f % 15 == 0:
            progress(f, n)
    writer.close()
    last = Image.fromarray(fl.frame(n - 1))
    last.save(out.with_suffix(".jpg"), quality=92)
    last.save(out.with_name(out.stem + "_last.png"))      # 无损的最后一帧：正片转场从这里接着演
    card, cx, cy, _ = fl.final_card()
    t_last = (n - 1) / fps
    bg_only = Image.fromarray(np.clip(fl._scene(t_last, fl.pos(t_last), skip=fl.n - 1), 0, 255).astype(np.uint8))
    first_bg = Image.fromarray(np.clip(fl._scene(0.0, fl.pos(0.0), skip=0), 0, 255).astype(np.uint8))
    first = {"last_frame": first_bg, "full": Image.fromarray(fl.frame(0)), "card": fl.cards[0],
             "card_center": (fl.cx, fl.cy), "card_size": fl.size}
    wav = sfx.write_wav(out.with_name(out.stem + "_sfx.wav"), fl.sound(sfx_tail, whoosh_at))
    return {"video": out, "sfx": wav, "last_frame": bg_only, "full_last_frame": last, "card": card,
            "card_center": (cx, cy), "card_size": fl.size * fl.breathe(t_last), "first": first}


def main() -> None:
    ap = argparse.ArgumentParser(description="拨片下滑开头")
    ap.add_argument("--final", type=Path, required=True, help="最后停留的主图")
    ap.add_argument("--images", type=Path, nargs="*", default=[], help="依次滑过的其他图片")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--artist", default="")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--fps", type=int, default=60)
    a = ap.parse_args()
    w, h = map(int, a.size.lower().split("x"))
    render(a.final, a.images, a.out, w, h, a.fps, a.seconds, a.title, a.artist)
    print("done", a.out)


if __name__ == "__main__":
    main()
