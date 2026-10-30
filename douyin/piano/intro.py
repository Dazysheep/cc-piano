"""爆款开头：两张黑胶唱片(头像 × 曲子封面)飞入旋转，音符环绕，中间 × 联动，配高潮片段。

特效：节拍脉冲(缩放+闪光+波形环)、星尘粒子+光带、故障风闪烁、胶片漏光+颗粒。
所有动画只由帧号决定，可重复渲染。
"""
import colorsys
import math
import re
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_CJK = "C:/Windows/Fonts/msyhbd.ttc"
FONT_LATIN = "C:/Windows/Fonts/seguibl.ttf"
FONT_THIN = "C:/Windows/Fonts/bahnschrift.ttf"
FONT_SYMBOL = "C:/Windows/Fonts/seguisym.ttf"
CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


# ---------------------------------------------------------------- 工具
def ease_out_back(x: float, k: float = 1.6) -> float:
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def window(t: float, a: float, b: float) -> float:
    """t 在 [a,b] 内从 0 平滑升到 1。"""
    return ease_out((t - a) / max(b - a, 1e-6))


def accent_color(img: Image.Image) -> tuple[int, int, int]:
    """取封面里最鲜艳的颜色做点缀色（光带、波形环、× 的光晕）。"""
    small = np.asarray(img.convert("RGB").resize((64, 64)), dtype=np.float32) / 255
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in small.reshape(-1, 3)])
    score = hsv[:, 1] * hsv[:, 2]
    top = hsv[np.argsort(score)[-200:]]
    h = float(np.median(top[:, 0]))
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def mixed_text(draw, xy, text: str, size: int, fill, anchor_center=True) -> None:
    """中英混排：中文用雅黑粗体，其他用 Segoe UI Black；xy 为整行中心。"""
    runs, cur = [], ""
    for ch in text:
        if cur and bool(CJK.match(ch)) != bool(CJK.match(cur[-1])):
            runs.append(cur)
            cur = ""
        cur += ch
    if cur:
        runs.append(cur)
    fonts = [ImageFont.truetype(FONT_CJK if CJK.match(r[0]) else FONT_LATIN, size) for r in runs]
    widths = [draw.textlength(r, font=f) for r, f in zip(runs, fonts)]
    x = xy[0] - sum(widths) / 2 if anchor_center else xy[0]
    for r, f, w in zip(runs, fonts, widths):
        draw.text((x, xy[1]), r, font=f, fill=fill, anchor="lm")
        x += w


# ---------------------------------------------------------------- 唱片
def make_vinyl(img: Image.Image, r: int) -> Image.Image:
    """黑胶唱片贴图(RGBA)：纹路 + 中心圆形标签(用户图片) + 中心孔。"""
    d = 2 * r
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32)
    dist = np.hypot(xx - r + 0.5, yy - r + 0.5) / r
    groove = 0.075 + 0.035 * (np.sin(dist * 180) > 0.6) + 0.02 * np.sin(dist * 23)
    base = np.clip(groove, 0, 1)
    rgb = np.repeat((base * 255).astype(np.uint8)[:, :, None], 3, axis=2)
    disc = Image.fromarray(rgb)
    alpha = Image.fromarray(((dist <= 1.0) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))

    lr = int(r * 0.62)   # 标签半径
    label = ImageOps.fit(img.convert("RGB"), (2 * lr, 2 * lr), Image.LANCZOS)
    mask = Image.new("L", (2 * lr, 2 * lr), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 2 * lr - 1, 2 * lr - 1], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1))
    disc.paste(label, (r - lr, r - lr), mask)
    dr = ImageDraw.Draw(disc)
    dr.ellipse([r - lr, r - lr, r + lr, r + lr], outline=(20, 20, 20), width=max(2, r // 90))
    hole = max(4, r // 28)
    dr.ellipse([r - hole, r - hole, r + hole, r + hole], fill=(8, 8, 8))
    disc.putalpha(alpha)
    return disc


def make_sheen(r: int) -> Image.Image:
    """唱片表面的固定反光（两道相对的扇形高光，不随唱片转）。"""
    d = 2 * r
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32)
    ang = np.arctan2(yy - r, xx - r)
    dist = np.hypot(xx - r, yy - r) / r
    wedge = np.maximum(np.cos(2 * (ang + 0.8)), 0) ** 6
    a = wedge * 0.22 * (dist <= 1.0) * (dist > 0.62)
    arr = np.zeros((d, d, 4), dtype=np.uint8)
    arr[..., :3] = 255
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr)


def glyph(ch: str, size: int, color) -> Image.Image:
    font = ImageFont.truetype(FONT_SYMBOL, size)
    pad = size // 2
    im = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad + size / 2, pad + size / 2), ch, font=font, fill=(*color, 255), anchor="mm")
    glow = im.filter(ImageFilter.GaussianBlur(size / 6))
    return Image.alpha_composite(glow, im)


# ---------------------------------------------------------------- 音频：高潮片段 + 转场音效
def find_highlight(notes: dict, length: float) -> float:
    """音符最密、力度最大的 length 秒，返回起点（对齐到一个音符的开头）。"""
    start, vel = notes["start"], notes["velocity"].astype(np.float32)
    total = float(notes["end"].max())
    if total <= length + 1:
        return 0.0
    # 只在 12%~80% 之间找：避开前奏和结尾的大和弦，选副歌这类主旋律段落
    cands = start[(start >= total * 0.12) & (start <= min(total * 0.8, total - length - 0.5))]
    if not len(cands):
        cands = start[start <= total - length]
    best, best_t = -1.0, float(cands[0])
    for t in np.unique(np.round(cands, 2)):
        m = (start >= t) & (start < t + length)
        score = float(vel[m].sum())
        if score > best:
            best, best_t = score, float(t)
    return best_t


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    return data.reshape(-1, ch), sr


def write_wav(path: Path, data: np.ndarray, sr: int) -> None:
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def intro_audio(piano_wav: Path, t0: float, dur: float, sfx: bool, out: Path) -> np.ndarray:
    """截取高潮片段，淡入淡出，叠加「嗖 + 咚」转场音效；返回单声道包络用于节拍动画。"""
    data, sr = read_wav(piano_wav)
    a, b = int(t0 * sr), int((t0 + dur) * sr)
    seg = data[a:b].copy()
    if len(seg) < b - a:
        seg = np.vstack([seg, np.zeros((b - a - len(seg), seg.shape[1]), dtype=np.float32)])
    n = len(seg)
    fade_in, fade_out = int(0.06 * sr), int(0.5 * sr)
    env = np.ones(n, dtype=np.float32)
    env[:fade_in] = np.linspace(0, 1, fade_in)
    env[-fade_out:] = np.linspace(1, 0, fade_out)
    seg *= env[:, None]
    if sfx:
        rng = np.random.default_rng(7)
        t = np.arange(n) / sr
        # 嗖：带通噪声，0~0.5 秒渐强
        noise = rng.standard_normal(n).astype(np.float32)
        k = int(sr * 0.004)
        noise = np.convolve(noise, np.ones(k) / k, mode="same") - np.convolve(noise, np.ones(k * 6) / (k * 6), mode="same")
        whoosh = noise * np.clip(t / 0.5, 0, 1) ** 2 * (t < 0.5) * 0.9
        # 咚：0.5 秒处的低频撞击
        tt = np.clip(t - 0.5, 0, None)
        boom = np.sin(2 * np.pi * (55 + 40 * np.exp(-tt * 18)) * tt) * np.exp(-tt * 7) * (t >= 0.5) * 0.55
        seg += (whoosh + boom)[:, None].astype(np.float32)
    peak = np.abs(seg).max()
    if peak > 0.98:
        seg *= 0.98 / peak
    write_wav(out, seg, sr)
    return seg.mean(axis=1), sr


def beat_envelope(mono: np.ndarray, sr: int, fps: int, n_frames: int):
    """每帧的响度、节拍脉冲(响度突增)和 48 段频谱（用于波形环）。"""
    hop = sr / fps
    rms = np.zeros(n_frames, dtype=np.float32)
    spec = np.zeros((n_frames, 48), dtype=np.float32)
    win = int(sr * 0.05)
    edges = np.geomspace(60, 6000, 49)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    for f in range(n_frames):
        c = int(f * hop)
        chunk = mono[max(0, c - win // 2): c + win // 2]
        if len(chunk) < win:
            chunk = np.pad(chunk, (0, win - len(chunk)))
        rms[f] = np.sqrt(np.mean(chunk ** 2))
        mag = np.abs(np.fft.rfft(chunk * np.hanning(win)))
        for i in range(48):
            sel = (freqs >= edges[i]) & (freqs < edges[i + 1])
            spec[f, i] = mag[sel].mean() if sel.any() else 0
    rms /= max(rms.max(), 1e-6)
    smooth = np.convolve(rms, np.ones(9) / 9, mode="same")
    pulse = np.clip((rms - smooth) * 5, 0, 1)
    for f in range(1, n_frames):   # 脉冲快起慢落
        pulse[f] = max(pulse[f], pulse[f - 1] * 0.82)
    spec = np.log1p(spec * 8)
    spec /= max(np.percentile(spec, 98), 1e-6)
    return rms, pulse, np.clip(spec, 0, 1.2)


# ---------------------------------------------------------------- 画面
class Intro:
    def __init__(self, w, h, fps, dur, avatar: Path, cover: Path, left: str, right: str, title: str, fx: dict,
                 env):
        self.w, self.h, self.fps, self.dur = w, h, fps, dur
        self.fx = fx
        self.rms, self.pulse, self.spec = env
        self.vertical = h > w
        cov = Image.open(cover).convert("RGB")
        self.accent = accent_color(cov)
        s = min(w, h)

        # 背景：封面模糊放大 + 压暗 + 偏色
        bg = ImageOps.fit(cov, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(s / 18))
        bg = Image.blend(bg, Image.new("RGB", (w, h), (10, 6, 22)), 0.55)
        self.bg = bg.resize((int(w * 1.1), int(h * 1.1)), Image.LANCZOS)

        if self.vertical:
            self.r = int(w * 0.22)
            self.centers = [(w * 0.5, h * 0.27), (w * 0.5, h * 0.615)]
            self.text_y = (h * 0.80, h * 0.855)
        else:
            self.r = int(h * 0.25)
            self.centers = [(w * 0.30, h * 0.43), (w * 0.70, h * 0.43)]
            self.text_y = (h * 0.79, h * 0.875)
        self.discs = [make_vinyl(Image.open(avatar), self.r), make_vinyl(cov, self.r)]
        self.sheen = make_sheen(self.r)

        # 文字层（静态，入场时做淡入+位移）
        self.names = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.names)
        mixed_text(d, (w / 2, self.text_y[0]), f"{left}  ×  {right}", int(s * 0.07), (255, 255, 255, 255))
        self.title_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if title:
            spaced = " ".join(title.lower()) if len(title) <= 14 else title
            ImageDraw.Draw(self.title_layer).text((w / 2, self.text_y[1]), spaced, font=ImageFont.truetype(
                FONT_THIN, int(s * 0.045)), fill=(*self.accent, 255), anchor="mm")
        glow = self.names.filter(ImageFilter.GaussianBlur(s / 90))
        self.names = Image.alpha_composite(glow, self.names)

        self.glyphs = [glyph(c, int(s * 0.055), (255, 255, 255)) for c in "♪♫♬♩"]
        self.glyphs_c = [glyph(c, int(s * 0.045), self.accent) for c in "♪♫"]
        rng = np.random.default_rng(11)
        self.stars = rng.uniform(0, 1, (110, 5))     # x, y, 速度, 大小, 相位
        self.grain_arr = [rng.normal(0, 5, (h // 2, w // 2)).astype(np.float32) for _ in range(6)]

    @staticmethod
    def _over(img: Image.Image, layer: Image.Image, pos, alpha: float = 1.0) -> None:
        """把 RGBA 图层叠到画面上，位置可以为负（部分在画面外）。"""
        mask = layer.getchannel("A")
        if alpha < 1:
            mask = mask.point(lambda v: int(v * alpha))
        img.paste(layer.convert("RGB"), (int(pos[0]), int(pos[1])), mask)

    # 各元素 -----------------------------------------------------------
    def _disc_pos(self, i: int, t: float):
        cx, cy = self.centers[i]
        k = ease_out_back(t / 0.55)
        if self.vertical:
            sy = -self.r * 1.4 if i == 0 else self.h + self.r * 1.4
            return cx, sy + (cy - sy) * k
        sx = -self.r * 1.4 if i == 0 else self.w + self.r * 1.4
        return sx + (cx - sx) * k, cy

    def _ring(self, layer, cx, cy, r, f, color, alpha):
        """唱片外圈随音乐跳动的波形环。"""
        spec = self.spec[min(f, len(self.spec) - 1)]
        d = ImageDraw.Draw(layer)
        n = 96
        for k in range(n):
            v = spec[k % 48 if k < 48 else 95 - k]
            ang = 2 * math.pi * k / n - math.pi / 2
            r0, r1 = r * 1.06, r * (1.08 + 0.22 * v)
            d.line([cx + r0 * math.cos(ang), cy + r0 * math.sin(ang), cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)],
                   fill=(*color, int(200 * alpha)), width=max(2, int(r / 70)))

    def frame(self, f: int) -> Image.Image:
        t = f / self.fps
        w, h, s = self.w, self.h, min(self.w, self.h)
        pulse = float(self.pulse[min(f, len(self.pulse) - 1)]) if self.fx.get("beat", True) else 0.0

        # 背景缓慢推近 + 节拍提亮
        z = 1.0 + 0.04 * t / self.dur
        bw, bh = self.bg.size
        cw, ch = int(w / z * 1.0), int(h / z * 1.0)
        ox, oy = (bw - cw) // 2, (bh - ch) // 2
        img = self.bg.crop((ox, oy, ox + cw, oy + ch)).resize((w, h), Image.BILINEAR).convert("RGBA")
        if pulse > 0.02:
            img = Image.blend(img, Image.new("RGBA", (w, h), (*self.accent, 255)), 0.12 * pulse)

        fx = Image.new("RGBA", (w, h), (0, 0, 0, 0))   # 发光元素先画在这层，统一做光晕
        fxd = ImageDraw.Draw(fx)

        # 星尘粒子
        if self.fx.get("stardust", True):
            for x, y, sp, sz, ph in self.stars:
                yy = (y - t * (0.03 + 0.05 * sp)) % 1.0
                xx = x + 0.01 * math.sin(t * 1.5 + ph * 6)
                a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 3 + ph * 9))
                rr = (1 + 2.5 * sz) * s / 1080
                fxd.ellipse([xx * w - rr, yy * h - rr, xx * w + rr, yy * h + rr], fill=(255, 245, 255, int(200 * a)))

        # 两张唱片之间的光带（× 出现后从中间向两边展开）
        p0, p1 = self._disc_pos(0, t), self._disc_pos(1, t)
        beam = window(t, 0.6, 1.1)
        if self.fx.get("stardust", True) and beam > 0:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            for k in range(3):
                ax = mx + (p0[0] - mx) * beam * 0.8
                ay = my + (p0[1] - my) * beam * 0.8
                bx = mx + (p1[0] - mx) * beam * 0.8
                by = my + (p1[1] - my) * beam * 0.8
                fxd.line([ax, ay, bx, by], fill=(*self.accent, int(90 - 25 * k)), width=int(s * (0.006 + 0.01 * k)))
            # 光带上流动的亮点
            for k in range(4):
                u = ((t * 0.9 + k / 4) % 1.0)
                px, py = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u
                rr = s * 0.006 * beam
                fxd.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(255, 255, 255, int(230 * beam)))

        # 波形环
        if self.fx.get("beat", True):
            for i, p in enumerate((p0, p1)):
                self._ring(fx, p[0], p[1], self.r * (1 + 0.05 * pulse), f, self.accent, window(t, 0.45, 0.9))

        # 唱片：入场高速旋转逐渐减速到匀速，节拍时轻微放大
        for i, (cx, cy) in enumerate((p0, p1)):
            spin = 140 * t + 260 * (1 - ease_out(t / 0.9)) * (1 if i == 0 else -1)
            ang = -spin if i == 0 else spin
            scale = 1 + 0.05 * pulse
            disc = self.discs[i].rotate(ang, resample=Image.BICUBIC)
            size = int(2 * self.r * scale)
            disc = disc.resize((size, size), Image.BILINEAR)
            sheen = self.sheen.resize((size, size), Image.BILINEAR)
            shadow = Image.new("L", (size, size), 0)
            ImageDraw.Draw(shadow).ellipse([0, 0, size - 1, size - 1], fill=150)
            shadow = shadow.filter(ImageFilter.GaussianBlur(size / 25))
            x0, y0 = int(cx - size / 2), int(cy - size / 2)
            img.paste((0, 0, 0, 255), (x0 + size // 40, y0 + size // 25, x0 + size // 40 + size, y0 + size // 25 + size),
                      shadow)
            self._over(img, disc, (x0, y0))
            self._over(img, sheen, (x0, y0))

        # 环绕音符
        if t > 0.45:
            na = window(t, 0.45, 0.9)
            for i, (cx, cy) in enumerate((p0, p1)):
                for k in range(5):
                    ang = t * (0.9 + 0.15 * k) * (1 if i == 0 else -1) + k * 2 * math.pi / 5 + i
                    rr = self.r * (1.32 + 0.06 * math.sin(t * 2.3 + k))
                    gx, gy = cx + rr * math.cos(ang), cy + rr * math.sin(ang) * 0.92
                    g = self.glyphs[(k + i) % 4] if k % 2 == 0 else self.glyphs_c[(k + i) % 2]
                    a = na * (0.55 + 0.45 * math.sin(t * 3 + k * 1.7) ** 2)
                    self._over(img, g, (gx - g.width / 2, gy - g.height / 2), a)
            # 往上飘散的音符
            for k in range(8):
                ph = (t * 0.45 + k / 8) % 1.0
                i = k % 2
                cx, cy = (p0, p1)[i]
                gx = cx + (k - 3.5) * self.r * 0.22 + math.sin(ph * 6 + k) * self.r * 0.1
                gy = cy - self.r * 0.6 - ph * self.r * 1.6
                if 0 < gy < h:
                    g = self.glyphs_c[k % 2]
                    self._over(img, g, (gx - g.width / 2, gy - g.height / 2), na * math.sin(ph * math.pi))

        # 中间的 ×：弹出 + 光晕
        xk = ease_out_back((t - 0.6) / 0.4, 2.2) if t > 0.6 else 0
        if xk > 0:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            arm = s * 0.045 * xk * (1 + 0.15 * pulse)
            wd = max(3, int(s * 0.012))
            for dx, dy in ((1, 1), (1, -1)):
                fxd.line([mx - arm * dx, my - arm * dy, mx + arm * dx, my + arm * dy], fill=(255, 255, 255, 255), width=wd)

        glow = fx.resize((w // 2, h // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(s / 220))
        img.alpha_composite(glow.resize((w, h), Image.BILINEAR))
        img.alpha_composite(fx)

        # 文字入场：淡入 + 上浮
        ta = window(t, 0.9, 1.5)
        if ta > 0:
            self._over(img, self.names, (0, (1 - ta) * s * 0.03), ta)
        tb = window(t, 1.2, 1.8)
        if tb > 0:
            self._over(img, self.title_layer, (0, (1 - tb) * s * 0.03), tb)

        out = img.convert("RGB")

        # 胶片漏光（暖色光斑扫过）
        if self.fx.get("light_leak", True):
            lt = (t - 1.0) / 2.2
            if 0 < lt < 1:
                leak = Image.new("RGB", (w // 4, h // 4), 0)
                ld = ImageDraw.Draw(leak)
                cx = (-0.2 + 1.4 * lt) * w / 4
                for k in range(6, 0, -1):
                    rr = k * s / 4 * 0.12
                    col = (int(255 * 0.18 * (7 - k) / 6 * math.sin(lt * math.pi)), int(140 * 0.18 * (7 - k) / 6 * math.sin(lt * math.pi)), int(60 * 0.12 * (7 - k) / 6))
                    ld.ellipse([cx - rr * 1.6, h / 8 - rr, cx + rr * 1.6, h / 8 + rr], fill=col)
                leak = leak.filter(ImageFilter.GaussianBlur(s / 40)).resize((w, h), Image.BILINEAR)
                out = ImageChops.add(out, leak)

        arr = np.asarray(out).astype(np.float32)

        # 入场白闪 + 出场推近
        flash = max(0.0, 1 - abs(t - 0.52) / 0.08) * 0.3
        if flash > 0:
            arr = arr + (255 - arr) * flash
        if t > self.dur - 0.45:
            k = (t - (self.dur - 0.45)) / 0.45
            zoom = 1 + 0.12 * ease_out(k)
            im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
            zw, zh = int(w / zoom), int(h / zoom)
            im = im.crop(((w - zw) // 2, (h - zh) // 2, (w - zw) // 2 + zw, (h - zh) // 2 + zh)).resize((w, h))
            arr = np.asarray(im).astype(np.float32) * (1 - 0.65 * ease_out(k))   # 只压暗，不全黑，卡点切正片

        # 故障风：入场与出场各一次
        if self.fx.get("glitch", True):
            g = max(1 - abs(t - 0.55) / 0.15, 1 - abs(t - (self.dur - 0.3)) / 0.12, 0)
            if g > 0:
                rng = np.random.default_rng(f)
                dx = int(s * 0.018 * g)
                arr[..., 0] = np.roll(arr[..., 0], dx, axis=1)
                arr[..., 2] = np.roll(arr[..., 2], -dx, axis=1)
                for _ in range(int(6 * g) + 1):
                    y0 = int(rng.uniform(0, h - 10))
                    hh = int(rng.uniform(4, s * 0.05))
                    arr[y0:y0 + hh] = np.roll(arr[y0:y0 + hh], int(rng.uniform(-1, 1) * s * 0.06 * g), axis=1)

        # 胶片颗粒
        if self.fx.get("light_leak", True):
            gr = self.grain_arr[f % len(self.grain_arr)]
            arr += np.repeat(np.repeat(gr, 2, axis=0), 2, axis=1)[:h, :w, None]

        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- 入口
def render_intro(*, w: int, h: int, fps: int, cfg: dict, notes: dict, piano_wav: Path, avatar: Path, cover: Path,
                 left: str, right: str, title: str, out: Path, crf: int = 14) -> dict:
    ic = cfg["intro"]
    dur = float(ic.get("duration", 4.0))
    t0 = find_highlight(notes, dur)
    wav = out.with_suffix(".wav")
    mono, sr = intro_audio(piano_wav, t0, dur, bool(ic.get("sfx", True)), wav)
    n = int(round(dur * fps))
    env = beat_envelope(mono, sr, fps, n)
    intro = Intro(w, h, fps, dur, avatar, cover, left, right, title, ic.get("effects", {}), env)

    silent = out.with_name(out.stem + "_v.mp4")
    writer = imageio_ffmpeg.write_frames(
        str(silent), (w, h), fps=fps, codec="libx264", pix_fmt_out="yuv420p", quality=None,
        output_params=["-crf", str(crf), "-preset", "fast"], macro_block_size=1, ffmpeg_log_level="error")
    writer.send(None)
    for f in range(n):
        writer.send(intro.frame(f).tobytes())
    writer.close()
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    silent.unlink()
    wav.unlink()
    return {"path": out, "duration": n / fps, "highlight": t0, "cover_frame": intro.frame(int(n * 0.55))}
