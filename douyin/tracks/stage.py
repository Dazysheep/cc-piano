"""音轨画面上的叠加特效：副歌烟花、左下角唱歌的像素 Claude 小人 + 歌词、胶片颗粒。

都是 DawView 的 overlays（每帧 ov(im, t) 直接画在 PIL 图上），颗粒在整帧最后加。
时间 t 是视频时间（= 歌曲时间 - song_start）。
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

import daw

W, H = daw.W, daw.H


def _hash(*xs) -> float:
    """确定性的伪随机 0~1（同一帧重渲结果一致）。"""
    v = math.sin(sum(x * k for x, k in zip(xs, (12.9898, 78.233, 37.719, 93.989)))) * 43758.5453
    return v - math.floor(v)


# ====================================================================== 烟花
class Fireworks:
    """副歌里每小节一束烟花（重拍落点炸开），每束换一个色系；半分辨率累加 → 高斯光晕 → 叠加（加色混合）。"""
    SCALE = 2

    def __init__(self, spans: list[list[float]], beats: list[float], palettes: list, area: tuple, seed: int = 5):
        self.palettes = palettes
        rng = np.random.default_rng(seed)
        x0, y0, x1, y1 = area
        self.bursts = []
        k = 0
        for ci, (a, b) in enumerate(spans):
            downs = [bt for i, bt in enumerate(beats) if i % 4 == 0 and a <= bt <= b - 0.8]
            if not downs:
                downs = list(np.arange(a + 0.5, b - 0.8, 2.2))
            for j, bt in enumerate(downs):
                for extra in ((0,) if j % 3 else (0, 1)):          # 每三小节来一次双响
                    kind = ("peony", "ring", "willow", "peony", "crossette")[k % 5]
                    n = {"peony": 120, "ring": 70, "willow": 90, "crossette": 60}[kind]
                    ang = rng.uniform(0, 2 * np.pi, n)
                    if kind == "ring":
                        spd = np.full(n, 1.0) + rng.normal(0, 0.03, n)
                        ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
                    else:
                        spd = np.sqrt(rng.uniform(0.15, 1.0, n))
                    pal = palettes[(k + ci * 2) % len(palettes)]
                    mix = rng.uniform(0, 1, n)
                    c0, c1 = np.array(pal[0], np.float32), np.array(pal[1], np.float32)
                    cols = c0[None] * (1 - mix[:, None]) + c1[None] * mix[:, None]
                    t_b = bt + extra * 0.42
                    self.bursts.append({
                        "t": t_b, "kind": kind,
                        "x": rng.uniform(x0 + 120, x1 - 120), "y": rng.uniform(y0 + 80, y0 + (y1 - y0) * 0.55),
                        "x_launch": rng.uniform(x0 + 200, x1 - 200),
                        "r": rng.uniform(170, 260) * (0.8 if extra else 1.0),
                        "vx": np.cos(ang) * spd, "vy": np.sin(ang) * spd, "col": cols,
                        "twinkle": rng.uniform(0, 1, n) < (0.5 if kind == "willow" else 0.25),
                        "life": 2.4 if kind == "willow" else 1.6, "seed": k,
                    })
                    k += 1
        g = np.exp(-(np.mgrid[-24:25, -24:25] ** 2).sum(0) / (2 * 9.0 ** 2)).astype(np.float32)
        self.flash = g

    def active(self, t: float) -> list:
        return [b for b in self.bursts if b["t"] - 0.6 <= t <= b["t"] + b["life"]]

    def __call__(self, im: Image.Image, t: float) -> None:
        act = self.active(t)
        if not act:
            return
        s = self.SCALE
        buf = np.zeros((H // s, W // s, 3), np.float32)
        hw, hh = W // s, H // s

        def splat(xs, ys, cols, amp):
            xi, yi = (np.asarray(xs) / s).astype(int), (np.asarray(ys) / s).astype(int)
            ok = (xi >= 0) & (xi < hw) & (yi >= 0) & (yi < hh)
            np.add.at(buf, (yi[ok], xi[ok]), (np.asarray(cols)[ok] * np.asarray(amp)[ok, None]))

        for b in act:
            tau = t - b["t"]
            if tau < 0:                                  # 升空：一点亮光拖着火星
                p = 1 + tau / 0.6
                ease = 1 - (1 - p) ** 2
                lx = b["x_launch"] + (b["x"] - b["x_launch"]) * ease
                ly = H + 20 + (b["y"] - H - 20) * ease
                trail = np.linspace(0, 0.12, 8)
                xs = lx - (b["x"] - b["x_launch"]) * trail * 0.6
                ys = ly + np.linspace(0, 70, 8)
                col = np.array(b["col"][0]) * 0.5 + 128
                splat(xs, ys, np.tile(col, (8, 1)), np.linspace(2.2, 0.2, 8))
                continue
            k, g, r, life = 2.6, 170.0, b["r"], b["life"]
            if b["kind"] == "willow":
                k, g = 1.9, 120.0
            fade = max(0.0, 1 - tau / life) ** 1.4
            for j in range(6):                          # 拖尾：沿时间往回取几个位置
                tt = max(0.0, tau - j * 0.03)
                e = (1 - math.exp(-k * tt)) / k
                xs = b["x"] + b["vx"] * r * k * e
                ys = b["y"] + b["vy"] * r * k * e + g * (tt - e) / k * 1.6
                amp = fade * (1.0 - j / 6) ** 1.5 * 1.6
                tw = np.where(b["twinkle"] & (tau > life * 0.45),
                              (np.sin(tau * 40 + np.arange(len(xs)) * 1.7) > 0.2).astype(np.float32), 1.0)
                hot = min(1.0, tau / 0.18)               # 刚炸开时偏白
                cols = b["col"] * hot + 255 * (1 - hot)
                splat(xs, ys, cols, np.full(len(xs), amp) * tw)
                if b["kind"] == "crossette" and tau > 0.55 and j == 0:   # 十字分裂
                    for dx, dy in ((14, 0), (-14, 0), (0, 14), (0, -14)):
                        splat(xs + dx * (tau - 0.55) * 6, ys + dy * (tau - 0.55) * 6, cols, np.full(len(xs), amp * 0.6))
            if tau < 0.35:                               # 炸开瞬间的光团
                fa = (1 - tau / 0.35) ** 2 * 0.9
                cx, cy = int(b["x"] / s), int(b["y"] / s)
                fl = self.flash
                y0, x0 = cy - 24, cx - 24
                ys0, xs0 = max(0, -y0), max(0, -x0)
                y1, x1 = min(49, hh - y0), min(49, hw - x0)
                if y1 > ys0 and x1 > xs0:
                    buf[y0 + ys0:y0 + y1, x0 + xs0:x0 + x1] += fl[ys0:y1, xs0:x1, None] * np.array(b["col"][0]) * fa
        glow = gaussian_filter(buf, sigma=(2.2, 2.2, 0)) * 3.0 + gaussian_filter(buf, sigma=(0.6, 0.6, 0))
        up = np.asarray(Image.fromarray(np.clip(glow, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR),
                        dtype=np.int16)
        base = np.asarray(im, dtype=np.int16)
        im.paste(Image.fromarray(np.clip(base + up, 0, 255).astype(np.uint8)))


# ====================================================================== 像素 Claude 小人
BODY, HI, SHADE = (217, 119, 87), (236, 152, 120), (184, 92, 64)
EYE, MOUTH, TONGUE = (38, 24, 20), (58, 22, 20), (206, 86, 86)
MIC_HEAD, MIC_HI, MIC_GRIP = (66, 66, 76), (196, 196, 208), (128, 128, 140)
GW, GH = 36, 23                     # 精灵网格（格子）


TEAR = (132, 190, 246)


def clawd(mouth: int = 0, eyes: str = "open", step: int = 0, mic: bool = True, arm: str = "down") -> Image.Image:
    """Claude Code 的像素小人（橙色方块身体、两只方眼睛、两侧小手、四条小腿），右手拿麦克风。
    mouth 0~3：张嘴程度；eyes: open / blink / happy / look_l / look_r（眼珠往左右看）/ sad（垂眼 + 一滴泪）；
    step: 0/1 两组腿交替抬起；arm（左手）: down / up（举起）/ wave（挥手的另一帧，和 up 交替就是挥手）。"""
    g = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    p = g.load()

    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if 0 <= x < GW and 0 <= y < GH:
                    p[x, y] = (*c, 255)

    ox, oy = 5, 4                     # 身体左上角
    rect(ox, oy, ox + 23, oy + 13, BODY)
    rect(ox, oy, ox + 23, oy, HI)                       # 顶部高光
    rect(ox, oy + 13, ox + 23, oy + 13, SHADE)          # 底部阴影
    rect(ox + 23, oy + 1, ox + 23, oy + 13, SHADE)
    if arm == "up":                                      # 左手举过头顶（和身体隔一格，肩膀处连上）
        rect(ox - 2, oy + 4, ox - 1, oy + 6, BODY)
        rect(ox - 4, oy - 3, ox - 2, oy + 5, BODY)
        rect(ox - 4, oy - 3, ox - 2, oy - 3, HI)
        rect(ox - 2, oy - 2, ox - 2, oy + 5, SHADE)
    elif arm == "wave":                                  # 挥手：手往外摆
        rect(ox - 2, oy + 4, ox - 1, oy + 6, BODY)
        rect(ox - 4, oy + 1, ox - 3, oy + 5, BODY)
        rect(ox - 5, oy - 3, ox - 4, oy + 1, BODY)
        rect(ox - 5, oy - 3, ox - 4, oy - 3, HI)
    else:
        rect(ox - 4, oy + 6, ox - 1, oy + 9, BODY)      # 左手
        rect(ox - 4, oy + 9, ox - 1, oy + 9, SHADE)
    # 眼睛
    for i, ex in enumerate((ox + 5, ox + 17)):
        if eyes == "blink":
            rect(ex, oy + 6, ex + 1, oy + 6, EYE)
        elif eyes == "happy":                            # ^ ^
            rect(ex, oy + 4, ex + 1, oy + 4, EYE)
            rect(ex - 1, oy + 5, ex - 1, oy + 6, EYE)
            rect(ex + 2, oy + 5, ex + 2, oy + 6, EYE)
        elif eyes == "sad":                              # 垂下来的眼睛，右眼挂一滴泪
            rect(ex, oy + 5, ex + 1, oy + 6, EYE)
            bx = ex + 2 if i == 0 else ex - 1               # 眉毛内侧上扬
            rect(bx, oy + 3, bx, oy + 3, EYE)
            if i == 1:
                rect(ex + 1, oy + 8, ex + 1, oy + 9, TEAR)
        elif eyes in ("look_l", "look_r"):
            dx = -2 if eyes == "look_l" else 2
            rect(ex + dx, oy + 3, ex + 1 + dx, oy + 6, EYE)
        else:
            rect(ex, oy + 3, ex + 1, oy + 6, EYE)
    # 嘴
    if mouth > 0:
        mx = ox + 10
        rect(mx, oy + 9, mx + 3, oy + 8 + mouth, MOUTH)
        if mouth >= 3:
            rect(mx + 1, oy + 8 + mouth, mx + 2, oy + 8 + mouth, TONGUE)
    # 腿
    for i, lx in enumerate((ox + 2, ox + 6, ox + 16, ox + 20)):
        up = 1 if (i % 2 == step % 2) and step >= 0 else 0
        rect(lx, oy + 14, lx + 1, oy + 16 - up, SHADE if i in (1, 3) else BODY)
    if mic:                                              # 右手举着麦克风，麦头在嘴边
        hx = ox + 24
        rect(hx, oy + 6, hx + 3, oy + 9, BODY)           # 右手
        rect(hx, oy + 9, hx + 3, oy + 9, SHADE)
        rect(hx + 2, oy + 1, hx + 3, oy + 6, MIC_GRIP)   # 麦杆
        rect(hx + 1, oy - 4, hx + 4, oy, MIC_HEAD)       # 麦头
        rect(hx + 1, oy - 4, hx + 2, oy - 3, MIC_HI)
    else:
        rect(ox + 24, oy + 6, ox + 27, oy + 9, BODY)
    return g


NOTE = ["..XX", "..X.X", "..X..X", "..X", ".XX", "XXX", "XX."]


def note_sprite(col) -> Image.Image:
    g = Image.new("RGBA", (6, len(NOTE)), (0, 0, 0, 0))
    for y, row in enumerate(NOTE):
        for x, ch in enumerate(row):
            if ch == "X":
                g.putpixel((x, y), (*col, 255))
    return g


class Singer:
    """左下角唱歌的小人 + 歌词。

    歌词以画面中线偏左为中心，小人站在歌词左边：歌词越长，小人越靠左。
    换句时小人不直接跳过去，而是跳一段舞步过去：跳起转一圈 / 滑步 / 原地转两圈 / 三连小跳 / 太空步（背对着滑）/
    空翻，轮流使用。
    唱歌时嘴巴跟着人声音量开合，每拍踏脚、身体左右摇摆；副歌里眯眼开心、重拍蹦一下，唱得响时举起左手；
    唱到难过的词（unhappy、cry…）垂眼掉一滴泪；人声强时麦克风上飘出音符。
    不唱的时候：开头先挥手打招呼，间奏里左右张望、偶尔挥手、每两小节原地转个身。"""
    P = 5                       # 每格像素（原来是 7，小人缩小一些）
    MOVE = 0.95                 # 转场舞步时长（秒）
    SAD = ("unhappy", "sad", "cry", "tear", "ugly", "misery", "alone", "lonely", "hurt", "broken", "goodbye")

    def __init__(self, lines: list[dict], theme: dict, vocal_env: np.ndarray, env_rate: int, beats: list[float],
                 chorus: list[list[float]], band_top: int):
        self.th = theme
        self.lines = lines
        self.env, self.rate = vocal_env, env_rate
        self.beats = np.array(beats or [0.0])
        self.chorus = chorus
        self.band_top = band_top
        self.floor = H - 26
        self.f_en = ImageFont.truetype(theme["lyric_en"], 46)
        self.f_zh = ImageFont.truetype(theme["lyric_zh"], 28)
        self.sprites = {}
        self.note = note_sprite(theme["ivory"])
        # 每句的文字位置和小人站位
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        sw = GW * self.P
        if W < H:   # 竖屏：歌词放在小人右边的剩余宽度里居中，最长的一句放不下时整体缩小字号
            room = W - 36 - sw - 18 - 36
            longest = max((d.textlength(ln["text"], font=self.f_en) for ln in lines), default=0)
            if longest > room:
                self.f_en = ImageFont.truetype(theme["lyric_en"], max(26, int(46 * room / longest)))
            self.cx = 36 + sw + 18 + room / 2
        else:
            self.cx = W * 0.47
        for ln in lines:
            ln["w"] = d.textlength(ln["text"], font=self.f_en)
            ln["left"] = self.cx - ln["w"] / 2
            ln["x"] = float(np.clip(ln["left"] - sw - 18, 36, 780 if W > H else 36))
            ln["word_x"] = []
            x = 0.0
            for w, s, e in ln["words"]:
                ww = d.textlength(w, font=self.f_en)
                ln["word_x"].append((x, x + ww, s, e))
                x += ww + d.textlength(" ", font=self.f_en)

    def _sprite(self, mouth, eyes, step, flip=False, arm="down"):
        key = (mouth, eyes, step, flip, arm)
        if key not in self.sprites:
            g = clawd(mouth, eyes, step, arm=arm)
            if flip:
                g = g.transpose(Image.FLIP_LEFT_RIGHT)
            self.sprites[key] = g.resize((GW * self.P, GH * self.P), Image.NEAREST)
        return self.sprites[key]

    def _line_at(self, t):
        cur = None
        for i, ln in enumerate(self.lines):
            if ln["start"] - 0.35 <= t:
                cur = i
        return cur

    def _pos(self, t):
        """小人的位置、跳起高度、水平缩放（转身，负数 = 面朝左）、倾斜（弧度）、是否正在走舞步。"""
        if not self.lines:
            return W * 0.18, 0.0, 1.0, 0.0, False
        idx = None
        for i, ln in enumerate(self.lines):
            if t >= ln["start"] - self.MOVE * 0.6:
                idx = i
        if idx is None:
            return self.lines[0]["x"], 0.0, 1.0, 0.0, False
        x1 = self.lines[idx]["x"]
        x0 = self.lines[idx - 1]["x"] if idx > 0 else x1
        u = (t - (self.lines[idx]["start"] - self.MOVE * 0.6)) / self.MOVE
        if u >= 1 or idx == 0 and u < 0:
            return x1, 0.0, 1.0, 0.0, False
        u = max(u, 0.0)
        k = self.P / 7                  # 跳的高度跟着个子缩放
        style = idx % 6
        e = u * u * (3 - 2 * u)
        x = x0 + (x1 - x0) * e
        if style == 0:      # 跳起来转一圈
            return x, math.sin(math.pi * u) * 70 * k, math.cos(2 * math.pi * e), 0.0, True
        if style == 1:      # 滑步（身体后仰，脚下碎步）
            return x, abs(math.sin(u * math.pi * 4)) * 8 * k, 1.0, -math.sin(math.pi * u) * 0.18, True
        if style == 2:      # 原地转两圈再滑过去
            x = x0 + (x1 - x0) * _ease(u * 1.6 - 0.6)
            return x, math.sin(math.pi * u) * 26 * k, math.cos(4 * math.pi * e), 0.0, True
        if style == 3:      # 三连小跳
            return x, abs(math.sin(u * math.pi * 3)) * 34 * k, math.cos(math.pi * 2 * e), 0.0, True
        if style == 4:      # 太空步：背对着前进方向滑过去，身体前倾，最后转回来
            back = -1.0 if x1 >= x0 else 1.0
            sx = back if u < 0.82 else back * math.cos(math.pi * (u - 0.82) / 0.18)
            return x, abs(math.sin(u * math.pi * 6)) * 4 * k, sx, 0.12 * math.sin(math.pi * u) * -back, True
        # 空翻：高高跳起，在空中整个翻一圈
        spin = 2 * math.pi * _ease((u - 0.15) / 0.7) * (1 if x1 >= x0 else -1)
        return x, math.sin(math.pi * u) * 90 * k, 1.0, -spin, True

    def _vocal(self, t):
        i = int(t * self.rate)
        if i < 0 or i >= len(self.env):
            return 0.0
        return float(self.env[max(0, i - 2): i + 3].max())

    def __call__(self, im: Image.Image, t: float) -> None:
        th = self.th
        d = ImageDraw.Draw(im)
        in_ch = any(a <= t <= b for a, b in self.chorus)
        # ---- 歌词
        cur = self._line_at(t)
        if cur is not None:
            ln = self.lines[cur]
            end = ln["end"] + 0.6
            nxt = self.lines[cur + 1]["start"] - 0.35 if cur + 1 < len(self.lines) else end + 9
            # 一直显示到下一句出现；后面是长间奏（6 秒以上）时，唱完再停 3 秒
            hold = nxt if nxt - end < 6 else end + 2.4
            fade_out = min(1.0, max(0.0, (hold - t) / 0.3))
            fade_in = min(1.0, max(0.0, (t - ln["start"] + 0.35) / 0.3))
            a = fade_in * fade_out
            if a > 0.01:
                y = self.band_top + 58 + (1 - fade_in) * 14
                self._karaoke(im, ln, t, y, a, in_ch)
                if ln.get("zh"):
                    zc = tuple(int(c * a + 0) for c in th["muted"])
                    d.text((self.cx, y + 62), ln["zh"], font=self.f_zh, fill=zc, anchor="mm")
        # ---- 小人
        x, hop, sx, lean, moving = self._pos(t)
        v = self._vocal(t)
        singing = cur is not None and self.lines[cur]["start"] - 0.1 <= t <= self.lines[cur]["end"] + 0.15
        mouth = 0 if not singing else (3 if v > 0.55 else 2 if v > 0.28 else 1 if v > 0.1 else 0)
        bi = int(np.searchsorted(self.beats, t))
        prev_b = self.beats[bi - 1] if bi > 0 else 0.0
        beat_len = float(np.median(np.diff(self.beats))) if len(self.beats) > 2 else 0.5
        phase = t - prev_b
        sc = self.P / 7
        blink = (t % 3.7) < 0.12
        sad = singing and any(w in self.lines[cur]["text"].lower() for w in self.SAD)
        first = self.lines[0]["start"] if self.lines else 1e9
        arm = "down"
        if blink:
            eyes = "blink"
        elif sad:
            eyes = "sad"
        elif in_ch and v > 0.35:
            eyes = "happy"
        elif not singing and not moving:                          # 没在唱：左右张望
            eyes = ("open", "look_l", "open", "look_r")[int(t / 1.3) % 4]
        else:
            eyes = "open"
        if not moving:
            if singing:
                if in_ch and v > 0.5:                             # 副歌唱得响：举起左手
                    arm = "up"
                lean = 0.07 * math.sin(math.pi * (bi + min(phase / beat_len, 1.0)))   # 跟着拍子左右摇
                if in_ch and bi % 4 == 0:                         # 副歌重拍蹦一下
                    hop = math.sin(math.pi * min(phase / 0.32, 1.0)) * 22 * sc
            else:
                hello = t < first - 1.0                           # 开头：挥手打招呼
                if hello or (t % 6.0) < 1.2:                      # 间奏里隔一会儿挥挥手
                    arm = ("up", "wave")[int(t / 0.2) % 2]
                    eyes = "happy" if not blink else eyes
                elif bi % 8 == 0 and phase < beat_len:            # 每两小节原地转个身
                    sx = math.cos(2 * math.pi * phase / beat_len)
                hop = max(hop, math.sin(math.pi * min(phase / 0.25, 1.0)) * 6 * sc)
        step = bi % 2 if singing or in_ch or moving else -1
        bob = max(0.0, 1 - phase / 0.22) * 6                      # 每拍轻轻一顿
        spr = self._sprite(mouth, eyes, step, flip=sx < 0, arm=arm)
        w = max(2, int(spr.width * abs(sx)))
        hh = spr.height
        squash = 1.0 - (0.06 if bob > 3 else 0.0)
        h2 = int(hh * squash)
        if w != spr.width or h2 != hh:
            spr = spr.resize((w, h2), Image.NEAREST)
        if lean:
            spr = spr.rotate(math.degrees(lean), resample=Image.NEAREST, expand=True)
        px = int(x + (GW * self.P - spr.width) / 2)
        py = int(self.floor - spr.height - hop)
        # 影子
        sw = int(GW * self.P * 0.7 * (1 - hop / 200))
        sh_col = (0, 0, 0)
        shadow = Image.new("L", (sw, 14), 0)
        ImageDraw.Draw(shadow).ellipse([0, 0, sw - 1, 13], fill=int(110 * (1 - hop / 160)))
        im.paste(sh_col, (int(x + GW * self.P / 2 - sw / 2), self.floor - 8), shadow)
        if in_ch:                                                   # 副歌时脚下一圈暖光
            gw = int(300 * sc)
            glow = Image.new("L", (gw, 60), 0)
            ImageDraw.Draw(glow).ellipse([int(gw * 0.1), 14, int(gw * 0.9), 45], fill=34)
            im.paste(th["ph_glow"], (int(x + GW * self.P / 2 - gw / 2), self.floor - 34), glow)
        im.paste(spr, (px, py), spr)
        # 音符：唱得响的时候从麦克风飘出来
        if singing:
            for k in range(3):
                t0 = math.floor(t / 0.7 - k / 3) * 0.7 + k * 0.7 / 3
                age = t - t0
                if age < 0 or age > 1.4 or self._vocal(t0) < 0.25:
                    continue
                n = self.note.resize((6 * 4, len(NOTE) * 4), Image.NEAREST)
                al = int(255 * (1 - age / 1.4))
                mx = px + (spr.width - 10 if sx >= 0 else 10) + math.sin(age * 5 + k) * 12
                my = py - 10 - age * 60
                im.paste(th["ivory"], (int(mx), int(my)), n.getchannel("A").point(lambda q, a=al: q * a // 255))

    def _karaoke(self, im, ln, t, y, a, in_ch):
        """整句先用浅色写出，已经唱过的部分用亮色覆盖（逐词推进）。"""
        th = self.th
        x0 = ln["left"]
        prog = 0.0
        for wx0, wx1, s, e in ln["word_x"]:
            if t >= e:
                prog = wx1
            elif t >= s:
                prog = wx0 + (wx1 - wx0) * (t - s) / max(e - s, 0.05)
                break
            else:
                break
        layer = Image.new("RGBA", (int(ln["w"]) + 20, 70), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        dim = (*th["muted"], int(170 * a))
        dl.text((4, 35), ln["text"], font=self.f_en, fill=dim, anchor="lm")
        if prog > 0:
            lit = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            hl = th["colors"]["vocals"] if in_ch else th["ivory"]
            ImageDraw.Draw(lit).text((4, 35), ln["text"], font=self.f_en, fill=(*hl, int(255 * a)), anchor="lm")
            cut = int(prog + 4)
            layer.paste(lit.crop((0, 0, cut, 70)), (0, 0), lit.crop((0, 0, cut, 70)))
        im.paste(layer, (int(x0 - 4), int(y - 35)), layer)


def _ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ====================================================================== 胶片颗粒
class Grain:
    """预先生成几帧颗粒（细颗粒 + 粗颗粒），逐帧轮换，加在整帧上。strength 约 0.05~0.1。"""

    def __init__(self, strength: float = 0.07, frames: int = 8, seed: int = 9):
        rng = np.random.default_rng(seed)
        self.frames = []
        for _ in range(frames):
            fine = rng.standard_normal((H, W)).astype(np.float32)
            coarse = rng.standard_normal((H // 3, W // 3)).astype(np.float32)
            coarse = np.asarray(Image.fromarray(coarse).resize((W, H), Image.BILINEAR))
            g = (fine * 0.7 + coarse * 0.6) * strength * 255
            self.frames.append(np.clip(g, -127, 127).astype(np.int8))

    def apply(self, frame: Image.Image, f: int, amount: float = 1.0) -> np.ndarray:
        arr = np.asarray(frame, dtype=np.int16)
        g = self.frames[f % len(self.frames)].astype(np.int16)
        if amount < 0.999:
            g = (g * amount).astype(np.int16)
        return np.clip(arr + g[..., None], 0, 255).astype(np.uint8)


# ====================================================================== 评论故事
def _ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _ease_in_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


class CommentStory:
    """评论像故事一样一幕一幕浮现：每条评论从它对应音轨的播放头处「长」出来，沿弧线飘到空位，
    文字逐行显现，停留后向上淡出；安静的一幕一次只出现一条（画面微微压暗聚焦），高潮的一幕很多碎片一起浮现；
    尾声所有碎片像拼图一样飞进专辑封面，最后一句话淡入。

    cards：[{t0, t1, text, track, solo}]（视频时间，build.py 按幕和节拍排好），finale：{t0, t1, text, sub}。
    view：DawView（取播放头、轨道位置、配色、封面小图位置）。"""
    IN, OUT = 0.75, 0.6           # 浮现 / 淡出时长
    CARD_W = 560
    GATHER = 1.6                  # 尾声前收拢碎片的时长

    def __init__(self, cards: list[dict], finale: dict | None, theme: dict, view, avoid: tuple | None = None):
        """avoid：卡片要让开的区域 (x0, y0, x1, y1)（两人模式里男生头顶的想象云朵）。"""
        self.th, self.view = theme, view
        self.cards, self.finale = cards, finale
        self.dim = True               # 独白时压暗画面；有 CommentScene 时由它来压暗（小人不跟着变暗）
        self.gather_to = None         # 尾声收拢到哪里（默认封面小图；CommentScene 设为文件夹口）
        self.f_card = ImageFont.truetype(theme["lyric_zh"], 30)
        self.f_solo = ImageFont.truetype(theme["font_cjk"], 40)
        self.f_src = ImageFont.truetype(theme["lyric_zh"], 18)
        self.f_quote = ImageFont.truetype(theme["font_cjk"], 54)
        self.f_fin = ImageFont.truetype(theme["font_cjk"], 64)
        self.f_fin_sub = ImageFont.truetype(theme["lyric_en"], 30)
        keys = [t["key"] for t in view.tracks]
        x0 = daw.PLAYHEAD_X + 70
        lane_bottom = H - view.bottom
        shown: list[dict] = []
        for i, c in enumerate(cards):
            accent = view.C.get(c.get("track"), theme["ivory"])
            c["img"], c["lines"] = self._card(c["text"], c.get("solo", False), accent)
            c["lane_y"] = (daw.LANE_TOP + keys.index(c["track"]) * view.lane_h + view.lane_h / 2
                           if c.get("track") in keys else (daw.LANE_TOP + lane_bottom) / 2)
            iw, ih = c["img"].size
            if c.get("solo"):                          # 独白：时间线中间，大字
                c["pos"] = (x0 + (W - x0 - iw) / 2, (daw.LANE_TOP + lane_bottom - ih) / 2)
                if avoid:                              # 让开云朵：放到云朵左边那一块的上部
                    c["pos"] = (max(daw.TL_X + 20, (daw.TL_X + avoid[0] - iw) / 2), daw.LANE_TOP + 30)
                continue
            # 停在自己那条音轨的高度，左右交替；和同时在画面上的卡片重叠时换到另一侧
            y = min(max(c["lane_y"] - ih / 2, daw.LANE_TOP + 6), lane_bottom - ih - 6)
            live = [o for o in shown if o["t1"] + self.OUT > c["t0"]]
            xs = [min(x0 + 70 + side * 330, W - iw - 24) for side in (i % 2, 1 - i % 2)]
            if avoid:                                  # 两人模式：再加播放头左边一格，挑第一个不碰云朵的位置
                xs = [min(x0 + 70, W - iw - 24), daw.TL_X + 30, min(x0 + 400, W - iw - 24)]
            for x in xs:
                hit_cloud = avoid and x < avoid[2] and avoid[0] < x + iw and y < avoid[3] and avoid[1] < y + ih
                if not hit_cloud and not any(x < o["pos"][0] + o["img"].width and o["pos"][0] < x + iw and
                                             y < o["pos"][1] + o["img"].height and o["pos"][1] < y + ih
                                             for o in live):
                    break
            c["pos"] = (x, y)
            shown.append(c)
        if finale:
            finale["img"] = self._final_card(finale["text"], finale.get("sub", ""))

    # ---------------------------------------------------------------- 卡片素材（预先画好，每帧只缩放和改透明度）
    @staticmethod
    def _wrap(text: str, font, max_w: float) -> list[str]:
        d = ImageDraw.Draw(Image.new("L", (8, 8)))
        lines, cur = [], ""
        for ch in text:
            # 标点不放在行首：放不下时也跟在上一行末尾
            if d.textlength(cur + ch, font=font) > max_w and cur and ch not in "，。！？、；：,.!?)）」”":
                lines.append(cur)
                cur = ""
            cur += ch
        return lines + [cur]

    def _card(self, text: str, solo: bool, accent) -> tuple[Image.Image, list[tuple[int, int, int]]]:
        """深色半透明圆角卡片 + 左侧音轨色条 + 引号 + 正文 + 「网易云评论」小字。返回 (RGBA 图, 每行 (x, y, 宽))。"""
        font = self.f_solo if solo else self.f_card
        pad, gap = 28, int(font.size * 0.5)
        lines = self._wrap(text, font, self.CARD_W + (220 if solo else 0) - pad * 2 - 20)
        d = ImageDraw.Draw(Image.new("L", (8, 8)))
        tw = max(d.textlength(ln, font=font) for ln in lines)
        w = int(max(tw, 200) + pad * 2 + 20)
        lh = font.size + gap
        h = int(pad * 2 + lh * len(lines) + 26)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle([0, 0, w - 1, h - 1], radius=18, fill=(*self.th["panel"], 215),
                             outline=(*accent, 120), width=2)
        dr.rounded_rectangle([0, 14, 6, h - 14], radius=3, fill=(*accent, 255))
        dr.text((16, 2), "“", font=self.f_quote, fill=(*accent, 150))
        spans = []
        for k, ln in enumerate(lines):
            y = pad + k * lh
            dr.text((pad + 20, y), ln, font=font, fill=(*self.th["ivory"], 255))
            spans.append((pad + 20, y, int(d.textlength(ln, font=font)) + 2))
        dr.text((w - pad, h - pad + 4), "— 网易云评论", font=self.f_src, fill=(*self.th["muted"], 230), anchor="rm")
        return im, spans

    def _final_card(self, text: str, sub: str) -> Image.Image:
        d = ImageDraw.Draw(Image.new("L", (8, 8)))
        f_sub = self.f_fin_sub                       # 小字里有中文（比如评论作者名）：换中文字体，英文的照旧
        if any(0x4E00 <= ord(ch) <= 0x9FFF for ch in sub):
            f_sub = ImageFont.truetype(self.th["lyric_zh"], 30)
        w = int(max(d.textlength(text, font=self.f_fin), d.textlength(sub, font=f_sub)) + 120)
        im = Image.new("RGBA", (w, 190), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((w / 2, 70), text, font=self.f_fin, fill=(*self.th["ivory"], 255), anchor="mm")
        if sub:
            dr.text((w / 2, 140), sub, font=f_sub, fill=(*self.th["muted"], 255), anchor="mm")
        return im

    # ---------------------------------------------------------------- 每帧
    @staticmethod
    def _fade(img: Image.Image, a: float) -> Image.Image:
        if a >= 0.999:
            return img
        out = img.copy()
        out.putalpha(img.getchannel("A").point(lambda v, a=a: int(v * a)))
        return out

    def _reveal(self, c: dict, u: float) -> Image.Image:
        """正文逐行从左到右显现（u: 0~1），用卡片底色把还没显现的部分盖住。"""
        img = c["img"]
        if u >= 1:
            return img
        shown = max(u, 0.0) * sum(s[2] for s in c["lines"])
        out = img.copy()
        dr = ImageDraw.Draw(out)
        size = (self.f_solo if c.get("solo") else self.f_card).size
        for x, y, w in c["lines"]:
            if shown >= w:
                shown -= w
                continue
            dr.rectangle([x + shown, y - 2, x + w + 4, y + size + 10], fill=(*self.th["panel"], 215))
            shown = 0
        return out

    def _focus(self, t: float) -> float:
        """独白卡片出现时画面压暗的程度（0~1，平滑进出）。"""
        k = 0.0
        for c in self.cards:
            if c.get("solo") and c["t0"] - 0.5 <= t <= c["t1"] + self.OUT + 0.5:
                k = max(k, min(_ease_in_out((t - c["t0"] + 0.4) / 0.9),
                               _ease_in_out((c["t1"] + self.OUT - t) / 0.9)))
        return k

    def __call__(self, im: Image.Image, t: float) -> None:
        fz = self._focus(t) if self.dim else 0.0
        if fz > 0.01:
            im.paste(Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.32 * fz))
        fin = self.finale
        g0 = fin["t0"] - self.GATHER if fin else None
        gather = (t - g0) / self.GATHER if fin and t >= g0 else None
        d = ImageDraw.Draw(im, "RGBA")
        tx, ty = self.gather_to or ((daw.THUMB[0] + daw.THUMB[2]) / 2, (daw.THUMB[1] + daw.THUMB[3]) / 2)
        for c in self.cards:
            end = c["t1"] + self.OUT
            collected = fin is not None and c["t0"] < g0 <= end
            if collected:
                end = fin["t0"]                      # 收拢时还在画面上的卡片一起飞进封面
            if not (c["t0"] <= t < end):
                continue
            u_in = _ease_out((t - c["t0"]) / self.IN)
            img = self._reveal(c, (t - c["t0"] - 0.15) / max(0.6, len(c["text"]) * 0.045))
            px, py = c["pos"]
            # 从小人抛起的纸那里飞出来（CommentScene 设置 origin）；没有小人时从播放头所在的音轨长出来
            ox, oy = c.get("origin") or (daw.PLAYHEAD_X, c["lane_y"])
            if u_in < 1:
                s = 0.25 + 0.75 * u_in
                cx = ox + (px + img.width / 2 - ox) * u_in
                cy = oy + (py + img.height / 2 - oy) * u_in - math.sin(math.pi * u_in) * 40
                a = u_in
            else:
                s, cx, cy, a = 1.0, px + img.width / 2, py + img.height / 2, 1.0
            if collected and gather is not None:
                g = _ease_in_out(gather)
                cx, cy = cx + (tx - cx) * g, cy + (ty - cy) * g - math.sin(math.pi * g) * 60
                s *= 1 - 0.9 * g
                a *= 1 - 0.6 * g
            elif t > c["t1"]:                         # 普通淡出：向上飘走
                v = _ease_in_out((t - c["t1"]) / self.OUT)
                cy -= 30 * v
                a *= 1 - v
            if a < 0.02 or s < 0.05:
                continue
            if t - c["t0"] < self.IN + 0.4 and gather is None:   # 连线：音轨 → 卡片，浮现时最亮然后消失
                la = int(160 * (1 - _ease_out((t - c["t0"]) / (self.IN + 0.4))))
                col = self.view.C.get(c.get("track"), self.th["ivory"])
                d.line([(ox, oy), (cx - img.width * s / 2, cy)], fill=(*col, la), width=2)
                d.ellipse([ox - 6, oy - 6, ox + 6, oy + 6], fill=(*col, la))
            if s != 1.0:
                img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
            img = self._fade(img, a)
            im.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)
        if fin and fin["t0"] <= t < fin["t1"]:
            a = min(_ease_out((t - fin["t0"]) / 0.9), _ease_in_out((fin["t1"] - t) / 0.6))
            im.paste(Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.45 * a))
            img = self._fade(fin["img"], a)
            y = (H - img.height) / 2 - 20 * (1 - a)
            im.paste(img, (int((W - img.width) / 2), int(y)), img)
