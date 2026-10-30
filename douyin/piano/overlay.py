"""背景与文字图层。"""
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from keyboard import hex_rgb

CJK = re.compile(r"[　-鿿＀-￯]")


def background(w: int, h: int, cfg: dict) -> np.ndarray:
    bg = cfg["background"]
    if bg.get("image"):
        from PIL import ImageOps
        img = ImageOps.fit(Image.open(bg["image"]).convert("RGB"), (w, h), Image.LANCZOS)
        arr = np.asarray(img, dtype=np.float32) / 255 * 0.35
    else:
        y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        arr = hex_rgb(bg["top"]) * (1 - y) + hex_rgb(bg["bottom"]) * y
        arr = np.broadcast_to(arr, (h, w, 3)).copy()
    # 暗角
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    arr *= np.clip(1.15 - 0.45 * d, 0.4, 1)[:, :, None]
    return arr


def _small_caps(draw, x, y, text, font_path, size, fill, dry=False):
    """首字母大、其余为小号大写字母，基线对齐。返回结束 x 坐标；dry=True 只测量不绘制。"""
    big, small = ImageFont.truetype(font_path, size), ImageFont.truetype(font_path, int(size * 0.76))
    for word in text.split(" "):
        for i, ch in enumerate(word):
            f = big if i == 0 or not ch.isalpha() else small
            ch = ch.upper()
            if not dry:
                draw.text((x, y), ch, font=f, fill=fill, anchor="ls")
            x += draw.textlength(ch, font=f) + size * 0.02
        x += size * 0.32
    return x - size * 0.32


def _width(draw, text, cfg, size) -> float:
    if CJK.search(text):
        return draw.textlength(text, font=ImageFont.truetype(cfg["text"]["cjk_font"], size))
    return _small_caps(draw, 0, 0, text, cfg["text"]["font"], size, None, dry=True)


def _text(draw, x, y, text, cfg, size, fill, max_w, align="left"):
    """绘制一行文字，超出 max_w 时自动缩小字号；align=right 时 x 为右边界。"""
    while size > 12 and _width(draw, text, cfg, size) > max_w:
        size = int(size * 0.92)
    if align == "right":
        x -= _width(draw, text, cfg, size)
    if CJK.search(text):
        draw.text((x, y), text, font=ImageFont.truetype(cfg["text"]["cjk_font"], size), fill=fill, anchor="ls")
    else:
        _small_caps(draw, x, y, text, cfg["text"]["font"], size, fill)


def text_layer(w: int, h: int, meta: dict, cfg: dict) -> tuple[tuple[int, int, int, int], np.ndarray, np.ndarray] | None:
    """返回 (包围盒 x0,y0,x1,y1, alpha, 预乘颜色)，只保留有文字的区域以节省内存。"""
    img = text_image(w, h, meta, cfg)
    box = img.getbbox()
    if box is None:
        return None
    arr = np.asarray(img.crop(box), dtype=np.float32) / 255
    a = arr[:, :, 3:4]
    return box, a, arr[:, :, :3] * a


def _smooth(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def title_band(h: int, s: int, meta: dict) -> float:
    """标题/副标题文字区的底边 y（无标题时为 0）。"""
    if not (meta.get("title") or meta.get("subtitle")):
        return 0.0
    return h * 0.04 + s * (0.07 + (0.065 + 0.02 if meta.get("subtitle") else 0.02))


def note_visibility(w: int, h: int, meta: dict, cfg: dict) -> np.ndarray:
    """每一行音符的可见度(0-1)：标题区内完全不画音符，往下平滑出现，标题绝不会被遮挡。"""
    y = np.arange(h, dtype=np.float32)
    bottom = title_band(h, min(w, h), meta)
    if bottom <= 0 or not cfg.get("effects", {}).get("note_fade", True):
        return np.ones(h, dtype=np.float32)
    return _smooth((y - bottom - h * 0.01) / (h * 0.14))


def scrim_image(w: int, h: int, meta: dict, cfg: dict) -> Image.Image | None:
    """文字后面的黑色渐隐蒙版：顶部盖住标题区再柔和过渡；有水印时琴键下方也压暗。"""
    strength = float(cfg.get("effects", {}).get("scrim", 0))
    if strength <= 0 or not (meta.get("title") or meta.get("subtitle") or meta.get("watermark")):
        return None
    s = min(w, h)
    y = np.arange(h, dtype=np.float32)
    alpha = np.zeros(h, dtype=np.float32)
    if meta.get("title") or meta.get("subtitle"):
        text_bottom = title_band(h, s, meta)
        fade = h * 0.16
        alpha = np.maximum(alpha, 1 - _smooth((y - text_bottom) / fade))
    if meta.get("watermark") or meta.get("corner_text"):
        kb_bottom = h * cfg["layout"]["keyboard_bottom"]
        alpha = np.maximum(alpha, _smooth((y - kb_bottom) / max(h - kb_bottom, 1) * 3))
    a = (alpha * strength * 255).astype(np.uint8)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.putalpha(Image.fromarray(np.repeat(a[:, None], w, axis=1)))
    return img


def text_image(w: int, h: int, meta: dict, cfg: dict, with_scrim: bool = True) -> Image.Image:
    """标题、副标题、左下角文字、右下角水印的整幅透明图层（默认叠在蒙版上）。"""
    scrim = scrim_image(w, h, meta, cfg) if with_scrim else None
    img = scrim if scrim is not None else Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x = int(w * 0.075)
    max_w = w - 2 * x
    s = min(w, h)  # 字号以短边为基准，横竖屏一致
    y = int(h * 0.04) + int(s * 0.07)
    if meta.get("title"):
        _text(draw, x, y, meta["title"], cfg, int(s * 0.058), (240, 240, 240, 255), max_w)
        y += int(s * 0.065)
    if meta.get("subtitle"):
        _text(draw, x, y, meta["subtitle"], cfg, int(s * 0.034), (196, 196, 196, 255), max_w)
    if meta.get("corner_text"):
        _text(draw, x, int(h - s * 0.05), meta["corner_text"], cfg, int(s * 0.045), (230, 230, 230, 220), max_w)
    if meta.get("watermark"):
        _text(draw, w - x, int(h - s * 0.05), meta["watermark"], cfg, int(s * 0.03), (255, 255, 255, 190),
              max_w // 2, align="right")
    return img
