"""音轨剪辑画面：编曲软件风格的多轨时间线。

播放头固定在时间线左侧 1/3 处，各轨道（原曲 / 人声 / 钢琴 / 吉他 / 贝斯 / 其他）从右往左平滑滚动。
波形来自分离出的真实音轨；钢琴轨显示转写出来的音符（MIDI 片段样式）；配色和字体来自主题（themes.py）。
为了流畅和速度：整首每条轨道预先画成长条，每帧只做裁切 + 粘贴，再叠加播放头、电平、光斑等动态元素。
可选：backdrop（封面虚化背景，面板变成毛玻璃）、bottom（底部留给歌词的高度）、overlays（每帧叠加的特效）、
outro（结尾倒放开头转场：封面从标题栏飞回画面中央，最后一帧与开头第一帧一致，便于无限循环）。
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import themes

W, H = 1920, 1080
TOP_BAR, RULER_H = 64, 40
HERO = 0                             # 竖屏：标题栏下面的大封面区高度（横屏为 0）
RULER_Y = TOP_BAR + HERO             # 标尺顶边
LANE_TOP = RULER_Y + RULER_H + 8
HEADER_W = 280
TL_X = HEADER_W                      # 时间线区域起点
TL_W = W - TL_X
PLAYHEAD_X = TL_X + int(TL_W * 0.33)
PXPS = 140                           # 每秒多少像素（滚动速度）
PAD = 8.0                            # 长条左右各留的秒数
VERTICAL = False

_fonts = {}


def font(path, size):
    if (path, size) not in _fonts:
        _fonts[path, size] = ImageFont.truetype(path, size)
    return _fonts[path, size]


def face(th: dict, key: str, text: str) -> str:
    """标题栏 / 标签的字体：文字里有中文（歌名、歌手）时换成主题的中文字体，纯英文照旧。"""
    if any(0x4E00 <= ord(ch) <= 0x9FFF for ch in text):
        return th["font_cjk"] if key == "font_semi" else th.get("lyric_zh", th["font_cjk"])
    return th[key]


THUMB = (24, 8, 72, 56)   # 标题栏左边的专辑小图（竖屏时是主视觉区的大封面）
ENTRY = 1.8               # 转场时长：水墨晕开露出编曲界面，同时开头的主图飞进小图位置
OUTRO = 2.2               # 结尾转场时长（倒放：主图从小图位置飞回中央）
HERO_CARD = 400           # 竖屏大封面边长


def set_canvas(vertical: bool) -> None:
    """切换画布：横屏 1920×1080（默认）或竖屏 1080×1920。竖屏在标题栏下留出主视觉区（大封面 + 歌名），
    多轨面板在下半屏。要在创建 DawView、导入 stage 之前调用。"""
    global W, H, HERO, RULER_Y, LANE_TOP, HEADER_W, TL_X, TL_W, PLAYHEAD_X, THUMB, VERTICAL
    VERTICAL = vertical
    W, H = (1080, 1920) if vertical else (1920, 1080)
    HERO = 600 if vertical else 0
    RULER_Y = TOP_BAR + HERO
    LANE_TOP = RULER_Y + RULER_H + 8
    HEADER_W = 240 if vertical else 280
    TL_X = HEADER_W
    TL_W = W - TL_X
    PLAYHEAD_X = TL_X + int(TL_W * 0.33)
    if vertical:
        x0, y0 = (W - HERO_CARD) // 2, TOP_BAR + 40
        THUMB = (x0, y0, x0 + HERO_CARD, y0 + HERO_CARD)
    else:
        THUMB = (24, 8, 72, 56)
    import sys
    st = sys.modules.get("stage")
    if st is not None:                 # stage 在导入时记下了画布尺寸
        st.W, st.H = W, H


def _smooth(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _out_cubic(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _in_out_cubic(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def make_backdrop(cover: Image.Image, dim: float = 0.55, tint=(0, 0, 0)) -> Image.Image:
    """封面 → 铺满、强虚化、压暗的背景（比画面大 6%，每帧缓慢漂移）。"""
    bw, bh = int(W * 1.06), int(H * 1.06)
    small = ImageOps.fit(cover.convert("RGB"), (bw // 6, bh // 6), Image.LANCZOS).filter(ImageFilter.GaussianBlur(9))
    arr = np.asarray(small.resize((bw, bh), Image.BICUBIC), dtype=np.float32)
    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
    vig = np.clip(1.12 - 0.5 * np.hypot((xx - bw / 2) / (bw / 2), (yy - bh / 2) / (bh / 2)), 0.45, 1)[..., None]
    arr = arr * dim * vig + np.array(tint, np.float32) * (1 - dim) * 0.5
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


class DawView:
    def __init__(self, work: Path, title: str, artist: str, song_start: float, intro: dict | None = None,
                 t_entry: float = 0.0, theme: str | None = None, backdrop: Image.Image | None = None,
                 bottom: int = 0, overlays: list | None = None, outro: dict | None = None,
                 t_last: float | None = None, pulse: float = 0.0, keep: list[str] | None = None):
        """intro：开头最后一帧与主图卡片信息（来自 flick_intro.render），t_entry：正片从第几秒开始。
        outro：开头第一帧的信息（flick_intro.render 的 first），t_last：最后一帧的时间。
        pulse：重拍时画面推近的幅度（0.015 = 1.5%，0 关闭），竖屏的大封面同时跟着跳。"""
        self.pulse = pulse
        self.th = themes.get(theme)
        self.C = self.th["colors"]
        self.glass = backdrop is not None
        self.backdrop = backdrop
        self.bottom = bottom
        self.overlays = overlays or []
        self.intro, self.t_entry = intro, t_entry
        self.outro, self.t_last = outro, t_last
        self.thumb = None
        if intro:
            tw = THUMB[2] - THUMB[0]
            self.thumb = intro["card"].resize((tw, tw), Image.LANCZOS)
        self.a = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
        self.rate = self.a["env_rate"]
        self.dur = self.a["song"]["duration"]
        self.song_start = song_start
        self.title, self.artist = title, artist
        tempo = self.a["tempo"]
        beats = self.a["beats"]
        if tempo > 140:                       # 节拍检测常把每拍算成两拍
            tempo, beats = tempo / 2, beats[::2]
        self.tempo, self.beats = tempo, beats
        down = self.a.get("downbeat", 0)          # 第几拍是小节的第一拍（重拍），旧分析结果没有时按 0
        self.downbeats = np.array(beats[down::4] if beats else [], dtype=np.float32)
        self.tracks = self.a["tracks"]
        if keep:                                  # 只显示这几条音轨（给小人和小剧场腾地方）
            self.tracks = [t for t in self.tracks if t["key"] in keep] or self.tracks
        self.n = len(self.tracks)
        self.lane_h = (H - LANE_TOP - 8 - bottom) // self.n
        self.env = {t["key"]: np.load(work / f"env_{t['key']}.npy").astype(np.float32)
                    for t in self.a["tracks"]}           # 隐藏的音轨也读（烟花、唱歌动作要用原曲 / 人声的响度）
        self.level = {k: v.max(axis=1) for k, v in self.env.items()}
        self.meter = {k: 0.0 for k in self.env}
        self._build_static()
        self._build_strips()
        self._build_fx()
        if intro or outro:
            self._build_ink_base()
        self.ink_in = self._build_ink(intro) if intro else None
        self.ink_out = self._build_ink(outro) if outro else None

    def _a(self, col, alpha: float = 1.0):
        """毛玻璃模式下给颜色加透明度；普通模式原样返回。"""
        return (*col, int(alpha * 255)) if self.glass else col

    # ------------------------------------------------------------ 静态底图
    def _build_static(self):
        th, C, g = self.th, self.C, self.th["glass"]
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)) if self.glass else Image.new("RGB", (W, H), th["bg"])
        d = ImageDraw.Draw(im)
        a = self._a
        d.rectangle([0, 0, W, TOP_BAR], fill=a(th["panel"], g + 0.15))
        if HERO:                                     # 竖屏：歌名写在大封面下面，标题栏只放走带控制
            ty = THUMB[3] + 52
            f_t = font(face(th, "font_semi", self.title), 48)
            while d.textlength(self.title, font=f_t) > W - 80 and f_t.size > 28:
                f_t = font(face(th, "font_semi", self.title), f_t.size - 2)
            d.text((W / 2, ty), self.title, font=f_t, fill=a(th["ivory"]), anchor="mm")
            d.text((W / 2, ty + 50), self.artist, font=font(face(th, "font_reg", self.artist), 28), fill=a(th["muted"]),
                   anchor="mm")
        else:
            tx = THUMB[2] + 16 if self.thumb else 28    # 有专辑小图时标题右移
            f_t = font(face(th, "font_semi", self.title), 26)
            d.text((tx, TOP_BAR / 2), self.title, font=f_t, fill=a(th["ivory"]), anchor="lm")
            tw = d.textlength(self.title, font=f_t)
            d.text((tx + tw + 14, TOP_BAR / 2 + 1), self.artist, font=font(face(th, "font_reg", self.artist), 20),
                   fill=a(th["muted"]),
                   anchor="lm")
        # 走带控制：⏮ ▶ ⏭ ●（画出来的图形）
        cx, cy = W / 2, TOP_BAR / 2
        d.rounded_rectangle([cx - 30, cy - 18, cx + 30, cy + 18], radius=18, fill=a(C["mix"]))
        d.polygon([(cx - 7, cy - 10), (cx - 7, cy + 10), (cx + 11, cy)], fill=a(th["bg"]))
        for sx in (-80, 80):
            x = cx + sx
            s = -1 if sx < 0 else 1
            d.polygon([(x - 8 * s, cy - 9), (x - 8 * s, cy + 9), (x + 4 * s, cy)], fill=a(th["muted"]))
            d.rectangle([x + 5 * s - 2, cy - 9, x + 5 * s + 1, cy + 9], fill=a(th["muted"]))
        d.ellipse([cx + 128, cy - 8, cx + 144, cy + 8], fill=a(th["rec"]))
        d.text((W - 28, TOP_BAR / 2), f"{self.tempo:.0f} BPM   4/4", font=font(th["font_num"], 20),
               fill=a(th["muted"]), anchor="rm")
        d.rectangle([0, RULER_Y, W, RULER_Y + RULER_H], fill=a(th["ruler_bg"], g + 0.1))
        d.line([0, RULER_Y + RULER_H, W, RULER_Y + RULER_H], fill=a(th["ruler_line"]))
        # 轨道头
        for i, t in enumerate(self.tracks):
            y0 = LANE_TOP + i * self.lane_h
            y1 = y0 + self.lane_h - 6
            col = C[t["key"]]
            d.rounded_rectangle([10, y0, HEADER_W - 12, y1], radius=10, fill=a(th["panel"], g + 0.1))
            d.rounded_rectangle([10, y0, 17, y1], radius=3, fill=a(col))
            ic_x, ic_y = 40, y0 + 34
            if t["key"] == "piano":   # 琴键图标
                for k in range(5):
                    d.rectangle([ic_x - 12 + k * 5, ic_y - 12, ic_x - 9 + k * 5, ic_y + 12], fill=a(col))
                for k in (0, 1, 3):
                    d.rectangle([ic_x - 9 + k * 5, ic_y - 12, ic_x - 7 + k * 5, ic_y + 2], fill=a(th["bg"]))
            else:                     # 波形图标
                for k, hh in enumerate((6, 12, 18, 10, 14, 5)):
                    x = ic_x - 13 + k * 5
                    d.rectangle([x, ic_y - hh / 2, x + 2, ic_y + hh / 2], fill=a(col))
            d.text((66, ic_y - 2), t["name"], font=font(th["font_cjk"], 22), fill=a(th["ivory"]), anchor="lm")
            d.text((66, ic_y + 26), t["label"], font=font(th["font_reg"], 15), fill=a(th["muted"]), anchor="lm")
            for k, ch in enumerate("MS"):
                bx = 66 + k * 34
                by = y1 - 34
                if by - (ic_y + 26) < 18:      # 轨道矮的时候 M/S 按钮放到名字右边
                    bx, by = HEADER_W - 104 + k * 34, ic_y - 12
                d.rounded_rectangle([bx, by, bx + 26, by + 22], radius=5, outline=a(th["btn"]), width=1)
                d.text((bx + 13, by + 11), ch, font=font(th["font_semi"], 13), fill=a(th["muted"]), anchor="mm")
            d.rounded_rectangle([HEADER_W - 32, y0 + 14, HEADER_W - 22, y1 - 14], radius=4,
                                fill=a(th["meter_bg"], g + 0.2))
        if self.bottom:               # 底部歌词区的毛玻璃面板
            y0 = H - self.bottom
            d.rounded_rectangle([10, y0, W - 10, H - 10], radius=14, fill=a(th["panel"], g))
        if self.glass:
            self.static_rgb, self.static_a = im.convert("RGB"), im.getchannel("A")
        self.static = im

    # ------------------------------------------------------------ 预渲染长条
    def _x(self, sec: float) -> int:
        return int(round((sec + PAD) * PXPS))

    def _build_strips(self):
        th, C = self.th, self.C
        width = self._x(self.dur + PAD)
        lh = self.lane_h - 6
        self.strips, self.strips_lit = [], []
        base_a = th["glass"] * 255 if self.glass else 255
        for i, t in enumerate(self.tracks):
            col = np.array(C[t["key"]], dtype=np.float32)
            base = np.zeros((lh, width, 4), dtype=np.float32)
            base[..., :3] = th["lane_a"] if i % 2 == 0 else th["lane_b"]
            base[..., 3] = base_a
            for b, bt in enumerate(self.beats):          # 节拍网格：每 4 拍一条小节线
                x = self._x(bt)
                if 0 <= x < width:
                    base[:, x, :3] += 26 if b % 4 == 0 else 9
            img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))   # 半透明片段先画在独立图层，再混合到底色上
            d = ImageDraw.Draw(layer)
            for c0, c1 in t["clips"]:
                x0, x1 = self._x(c0), self._x(c1)
                d.rounded_rectangle([x0, 4, x1, lh - 4], radius=9, fill=(*C[t["key"]], 46),
                                    outline=(*C[t["key"]], 150), width=1)
                d.rounded_rectangle([x0, 4, x1, 26], radius=9, fill=(*C[t["key"]], 70))
                label = t["label"] if t["key"] != "mix" else f"{self.title}.mp3"
                d.text((x0 + 10, 15), label, font=font(face(th, "font_semi", label), 14), fill=(*C[t["key"]], 255),
                       anchor="lm")
            img = Image.alpha_composite(img, layer)
            arr = np.asarray(img).astype(np.float32)
            body0, body1 = 30, lh - 8
            if t["key"] == "piano":
                self._draw_notes(arr, t, body0, body1, col)
            else:
                self._draw_wave(arr, t["key"], t["clips"], body0, body1, col)
            dim = arr.copy()
            lit = arr.copy()
            lit[..., :3] = np.clip(lit[..., :3] * 1.18 + 10, 0, 255)
            self.strips.append(Image.fromarray(dim.astype(np.uint8), "RGBA"))
            self.strips_lit.append(Image.fromarray(lit.astype(np.uint8), "RGBA"))

    def _draw_wave(self, arr, key, clips, y0, y1, col):
        """立体声两条波形（上半 L、下半 R），只画在片段范围内。"""
        env = self.env[key]
        ch = env.shape[1]
        n_px = int(math.ceil(self.dur * PXPS))
        idx = np.minimum((np.arange(n_px) / PXPS * self.rate).astype(int), len(env) - 1)
        nxt = np.minimum(idx + max(1, self.rate // PXPS + 1), len(env))
        amp = np.stack([env[a:b].max(axis=0) for a, b in zip(idx, nxt)])     # (n_px, ch)
        active = np.zeros(n_px, bool)
        for c0, c1 in clips:
            active[int(c0 * PXPS): int(c1 * PXPS)] = True
        halves = [(y0, (y0 + y1) / 2), ((y0 + y1) / 2, y1)]
        rows = np.arange(arr.shape[0])[:, None]
        xs = self._x(0) + np.arange(n_px)
        bright = np.minimum(col * 1.12 + 30, 255)
        for c, (h0, h1) in enumerate(halves):
            raw = np.minimum(amp[:, min(c, ch - 1)], 1.0)
            # 非线性压缩：密集段落也能看出强弱起伏，而不是一整块实心
            a = (raw ** 1.7) * 0.9 * active
            mid, half = (h0 + h1) / 2, (h1 - h0) / 2 - 3
            top, bot = mid - a * half, mid + a * half
            mask = (rows >= top[None, :]) & (rows <= bot[None, :])
            region = arr[:, xs[0]: xs[0] + n_px, :3]
            alpha = arr[:, xs[0]: xs[0] + n_px, 3]
            region[mask] = region[mask] * 0.25 + bright * 0.75
            alpha[mask] = 245
            centre = (np.abs(rows - mid) < 0.6) & active[None, :]
            region[centre] = region[centre] * 0.4 + bright * 0.6
            alpha[centre] = 245

    def _draw_notes(self, arr, t, y0, y1, col):
        notes = self.a.get("piano_notes", [])
        if not notes:
            return self._draw_wave(arr, t["key"], t["clips"], y0, y1, col)
        lo = min(p for p, _, _ in notes) - 1
        hi = max(p for p, _, _ in notes) + 1
        span = max(hi - lo, 12)
        nh = max(6.0, (y1 - y0) / span)
        img = Image.fromarray(arr.astype(np.uint8), "RGBA")
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        bright = tuple(int(min(255, c * 1.12 + 30)) for c in col)
        for p, s, e in notes:
            y = y1 - (p - lo) / span * (y1 - y0)
            d.rounded_rectangle([self._x(s), y - nh / 2, max(self._x(s) + 3, self._x(e)), y + nh / 2],
                                radius=2, fill=(*bright, 235))
        arr[:] = np.asarray(Image.alpha_composite(img, layer)).astype(np.float32)

    # ------------------------------------------------------------ 动态元素素材
    def _build_fx(self):
        # 播放头光晕
        g = np.exp(-((np.arange(61) - 30) / 9.0) ** 2)
        self.ph_glow = Image.fromarray((np.tile(g, (H - RULER_Y, 1)) * 90).astype(np.uint8), "L")
        # 播放头经过片段时的闪光
        yy, xx = np.mgrid[0:160, 0:160].astype(np.float32)
        spot = np.exp(-(((xx - 80) / 34) ** 2 + ((yy - 80) / 46) ** 2))
        self.spot = Image.fromarray((spot * 255).astype(np.uint8), "L")
        # 背景漂浮光斑（参考图三的半透明形状）
        rng = np.random.default_rng(3)
        self.blobs = []
        for k in range(7):
            r = int(rng.uniform(70, 150))
            m = Image.new("L", (r * 2, r * 2), 0)
            ImageDraw.Draw(m).ellipse([r * 0.2, r * 0.2, r * 1.8, r * 1.8], fill=255)
            m = m.filter(ImageFilter.GaussianBlur(r * 0.35))
            col = list(self.C.values())[k % len(self.C)]
            self.blobs.append((m, col, rng.uniform(0, 1), rng.uniform(0.15, 0.85), rng.uniform(0.01, 0.025),
                               rng.uniform(0, 6.28), rng.uniform(0.07, 0.14)))

    def _build_ink_base(self):
        gw, gh = W // 4, H // 4
        self._ink_rng = np.random.default_rng(11)

        def octave(cw, ch):
            a = self._ink_rng.random((ch, cw)).astype(np.float32)
            return np.asarray(Image.fromarray(a).resize((gw, gh), Image.BICUBIC), dtype=np.float32)

        def norm(a):
            return (a - a.min()) / (a.max() - a.min())

        self._ink_noise = norm(sum(octave(c, max(2, c * 9 // 16)) / (k + 1) for k, c in enumerate((5, 10, 20, 40))))
        self._ink_brush = norm(octave(16, 40))                  # 横向略拉长的纹理：笔触感
        self.ink_wash = norm(sum(octave(c, max(2, c * 9 // 16)) / (k + 1) for k, c in enumerate((20, 60, 160))))
        self.ink_tone = np.array(self.th["ink"], np.float32)

    def _build_ink(self, src: dict) -> dict:
        """水墨转场用的晕染场：几处墨点（第一处在主图背后）按距离向外扩散，叠加分形噪声和横向笔触纹理，
        让边缘像墨在宣纸上洇开一样不规则。场的值 0→1 表示被墨覆盖的先后顺序。"""
        gw, gh = W // 4, H // 4
        yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
        (ccx, ccy) = src["card_center"]
        blots = [(ccx, ccy, 0.0, 1.0)]                # (x, y, 延迟, 扩散速度)
        for x, y, delay in ((0.12, 0.2, 0.18), (0.86, 0.78, 0.12), (0.9, 0.15, 0.3), (0.1, 0.85, 0.26)):
            blots.append((x * W, y * H, delay, 0.8))
        diag = math.hypot(W, H)
        field = np.full((gh, gw), 9.0, np.float32)
        for bx, by, delay, speed in blots:
            d = np.hypot(xx * 4 - bx, yy * 4 - by) / diag / speed + delay
            field = np.minimum(field, d)
        field = field + (self._ink_noise - 0.5) * 0.22 + (self._ink_brush - 0.5) * 0.06
        # 旧画面逐渐虚化：预先算好几档模糊
        base = src["last_frame"].convert("RGB")
        return {"field": (field - field.min()) / (field.max() - field.min()), "src": src,
                "blur": [(0, base)] + [(r, base.filter(ImageFilter.GaussianBlur(r))) for r in (6, 14, 28)]}

    @staticmethod
    def _blurred(levels, r: float) -> Image.Image:
        for (r0, a), (r1, b) in zip(levels, levels[1:]):
            if r <= r1:
                return Image.blend(a, b, (r - r0) / (r1 - r0))
        return levels[-1][1]

    # ------------------------------------------------------------ 每一帧
    def progress(self, t: float) -> float:
        """0 = 开头/结尾的转场画面，1 = 完全是编曲界面（给颗粒感等叠加效果做淡入淡出）。"""
        u = (t - self.t_entry) / ENTRY if self.intro else 1.0
        if self.outro and self.t_last is not None:
            u = min(u, (self.t_last - t) / OUTRO)
        return min(max(u, 0.0), 1.0)

    def frame(self, t: float) -> Image.Image:
        if self.outro and self.t_last is not None and t > self.t_last - OUTRO:
            return self._entrance(t, max((self.t_last - t) / OUTRO, 0.0), self.ink_out)
        u = (t - self.t_entry) / ENTRY if self.intro else 1.0
        if u >= 1.0:
            im = self._render(t, playhead=True)
            if self.thumb:
                k = self.beat_kick(t) if HERO else 0.0
                if k > 0.01:                  # 竖屏大封面在重拍上跳一下
                    s = int(round(self.thumb.width * (1 + 0.05 * k)))
                    th_ = self.thumb.resize((s, s), Image.BILINEAR)
                    cx, cy = (THUMB[0] + THUMB[2]) / 2, (THUMB[1] + THUMB[3]) / 2
                    im.paste(th_, (int(cx - s / 2), int(cy - s / 2)), th_)
                else:
                    im.paste(self.thumb, THUMB[:2], self.thumb)
            return self._zoom(im, t)
        return self._entrance(t, max(u, 0.0), self.ink_in)

    def beat_kick(self, t: float) -> float:
        """重拍后的冲击量：重拍瞬间为 1，约 0.35 秒内衰减到 0。"""
        if not len(self.downbeats):
            return 0.0
        i = int(np.searchsorted(self.downbeats, t, side="right")) - 1
        if i < 0:
            return 0.0
        dt = t - float(self.downbeats[i])
        return math.exp(-dt / 0.12) if dt < 0.35 else 0.0

    def _zoom(self, im: Image.Image, t: float) -> Image.Image:
        """重拍时整个画面轻微推近再回弹。"""
        k = self.beat_kick(t) * self.pulse
        if k < 0.0005:
            return im
        cw, ch = W / (1 + k), H / (1 + k)
        x0, y0 = (W - cw) / 2, (H - ch) / 2
        return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))

    def _entrance(self, t: float, u: float, ink_s: dict) -> Image.Image:
        """水墨转场：开头画面逐渐虚化、压暗 → 墨从主图背后和画面四周洇开，墨迹里露出（由虚到实的）编曲界面
        → 主图卡片沿弧线飞到标题栏小图位置 → 播放头画出来。u=0 时与开头最后一帧完全一致。
        结尾用同一个函数倒着走（u 从 1 到 0），最后一帧就是开头第一帧。"""
        src = ink_s["src"]
        daw_im = self._render(t, playhead=False)
        # 旧画面：越来越虚、越来越暗
        old = self._blurred(ink_s["blur"], 28 * _smooth(u / 0.7))
        old = Image.blend(old, Image.new("RGB", (W, H), self.th["bg"]), 0.35 * _smooth(u / 0.8))
        # 新画面：先虚后实
        soft = 1 - _smooth((u - 0.15) / 0.65)
        if soft > 0.01:
            small = daw_im.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
            daw_im = Image.blend(daw_im, small.resize((W, H), Image.BICUBIC), soft)
        # 先是墨晕开（深色、带浓淡），稍后墨里透出新画面；两道遮罩阈值随时间推进，边缘柔和
        edge, lead = 0.14, 0.16
        x = min(u / 0.8, 1.0)
        e = (0.5 * _smooth(x) + 0.5 * x * (2 - x)) * (1 + edge + lead)   # 起步比 smoothstep 快一点
        ink = np.clip((e - ink_s["field"]) / edge, 0, 1)
        show = np.clip((e - lead - ink_s["field"]) / edge, 0, 1)
        ink, show = ink * ink * (3 - 2 * ink), show * show * (3 - 2 * show)
        a_ink = ink * (1 - show) * (0.78 + 0.22 * self.ink_wash)      # 墨色浓淡不匀，像水墨
        full = lambda x: np.asarray(Image.fromarray((x * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),  # noqa: E731
                                    dtype=np.float32)[..., None] / 255
        out = Image.composite(daw_im, old, Image.fromarray((show * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC))
        k = full(a_ink)
        arr = np.asarray(out, dtype=np.float32)
        out = Image.fromarray((arr * (1 - k) + self.ink_tone * k).astype(np.uint8))
        # 播放头从上往下画出来
        g = _smooth((u - 0.55) / 0.35)
        if g > 0:
            d = ImageDraw.Draw(out)
            y_end = RULER_Y + g * (H - RULER_Y)
            ph = self.th["playhead"]
            d.rectangle([PLAYHEAD_X - 1, RULER_Y, PLAYHEAD_X + 1, y_end], fill=ph)
            d.polygon([(PLAYHEAD_X - 9, RULER_Y + 2), (PLAYHEAD_X + 9, RULER_Y + 2), (PLAYHEAD_X, RULER_Y + 16)],
                      fill=ph)
        # 主图卡片飞向小图位置（带一点弧线），全程连续，最后正好落在小图上
        p = _in_out_cubic(u / 0.72)
        (cx0, cy0), s0 = src["card_center"], src["card_size"]
        cx1, cy1 = (THUMB[0] + THUMB[2]) / 2, (THUMB[1] + THUMB[3]) / 2
        s1 = THUMB[2] - THUMB[0]
        cx = cx0 + (cx1 - cx0) * p
        cy = cy0 + (cy1 - cy0) * p - math.sin(math.pi * p) * 70
        s = max(4, int(s0 + (s1 - s0) * p))
        card = src["card"] if src["card"].width == s else src["card"].resize((s, s), Image.BILINEAR)
        out.paste(card, (int(cx - s / 2), int(cy - s / 2)), card)
        return out

    def _base(self, t: float) -> Image.Image:
        if not self.glass:
            return self.static.copy()
        # 背景缓慢漂移（椭圆轨迹），随原曲电平轻微提亮
        bw, bh = self.backdrop.size
        ox = (bw - W) / 2 + math.sin(t * 0.07) * (bw - W) * 0.45
        oy = (bh - H) / 2 + math.cos(t * 0.05) * (bh - H) * 0.45
        im = self.backdrop.crop((int(ox), int(oy), int(ox) + W, int(oy) + H))
        im.paste(self.static_rgb, (0, 0), self.static_a)
        return im

    def _render(self, t: float, playhead: bool = True) -> Image.Image:
        th, C = self.th, self.C
        im = self._base(t)
        d = ImageDraw.Draw(im)
        left_sec = (PLAYHEAD_X - TL_X) / PXPS
        sx = self._x(t - left_sec)
        ph_rel = PLAYHEAD_X - TL_X
        f_idx = min(int(t * self.rate), len(next(iter(self.level.values()))) - 1)

        # 标尺：小节号 + 拍刻度
        for b, bt in enumerate(self.beats):
            x = TL_X + self._x(bt) - sx
            if TL_X <= x < W:
                if b % 4 == 0:
                    d.line([x, RULER_Y + 14, x, RULER_Y + RULER_H], fill=th["bar_tick"])
                    d.text((x + 5, RULER_Y + 16), str(b // 4 + 1), font=font(th["font_num"], 15), fill=th["muted"],
                           anchor="lm")
                else:
                    d.line([x, RULER_Y + 28, x, RULER_Y + RULER_H], fill=th["beat_tick"])

        # 轨道：播放头右边是未播放部分，左边是已播放部分(更亮)
        lh = self.lane_h - 6
        for i, t_ in enumerate(self.tracks):
            y0 = LANE_TOP + i * self.lane_h
            dim = self.strips[i].crop((sx + ph_rel, 0, sx + TL_W, lh))
            lit = self.strips_lit[i].crop((sx, 0, sx + ph_rel, lh))
            if self.glass:
                im.paste(dim, (TL_X + ph_rel, y0), dim)
                im.paste(lit, (TL_X, y0), lit)
            else:
                im.paste(dim, (TL_X + ph_rel, y0))
                im.paste(lit, (TL_X, y0))
            key = t_["key"]
            lv = float(self.level[key][f_idx])
            self.meter[key] = max(lv, self.meter[key] * 0.86)          # 电平：快起慢落
            mh = (self.lane_h - 34) * min(1.0, self.meter[key])
            yb = y0 + self.lane_h - 6 - 14
            if mh > 1:
                d.rounded_rectangle([HEADER_W - 31, yb - mh, HEADER_W - 23, yb], radius=3, fill=C[key])
            in_clip = any(c0 <= t <= c1 for c0, c1 in t_["clips"])
            if in_clip and lv > 0.05:                                  # 播放头经过有声片段时闪光
                a = min(1.0, lv) * 0.9
                spot = self.spot.resize((160, lh))
                im.paste(C[key], (PLAYHEAD_X - 80, y0), spot.point(lambda v, a=a: int(v * a * 0.55)))

        # 漂浮光斑
        lanes_bottom = H - self.bottom
        for m, col, x0, y0f, sp, ph, al in self.blobs:
            x = TL_X + ((x0 - t * sp) % 1.2 - 0.1) * TL_W
            y = LANE_TOP + (y0f + 0.05 * math.sin(t * 0.4 + ph)) * (lanes_bottom - LANE_TOP)
            im.paste(col, (int(x - m.width / 2), int(y - m.height / 2)), m.point(lambda v, a=al: int(v * a)))

        # 播放头
        if playhead:
            glow = self.ph_glow.crop((0, 0, 61, lanes_bottom - RULER_Y))
            k = self.beat_kick(t) if self.pulse else 0.0
            if k > 0.01:                       # 重拍时播放头光晕更亮
                glow = glow.point(lambda v, k=k: min(255, int(v * (1 + 1.6 * k))))
            im.paste(th["ph_glow"], (PLAYHEAD_X - 30, RULER_Y), glow)
            d.rectangle([PLAYHEAD_X - 1, RULER_Y, PLAYHEAD_X + 1, lanes_bottom], fill=th["playhead"])
            d.polygon([(PLAYHEAD_X - 9, RULER_Y + 2), (PLAYHEAD_X + 9, RULER_Y + 2), (PLAYHEAD_X, RULER_Y + 16)],
                      fill=th["playhead"])

        # 时间码（歌曲中的实际位置）
        pos = self.song_start + t
        tc = f"{int(pos // 60):02d}:{pos % 60:05.2f}"
        d.text((W / 2 + (170 if HERO else 230), TOP_BAR / 2), tc, font=font(th["font_num"], 24), fill=th["ivory"],
               anchor="lm")
        for ov in self.overlays:          # 烟花、歌词、小人等
            ov(im, t)
        return im
