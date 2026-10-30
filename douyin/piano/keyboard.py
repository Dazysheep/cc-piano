"""琴键布局与绘制。所有图像为 float32 RGB(0-1)。"""
import numpy as np

BLACK = {1, 3, 6, 8, 10}


def is_black(p: int) -> bool:
    return p % 12 in BLACK


def key_range(pitches: np.ndarray, mode: str) -> tuple[int, int]:
    if mode == "full":
        return 21, 108
    lo, hi = int(pitches.min()) - 2, int(pitches.max()) + 2
    while hi - lo < 48:  # 至少 4 个八度，避免琴键过宽
        lo, hi = lo - 1, hi + 1
    lo, hi = max(lo, 21), min(hi, 108)
    while lo > 21 and lo % 12 not in (0, 5):  # 起于 C 或 F
        lo -= 1
    while hi < 108 and hi % 12 not in (4, 11):  # 止于 E 或 B
        hi += 1
    return lo, hi


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


class Keyboard:
    def __init__(self, width: int, height: int, low: int, high: int):
        self.w, self.h = width, height
        whites = [p for p in range(low, high + 1) if not is_black(p)]
        self.ww = width / len(whites)
        bw = self.ww * 0.58
        self.bh = int(height * 0.63)

        self.rects: dict[int, tuple[float, float]] = {}
        wi = 0
        for p in range(low, high + 1):
            if is_black(p):
                self.rects[p] = (wi * self.ww - bw / 2, wi * self.ww + bw / 2)
            else:
                self.rects[p] = (wi * self.ww, (wi + 1) * self.ww)
                wi += 1

        # 像素 → 琴键编号，-1 为缝隙
        self.labels = np.full((height, width), -1, dtype=np.int16)
        for p, (x0, x1) in self.rects.items():
            if not is_black(p):
                self.labels[:, round(x0) : max(round(x1) - 1, round(x0) + 1)] = p
        for p, (x0, x1) in self.rects.items():
            if is_black(p):
                self.labels[: self.bh, max(round(x0), 0) : round(x1)] = p

        self.base = self._draw_base()
        self.pressed: dict[int, np.ndarray] = {}

    def _draw_base(self) -> np.ndarray:
        h, w = self.h, self.w
        y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        white = 0.66 + 0.24 * np.clip(y * 2.2, 0, 1)        # 顶部略暗，向下变亮(偏银灰)
        white = np.where(y > 0.94, white * 0.82, white)     # 琴键前沿
        yb = np.linspace(0, 1, self.bh, dtype=np.float32)[:, None]
        black_col = 0.05 + 0.07 * yb
        black_col = np.where(yb > 0.9, 0.22, black_col)     # 黑键前沿高光

        img = np.full((h, w), 0.1, dtype=np.float32)        # 缝隙
        is_w = (self.labels >= 0) & ~np.isin(self.labels, [p for p in self.rects if is_black(p)])
        img = np.where(is_w, np.broadcast_to(white, (h, w)), img)
        bmask = np.zeros((h, w), bool)
        bmask[: self.bh] = np.isin(self.labels[: self.bh], [p for p in self.rects if is_black(p)])
        full_black = np.zeros((h, w), dtype=np.float32)
        full_black[: self.bh] = black_col
        img = np.where(bmask, full_black, img)

        # 黑键在白键上的投影
        shadow = np.zeros((h, w), bool)
        shadow[self.bh : self.bh + max(3, h // 40)] = bmask[self.bh - 1]
        img = np.where(shadow & is_w, img * 0.72, img)
        # 顶部毛毡阴影
        top = max(4, h // 25)
        img[:top] *= np.linspace(0.35, 1, top, dtype=np.float32)[:, None]

        self.is_white_px, self.is_black_px = is_w, bmask
        return np.repeat(img[:, :, None], 3, axis=2)

    def pressed_image(self, color: np.ndarray) -> np.ndarray:
        key = hash(color.tobytes())
        if key not in self.pressed:
            img = self.base.copy()
            w_mix = self.base * 0.35 + color * 0.65
            b_mix = self.base * 0.3 + color * 0.75
            img[self.is_white_px] = w_mix[self.is_white_px]
            img[self.is_black_px] = b_mix[self.is_black_px]
            self.pressed[key] = img
        return self.pressed[key]

    def render(self, pressed: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
        """pressed: [(音高数组, 颜色)]"""
        out = self.base.copy()
        for pitches, color in pressed:
            if len(pitches):
                m = np.isin(self.labels, pitches)
                out[m] = self.pressed_image(color)[m]
        return out
