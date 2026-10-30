"""软件图标：Claude Code 风格的橙色像素小人，笑着抱着一个大音符，嘴里哼出三个小音符，像烟囱的烟一样往右上角飘。

在 32×32 的像素格子上画，最近邻放大（任务栏的 16/24/32 像素也清楚），底板是紫→靛蓝的圆角方块。
用法: python app/make_icon.py   → app/icon.ico（多尺寸）、app/icon.png（256，也给网页当 favicon）
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ORANGE, HI, SHADE = (217, 119, 87), (238, 152, 120), (184, 92, 64)
INK, MOUTH, BLUSH = (40, 26, 22), (70, 26, 24), (240, 140, 140)
NOTE, NOTE_SH = (255, 255, 255), (206, 214, 255)


def sprite() -> Image.Image:
    g = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    p = g.load()

    def px(x, y, c, a=255):
        if 0 <= x < 32 and 0 <= y < 32:
            p[x, y] = (*c, a)

    def rect(x0, y0, x1, y1, c, a=255):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px(x, y, c, a)

    # 身体（方块）+ 顶部高光 + 底部阴影
    rect(5, 14, 20, 25, ORANGE)
    rect(5, 14, 20, 14, HI)
    rect(5, 25, 20, 25, SHADE)
    rect(20, 15, 20, 25, SHADE)
    # 腿
    for x in (6, 10, 15, 19):
        rect(x, 26, x, 27, SHADE if x in (10, 19) else ORANGE)
    # 笑眼 ^ ^
    for ex in (9, 15):
        for x, y in ((ex - 1, 18), (ex, 17), (ex + 1, 18)):
            px(x, y, INK)
    # 腮红
    px(7, 20, BLUSH)
    px(18, 20, BLUSH)
    # 哼歌的小嘴（o）
    rect(12, 20, 13, 21, MOUTH)
    # 左手
    rect(2, 19, 4, 21, ORANGE)
    rect(2, 21, 4, 21, SHADE)
    # 抱着的大音符（八分音符）：符头在身体右下，符干、符尾往上
    rect(24, 11, 25, 23, NOTE)                       # 符干
    rect(26, 11, 27, 12, NOTE)                       # 符尾
    rect(27, 13, 28, 14, NOTE)
    rect(28, 15, 28, 16, NOTE_SH)
    rect(20, 22, 25, 25, NOTE)                       # 符头
    rect(21, 21, 24, 21, NOTE)
    rect(21, 26, 24, 26, NOTE_SH)
    rect(20, 25, 21, 25, NOTE_SH)
    # 右手抱住音符（盖在符头前面）
    rect(19, 21, 22, 23, ORANGE)
    rect(19, 23, 22, 23, SHADE)
    return g


def hum_notes(img: Image.Image, cell: float, off: int) -> None:
    """嘴里哼出的三个小音符：从嘴上方开始往右上角飘（像烟囱的烟），一个比一个大、一个比一个淡、各自歪一点。"""
    from PIL import ImageFont
    size = img.width
    for gx, gy, k, a, rot in ((12.0, 7.5, 0.15, 255, -12), (16.5, 2.8, 0.19, 215, 6), (21.5, -1.6, 0.23, 165, 16)):
        fs = max(8, int(size * k))
        layer = Image.new("RGBA", (fs * 2, fs * 2), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((fs, fs), "♪", font=ImageFont.truetype("C:/Windows/Fonts/seguisym.ttf", fs),
                                   fill=(*NOTE, a), anchor="mm")
        layer = layer.rotate(rot, resample=Image.BICUBIC)
        img.alpha_composite(layer, (int(off + gx * cell - fs), int(off + gy * cell - fs + fs * 0.5)))


def make(size: int = 256, radius: float = 0.22, scale: float = 0.84) -> Image.Image:
    """radius：圆角占边长的比例（0 = 方形）；scale：小人占边长的比例。"""
    # 底板：紫 → 靛蓝的圆角方块
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size))
    gp = grad.load()
    for y in range(size):
        for x in range(size):
            u = (x * 0.45 + (size - y) * 0.55) / size
            gp[x, y] = (int(124 + (79 - 124) * u), int(58 + (110 - 58) * u), int(237 + (245 - 237) * u), 255)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius), fill=255)
    bg.paste(grad, (0, 0), mask)
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))           # 左上角一点高光
    ImageDraw.Draw(hl).ellipse([-size * 0.3, -size * 0.6, size * 0.9, size * 0.38], fill=(255, 255, 255, 34))
    bg = Image.alpha_composite(bg, Image.composite(hl, Image.new("RGBA", (size, size), (0, 0, 0, 0)), mask))
    sp = sprite().resize((int(size * scale), int(size * scale)), Image.NEAREST)
    off = (size - sp.width) // 2
    shadow = Image.new("RGBA", sp.size, (0, 0, 0, 0))
    shadow.putalpha(sp.getchannel("A").point(lambda v: 70 if v else 0))
    bg.alpha_composite(shadow, (off + size // 64, off + size // 40))
    bg.alpha_composite(sp, (off, off))
    hum_notes(bg, sp.width / 32, off)
    return bg


def main() -> None:
    big = make(256)
    big.save(HERE / "icon.png")
    make(96).save(HERE.parent / "web" / "ui" / "icon.png")       # 网页的 favicon
    # 头像用：1080 方图、不留圆角，小人缩小一点，抖音裁成圆形时音符不会被切掉
    make(1080, radius=0, scale=0.7).convert("RGB").save(HERE / "avatar.png")
    # 小尺寸直接用像素格子画，避免缩小后发糊
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [make(s) if s >= 48 else make(s * 8).resize((s, s), Image.LANCZOS) for s in sizes]
    imgs[-1].save(HERE / "icon.ico", sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    print(HERE / "icon.ico")


if __name__ == "__main__":
    main()
