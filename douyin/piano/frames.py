"""逐帧渲染：下落音符 + 发光 + 琴键按下 + 文字。

为了速度，合成全部在 Pillow 的 uint8 图像上完成；numpy 只用于琴键蒙版。
"""
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from keyboard import Keyboard, hex_rgb, is_black, key_range
from overlay import background, note_visibility, text_layer

GLOW_DOWNSCALE = 4


def _u8(arr: np.ndarray) -> np.ndarray:
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)


def _rgb(c: np.ndarray) -> tuple[int, int, int]:
    return tuple(int(round(float(v) * 255)) for v in c)


class Renderer:
    def __init__(self, cfg: dict, notes: dict, meta: dict, duration: float):
        v, lay, nc = cfg["video"], cfg["layout"], cfg["notes"]
        self.w, self.h = v["width"], v["height"]
        self.lead = cfg["timing"]["lead_in"]
        self.duration = duration
        self.look = nc["lookahead"]

        low, high = key_range(notes["pitch"], lay["key_range"])
        keep = (notes["pitch"] >= low) & (notes["pitch"] <= high)
        n = {k: a[keep] for k, a in notes.items()}
        # 琴键高度不超过真实比例（白键长 ≈ 宽 × 6.4），避免竖屏时被拉长
        n_white = sum(1 for p in range(low, high + 1) if not is_black(p))
        kb_h = min(int(self.h * lay["keyboard_height"]), int(self.w / n_white * 6.4))
        self.kb_y = int(self.h * lay["keyboard_bottom"]) - kb_h
        self.kb = Keyboard(self.w, kb_h, low, high)
        self.speed = self.kb_y / self.look

        self.pitch, self.start = n["pitch"], n["start"]
        # 同音高相邻音符之间留一点缝
        self.end = np.maximum(n["end"] - 0.03, n["start"] + 0.04)
        pad = self.kb.ww * 0.08
        self.x0 = np.array([self.kb.rects[p][0] + pad for p in self.pitch], dtype=np.float32)
        self.x1 = np.array([self.kb.rects[p][1] - pad for p in self.pitch], dtype=np.float32)
        self.hand = n["hand"] if nc["color_by_hand"] else np.zeros_like(n["hand"])

        sides = ("left", "right") if nc["color_by_hand"] else ("right", "right")
        core = [hex_rgb(nc[s]["core"]) for s in sides]
        glow = [hex_rgb(nc[s]["glow"]) for s in sides]
        self.core = [_rgb(c) for c in core]
        self.glow_size = (self.w // GLOW_DOWNSCALE, self.kb_y // GLOW_DOWNSCALE)
        self.glow_img = [Image.new("RGB", self.glow_size, _rgb(g * nc["glow_strength"])) for g in glow]

        # 琴键：uint8 底图 + 每只手的按下图
        self.kb_base = _u8(self.kb.base)
        self.kb_pressed = [_u8(self.kb.pressed_image(c * 0.55 + g * 0.45)) for c, g in zip(core, glow)]

        self.bg = Image.fromarray(_u8(background(self.w, self.h, cfg)))
        ImageDraw.Draw(self.bg).rectangle([0, self.kb_y - 3, self.w, self.kb_y - 1], fill=(184, 184, 194))
        self.text = None
        t = text_layer(self.w, self.h, meta, cfg)
        if t:
            box, a, rgb = t
            self.text = (box, Image.fromarray(_u8(rgb / np.maximum(a, 1e-6))), Image.fromarray(_u8(a[:, :, 0])))
        self._init_effects(cfg)
        # 音符可见度蒙版（标题区内为 0）；全为 1 时不做处理以节省时间
        vis_rows = note_visibility(self.w, self.h, meta, cfg)[: self.kb_y]
        self.note_mask = None
        if vis_rows.min() < 0.999:
            col = (vis_rows * 255).astype(np.uint8)
            self.note_mask = Image.fromarray(np.repeat(col[:, None], self.w, axis=1))
            self.note_mask_small = self.note_mask.resize(self.glow_size, Image.BILINEAR)

        # 击键闪光：椭圆高斯光斑（L 图，1/4 分辨率），底边贴琴键顶
        sw, sh = int(self.kb.ww * 4 / GLOW_DOWNSCALE), int(self.h * 0.09 / GLOW_DOWNSCALE)
        yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
        spot = np.exp(-(((xx - sw / 2) / (sw / 5)) ** 2) - (((yy - sh) / (sh / 2.2)) ** 2))
        self.flash = Image.fromarray(_u8(spot))

    # ---- 交互特效（全部只由时间 t 决定，分段并行渲染也能无缝衔接） ----
    SPARK_LIFE = 0.9
    SHEEN_TIME = 0.45

    def _init_effects(self, cfg: dict) -> None:
        fx = cfg.get("effects", {})
        self.fx_sheen = bool(fx.get("sheen", True))
        self.fx_flow = bool(fx.get("line_flow", True))
        n_sparks = int(fx.get("sparks", 6))
        k = self.h / 1080
        # 每个音符的光点参数预先随机好：水平速度、上升速度、寿命、半径
        rng = np.random.default_rng(20261014)
        n = len(self.pitch)
        self.sparks = None
        if n_sparks > 0 and n:
            self.sparks = np.stack([
                rng.uniform(-70, 70, (n, n_sparks)) * k,
                rng.uniform(140, 380, (n, n_sparks)) * k,
                rng.uniform(0.45, self.SPARK_LIFE, (n, n_sparks)),
                rng.uniform(2.2, 4.6, (n, n_sparks)) * k,
            ], axis=-1)
        # 每个琴键的像素范围与形状(白键要避开压在上面的黑键)
        self.key_masks = {}
        for p, (x0, x1) in self.kb.rects.items():
            a, b = max(int(x0) - 1, 0), min(int(x1) + 2, self.w)
            m = self.kb.labels[:, a:b] == p
            self.key_masks[p] = (a, b, m)
        self.glow_rgb = [np.array(im.getpixel((0, 0)), dtype=np.float32) for im in self.glow_img]

    def _line(self, t: float, pressed: np.ndarray) -> np.ndarray:
        """琴键顶部 3px 亮线：底色 + 来回游走的流光 + 被按键位置的彩色光晕。"""
        x = np.arange(self.w, dtype=np.float32)
        light = np.full(self.w, 0.72, dtype=np.float32)
        tint = np.zeros((self.w, 3), dtype=np.float32)
        if self.fx_flow:
            period = 4.0
            u = (t % period) / period
            cx = (u * 1.4 - 0.2) * self.w if int(t // period) % 2 == 0 else (1.2 - u * 1.4) * self.w
            light += 0.28 * np.exp(-((x - cx) / (self.w * 0.06)) ** 2)
        for i in np.nonzero(pressed)[0]:
            cx = (self.x0[i] + self.x1[i]) / 2
            g = np.exp(-((x - cx) / (self.kb.ww * 1.6)) ** 2)
            tint += g[:, None] * self.glow_rgb[self.hand[i]][None, :] / 255 * 0.9
        row = np.clip(light[:, None] * np.array([0.98, 0.98, 1.0]) + tint, 0, 1)
        return np.repeat(_u8(row)[None, :, :], 3, axis=0)

    def frame(self, tv: float) -> Image.Image:
        """完整画面：背景 + 音符 + 琴键 + 文字，带首尾淡入淡出。"""
        t = tv - self.lead
        pressed = (self.start <= t) & (self.end > t)
        img = self.bg.copy()
        self._draw_notes(img, t, pressed)
        img.paste(Image.fromarray(self._line(t, pressed)), (0, self.kb_y - 3))
        img.paste(self._keyboard(t, pressed), (0, self.kb_y))

        if self.text:
            box, rgb, a = self.text
            img.paste(rgb, box[:2], mask=a)

        fade = min(1.0, tv / 0.8, (self.duration - tv) / 1.5)
        if fade < 1:
            f = max(fade, 0.0)
            img = img.point(lambda v: v * f)
        return img

    # ---- 剪映分层输出 ----
    @property
    def strip_box(self) -> tuple[int, int]:
        """琴键条(含顶部亮线)在画面中的 (y, 高度)，高度取偶数以便 yuv420 编码。"""
        y = self.kb_y - 4
        h = self.kb.h + 4
        return y, h + h % 2

    def notes_layer(self, tv: float) -> Image.Image:
        """纯黑底上的下落音符与发光，在剪映中用「滤色」叠加到背景上。"""
        t = tv - self.lead
        img = Image.new("RGB", (self.w, self.h), 0)
        self._draw_notes(img, t, (self.start <= t) & (self.end > t))
        return img

    def keys_layer(self, tv: float) -> Image.Image:
        t = tv - self.lead
        pressed = (self.start <= t) & (self.end > t)
        y, h = self.strip_box
        img = Image.new("RGB", (self.w, h), 0)
        img.paste(Image.fromarray(self._line(t, pressed)), (0, 1))
        img.paste(self._keyboard(t, pressed), (0, 4))
        return img

    def _keyboard(self, t: float, pressed: np.ndarray) -> Image.Image:
        kb = self.kb_base.copy()
        for hand in (0, 1):
            p = self.pitch[pressed & (self.hand == hand)]
            if len(p):
                m = np.isin(self.kb.labels, p)
                kb[m] = self.kb_pressed[hand][m]
        if self.fx_sheen:
            # 流光：刚按下的琴键上一道亮带从上往下扫过
            kh = self.kb.h
            rows = np.arange(kh, dtype=np.float32)
            for i in np.nonzero(pressed & (t - self.start < self.SHEEN_TIME))[0]:
                age = (t - self.start[i]) / self.SHEEN_TIME
                cy = -0.25 * kh + age * 1.5 * kh
                band = np.exp(-((rows - cy) / (kh * 0.12)) ** 2) * (1 - age) * 150
                a, b, m = self.key_masks[int(self.pitch[i])]
                region = kb[:, a:b].astype(np.int16)
                region += (band[:, None] * m)[:, :, None].astype(np.int16)
                kb[:, a:b] = np.clip(region, 0, 255).astype(np.uint8)
        return Image.fromarray(kb)

    def _draw_notes(self, img: Image.Image, t: float, pressed: np.ndarray) -> None:
        w, fh = self.w, self.kb_y
        vis = (self.start < t + self.look) & (self.end > t)
        sparking = (self.start <= t) & (self.start > t - self.SPARK_LIFE) if self.sparks is not None else None
        for hand in (0, 1):
            idx = np.nonzero(vis & (self.hand == hand))[0]
            sp_idx = np.nonzero(sparking & (self.hand == hand))[0] if sparking is not None else []
            if not len(idx) and not len(sp_idx):
                continue
            core = Image.new("L", (w, fh), 0)
            d = ImageDraw.Draw(core)
            for i in idx:
                yb = min(fh - (self.start[i] - t) * self.speed, fh)
                yt = max(fh - (self.end[i] - t) * self.speed, -10)
                x0, x1 = float(self.x0[i]), float(self.x1[i])
                r = max(1, min(6, (x1 - x0) / 2 - 1, (yb - yt) / 2 - 1))
                d.rounded_rectangle([x0, yt, x1, yb], radius=r, fill=255)
            # 击键光点：从琴键顶部溅起，受重力减速，逐渐熄灭（单独一层再取最亮值，避免擦暗音符）
            g = 320 * self.h / 1080
            if len(sp_idx):
                spk = Image.new("L", (w, fh), 0)
                d = ImageDraw.Draw(spk)
            for i in sp_idx:
                age = t - self.start[i]
                cx = (self.x0[i] + self.x1[i]) / 2
                for vx, vy, life, rad in self.sparks[i]:
                    if age >= life:
                        continue
                    px = cx + vx * age
                    py = fh - 2 - (vy * age - 0.5 * g * age * age)
                    a = int(255 * (1 - age / life) ** 1.5)
                    if py < fh and a > 8:
                        d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=a)
            if len(sp_idx):
                core = ImageChops.lighter(core, spk)
            if self.note_mask is not None:
                core = ImageChops.multiply(core, self.note_mask)

            # 发光与击键闪光都在 1/4 分辨率上计算、着色，最后放大
            sw, sh = self.glow_size
            glow = core.resize((sw, sh), Image.BILINEAR)
            glow = glow.filter(ImageFilter.GaussianBlur(4)).point(lambda v: min(255, v * 1.6))
            if self.note_mask is not None:
                glow = ImageChops.multiply(glow, self.note_mask_small)
            fw, fhh = self.flash.size
            for i in np.nonzero(pressed & (self.hand == hand))[0]:
                k = 0.45 + 0.55 * np.exp(-(t - self.start[i]) / 0.18)
                cx = int((self.x0[i] + self.x1[i]) / 2 / GLOW_DOWNSCALE) - fw // 2
                spot = self.flash.point(lambda v, k=k: v * k)
                region = glow.crop((cx, sh - fhh, cx + fw, sh))
                glow.paste(ImageChops.add(region, spot), (cx, sh - fhh))
            glow = ImageChops.multiply(self.glow_img[hand], glow.convert("RGB")).resize((w, fh), Image.BILINEAR)

            top = img.crop((0, 0, w, fh))
            top = ImageChops.add(top, glow)
            top.paste(self.core[hand], mask=core)
            img.paste(top, (0, 0))
