"""从音乐播放器截图里裁出专辑封面；普通图片则居中裁成正方形。

播放器截图（竖长，宽约 1179）：封面是半透明卡片里的一个正方形，距卡片顶边固定 74 像素。
先找卡片顶边（深色背景突然变亮处），再推出封面位置；找不到时用最常见的位置兜底。
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# 以 1179 宽的截图为基准（其他尺寸按比例换算）
REF_W = 1179
ALBUM_X0, ALBUM_X1 = 187, 995          # 封面左右边界
CARD_TO_ALBUM = 74                     # 卡片顶边到封面顶边的距离
DEFAULT_Y0 = 590                       # 兜底：最常见的封面上边界
INSET = 14                             # 往里收一点，避开截图里封面自带的圆角


def is_player_screenshot(img: Image.Image) -> bool:
    w, h = img.size
    return h / w > 1.9 and w >= 700


def _find_top(a: np.ndarray, k: float, side: int) -> int:
    """封面上边界 = 播放器卡片顶边 + 固定间距。卡片顶边是正中一条竖带从深色背景突然变亮的那一行。"""
    gray = a.mean(axis=2) if a.ndim == 3 else a
    cx = int(a.shape[1] / 2)
    band = gray[:, cx - 30: cx + 30].mean(axis=1)
    step = max(2, int(6 * k))
    for y in range(int(250 * k), int(1000 * k)):
        if band[y] - band[y - step] > 25 and band[y: y + int(40 * k)].min() > band[y - step] + 15:
            return y + int(CARD_TO_ALBUM * k)
    return int(DEFAULT_Y0 * k)


def crop_cover(path: Path) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if not is_player_screenshot(img):
        s = min(img.size)
        return ImageOps.fit(img, (s, s), Image.LANCZOS)
    k = img.width / REF_W
    a = np.asarray(img)
    side = int((ALBUM_X1 - ALBUM_X0) * k)
    y0 = _find_top(a, k, side)
    x0 = int(ALBUM_X0 * k)
    i = int(INSET * k)
    return img.crop((x0 + i, y0 + i, x0 + side - i, y0 + side - i))
