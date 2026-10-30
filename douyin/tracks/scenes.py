"""开头 / 结尾小剧场共用的道具和画法：夜空和半月、高楼、办公桌、显示器、台灯、手机、老虎扭蛋机、来电卡片、对话气泡、
餐桌和红烧肉、网易云小窗……都是 PIL 直接画（像素风小人 + 简洁的扁平道具），不用外部图片。

坐标都是 1920×1080 画面上的像素。小人用 clawd_anim（男生、女生、老板等）。
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import clawd_anim as ca

FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
FONT = r"C:\Windows\Fonts\msyh.ttc"
NIGHT_TOP, NIGHT_BOT = (10, 14, 34), (32, 36, 70)
MOON = (250, 240, 205)
BOSS = ca.recolor((128, 132, 146), scarf=(150, 30, 40))      # 老板：灰色 + 红领带（围巾画成领带的位置）


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def seg(t: float, a: float, b: float) -> float:
    """t 在 [a, b] 里的进度 0~1（带缓动）。"""
    return ease((t - a) / max(b - a, 1e-6))


# ---------------------------------------------------------------- 天空 / 月亮
def sky(w: int, h: int, top=NIGHT_TOP, bot=NIGHT_BOT) -> Image.Image:
    g = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / max(h - 1, 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)))
    return g.resize((w, h))


def stars(im: Image.Image, t: float, n: int = 90, seed: int = 4, y_max: float | None = None, dy: float = 0) -> None:
    rnd = random.Random(seed)
    d = ImageDraw.Draw(im, "RGBA")
    for _ in range(n):
        x, y = rnd.random() * im.width, rnd.random() * (y_max or im.height) + dy
        a = int(120 + 120 * (0.5 + 0.5 * math.sin(t * (1 + rnd.random() * 2) + rnd.random() * 6)))
        r = 1 + (rnd.random() > 0.85)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 250, 230, a))


def half_moon(im: Image.Image, cx: float, cy: float, r: float, glow: bool = True) -> None:
    """半月（上弦月：右半边亮）+ 一圈柔光。"""
    if glow:
        g = Image.new("L", (int(r * 6), int(r * 6)), 0)
        ImageDraw.Draw(g).ellipse([r * 1.6, r * 1.6, r * 4.4, r * 4.4], fill=90)
        g = g.filter(ImageFilter.GaussianBlur(r * 0.6))
        im.paste((255, 240, 200), (int(cx - r * 3), int(cy - r * 3)), g)
    d = ImageDraw.Draw(im)
    d.pieslice([cx - r, cy - r, cx + r, cy + r], -90, 90, fill=MOON)
    for k in range(3):                                         # 几个浅色环形山
        ox, oy, rr = [(0.35, -0.3, 0.12), (0.55, 0.25, 0.09), (0.2, 0.45, 0.07)][k]
        d.ellipse([cx + ox * r - rr * r, cy + oy * r - rr * r, cx + ox * r + rr * r, cy + oy * r + rr * r],
                  fill=(232, 222, 186))


def skyline(im: Image.Image, base_y: float, seed: int = 7, x0: float = 0, x1: float | None = None,
            col=(18, 22, 44), lit=(255, 210, 120), scale: float = 1.0) -> None:
    rnd = random.Random(seed)
    d = ImageDraw.Draw(im)
    x, x1 = x0, x1 if x1 is not None else im.width
    while x < x1:
        bw = rnd.randint(50, 130) * scale
        bh = rnd.randint(80, 300) * scale
        d.rectangle([x, base_y - bh, x + bw, base_y], fill=col)
        for wy in range(int(base_y - bh + 12 * scale), int(base_y - 10 * scale), max(1, int(18 * scale))):
            for wx in range(int(x + 8 * scale), int(x + bw - 8 * scale), max(1, int(16 * scale))):
                if rnd.random() < 0.28:
                    d.rectangle([wx, wy, wx + 6 * scale, wy + 8 * scale], fill=lit)
        x += bw + rnd.randint(4, 20) * scale


# ---------------------------------------------------------------- 办公室道具
def desk(d: ImageDraw.ImageDraw, x0, x1, top, h=60, col=(118, 84, 62)) -> None:
    d.rectangle([x0, top, x1, top + 16], fill=(146, 106, 78))
    d.rectangle([x0 + 10, top + 16, x1 - 10, top + h], fill=col)
    d.rectangle([x0 + 24, top + h, x0 + 44, top + h + 170], fill=(90, 64, 48))
    d.rectangle([x1 - 44, top + h, x1 - 24, top + h + 170], fill=(90, 64, 48))


def monitor(im: Image.Image, x0, y0, w, h, t: float, on: float = 1.0) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 12, fill=(30, 32, 40))
    sc = tuple(int(c * (0.25 + 0.75 * on)) for c in (52, 74, 120))
    d.rectangle([x0 + 12, y0 + 12, x0 + w - 12, y0 + h - 12], fill=sc)
    if on > 0.05:                                              # 屏幕上滚动的评论列表
        for k in range(7):
            y = y0 + 26 + ((k * 34 - t * 22) % (h - 50))
            ww = (0.45 + 0.4 * ((k * 37) % 10) / 10) * (w - 60)
            d.ellipse([x0 + 24, y, x0 + 40, y + 16], fill=(200, 210, 230, int(160 * on)))
            d.rectangle([x0 + 50, y + 2, x0 + 50 + ww, y + 8], fill=(220, 228, 245, int(170 * on)))
            d.rectangle([x0 + 50, y + 12, x0 + 50 + ww * 0.6, y + 16], fill=(160, 175, 205, int(140 * on)))
        d.rectangle([x0 + 12, y0 + 12, x0 + w - 12, y0 + 40], fill=(198, 30, 38, int(220 * on)))
        d.text((x0 + 26, y0 + 26), "网易云评论", font=font(16), fill=(255, 255, 255, int(255 * on)), anchor="lm")
        glow = Image.new("L", im.size, 0)
        ImageDraw.Draw(glow).ellipse([x0 - 60, y0 - 40, x0 + w + 60, y0 + h + 120], fill=int(60 * on))
        im.paste((120, 150, 220), (0, 0), glow.filter(ImageFilter.GaussianBlur(40)))
    d.rectangle([x0 + w / 2 - 14, y0 + h, x0 + w / 2 + 14, y0 + h + 40], fill=(40, 42, 52))
    d.rectangle([x0 + w / 2 - 60, y0 + h + 40, x0 + w / 2 + 60, y0 + h + 50], fill=(40, 42, 52))


def lamp(im: Image.Image, x, desk_top, on: float = 1.0) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    if on > 0.02:
        g = Image.new("L", im.size, 0)
        ImageDraw.Draw(g).polygon([(x + 40, desk_top - 200), (x - 140, desk_top + 10), (x + 260, desk_top + 10)],
                                   fill=int(70 * on))
        im.paste((255, 214, 140), (0, 0), g.filter(ImageFilter.GaussianBlur(30)))
    d.rectangle([x - 30, desk_top - 8, x + 30, desk_top], fill=(60, 60, 70))
    d.line([x, desk_top - 8, x + 10, desk_top - 150], fill=(70, 70, 80), width=8)
    d.line([x + 10, desk_top - 150, x + 60, desk_top - 200], fill=(70, 70, 80), width=8)
    d.polygon([(x + 30, desk_top - 230), (x + 110, desk_top - 210), (x + 70, desk_top - 170)], fill=(240, 200, 120))


def gacha(im: Image.Image, cx, base_y, t: float, shake: float = 0.0, s: float = 1.0, lever: float = 0.0,
          drop: float = -1.0) -> None:
    """老虎扭蛋机（女朋友送的）：老虎脸底座（耳朵、眼睛、鼻子、胡须、条纹）+ 投币口 + 正面旋钮 + 出蛋口托盘
    + 玻璃球罩（高光、彩色扭蛋）+ 右侧摇杆（红色圆球）。
    lever：摇杆拉下的程度 0~1；drop：扭蛋从出口掉出来的进度 0~1（<0 不画）。"""
    cx += shake * 4 * math.sin(t * 40)
    d = ImageDraw.Draw(im, "RGBA")
    bw, bh = 110 * s, 84 * s
    top = base_y - bh
    ORANGE, DARK, CREAM = (240, 140, 50), (40, 30, 30), (250, 232, 210)
    # 底座 + 脚
    d.rounded_rectangle([cx - bw / 2 - 4 * s, base_y - 8 * s, cx + bw / 2 + 4 * s, base_y], 4 * s, fill=(170, 90, 36))
    d.rounded_rectangle([cx - bw / 2, top, cx + bw / 2, base_y - 6 * s], 14 * s, fill=ORANGE)
    # 耳朵
    for k in (-1, 1):
        ex = cx + k * bw * 0.34
        d.ellipse([ex - 14 * s, top - 12 * s, ex + 14 * s, top + 14 * s], fill=ORANGE)
        d.ellipse([ex - 7 * s, top - 5 * s, ex + 7 * s, top + 8 * s], fill=(250, 190, 170))
    # 条纹（两侧各三道）
    for k in (-1, 1):
        for j, yy in enumerate((0.22, 0.48, 0.72)):
            y0 = top + bh * yy
            d.polygon([(cx + k * bw / 2, y0), (cx + k * (bw / 2 - (20 - j * 4) * s), y0 + 5 * s),
                       (cx + k * bw / 2, y0 + 11 * s)], fill=DARK)
    # 脸：白色口鼻区、眼睛（亮点）、鼻子、嘴、胡须
    d.ellipse([cx - 30 * s, top + 34 * s, cx + 30 * s, top + 70 * s], fill=CREAM)
    for k in (-1, 1):
        d.ellipse([cx + k * 22 * s - 7 * s, top + 16 * s, cx + k * 22 * s + 7 * s, top + 30 * s], fill=DARK)
        d.ellipse([cx + k * 22 * s - 3 * s, top + 18 * s, cx + k * 22 * s + 1 * s, top + 22 * s], fill=(255, 255, 255))
        for w_ in (-1, 1):
            d.line([cx + k * 26 * s, top + 50 * s + w_ * 4 * s, cx + k * 46 * s, top + 46 * s + w_ * 7 * s],
                   fill=DARK, width=max(1, int(2 * s)))
    d.polygon([(cx - 7 * s, top + 38 * s), (cx + 7 * s, top + 38 * s), (cx, top + 46 * s)], fill=(220, 90, 100))
    d.arc([cx - 10 * s, top + 42 * s, cx, top + 54 * s], 0, 180, fill=DARK, width=max(1, int(2 * s)))
    d.arc([cx, top + 42 * s, cx + 10 * s, top + 54 * s], 0, 180, fill=DARK, width=max(1, int(2 * s)))
    # 投币口（左上）和正面旋钮（拉杆时转动）
    d.rounded_rectangle([cx - bw / 2 + 8 * s, top + 8 * s, cx - bw / 2 + 24 * s, top + 30 * s], 3 * s, fill=(200, 110, 40))
    d.rectangle([cx - bw / 2 + 14 * s, top + 12 * s, cx - bw / 2 + 18 * s, top + 26 * s], fill=DARK)
    # 出蛋口托盘（底部中间）
    d.rounded_rectangle([cx - 16 * s, base_y - 24 * s, cx + 16 * s, base_y - 8 * s], 5 * s, fill=(120, 60, 30))
    # 玻璃球罩
    r = 58 * s
    gy = top - r + 10 * s
    d.rectangle([cx - 36 * s, top - 6 * s, cx + 36 * s, top + 2 * s], fill=(200, 110, 40))
    d.ellipse([cx - r, gy - r, cx + r, gy + r], fill=(220, 236, 255, 80), outline=(240, 248, 255, 230), width=3)
    rnd = random.Random(3)
    for k in range(11):
        a = rnd.random() * 2 * math.pi
        rr = rnd.random() * (r - 18 * s)
        px = cx + rr * math.cos(a) + shake * 3 * math.sin(t * 30 + k)
        py = gy + abs(rr * math.sin(a)) * 0.8 + 8 * s
        col = [(240, 90, 110), (90, 170, 240), (250, 210, 80), (120, 210, 140), (190, 130, 230)][k % 5]
        d.ellipse([px - 12 * s, py - 12 * s, px + 12 * s, py + 12 * s], fill=col)
        d.chord([px - 12 * s, py - 12 * s, px + 12 * s, py + 12 * s], 180, 360, fill=(250, 250, 250))
    d.arc([cx - r + 12 * s, gy - r + 12 * s, cx + r - 12 * s, gy + r - 12 * s], 200, 250, fill=(255, 255, 255, 230),
          width=max(2, int(5 * s)))                            # 玻璃高光
    d.ellipse([cx - r * 0.55, gy - r * 0.7, cx - r * 0.4, gy - r * 0.55], fill=(255, 255, 255, 200))
    # 摇杆：右侧转轴，向上斜立，拉下时往前下方转
    px0, py0 = cx + bw / 2 + 4 * s, top + bh * 0.45
    d.ellipse([px0 - 9 * s, py0 - 9 * s, px0 + 9 * s, py0 + 9 * s], fill=(150, 150, 160))
    ang = math.radians(-70 + 95 * lever)                      # -70°：竖着；+25°：拉到底
    L = 78 * s
    ex, ey = px0 + L * math.cos(ang) * 0.55, py0 + L * math.sin(ang)
    d.line([px0, py0, ex, ey], fill=(190, 190, 200), width=max(3, int(7 * s)))
    d.ellipse([ex - 13 * s, ey - 13 * s, ex + 13 * s, ey + 13 * s], fill=(226, 50, 60))
    d.ellipse([ex - 6 * s, ey - 8 * s, ex - 1 * s, ey - 3 * s], fill=(255, 200, 200))
    # 掉出来的扭蛋
    if drop >= 0:
        u = min(drop, 1.0)
        bx = cx + 30 * s * u
        by = base_y - 30 * s - math.sin(min(u * 1.6, 1) * math.pi) * 26 * s + 18 * s * u
        d.ellipse([bx - 13 * s, by - 13 * s, bx + 13 * s, by + 13 * s], fill=(240, 90, 110))
        d.chord([bx - 13 * s, by - 13 * s, bx + 13 * s, by + 13 * s], 180, 360, fill=(250, 250, 250))
    return (ex, ey)


def phone(im: Image.Image, cx, cy, ang: float = 0.0, ring: float = 0.0, t: float = 0.0, screen=(60, 120, 200),
          s: float = 1.0) -> None:
    """手机（可以旋转）；ring > 0 时震动并冒出声波弧线。"""
    w, h = int(40 * s), int(72 * s)
    p = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.rounded_rectangle([4, 4, w + 4, h + 4], 8, fill=(30, 30, 38))
    d.rounded_rectangle([8, 12, w, h - 4], 4, fill=screen)
    p = p.rotate(ang, Image.BICUBIC, expand=True)
    jx = ring * 3 * math.sin(t * 60)
    ca._put(im, p, (cx - p.width / 2 + jx, cy - p.height / 2))
    if ring > 0.05:
        d2 = ImageDraw.Draw(im, "RGBA")
        for k in range(3):
            u = (t * 1.6 + k / 3) % 1
            r = 30 + u * 50
            d2.arc([cx - r, cy - r, cx + r, cy + r], -60, 60, fill=(255, 255, 255, int(200 * (1 - u) * ring)), width=4)
            d2.arc([cx - r, cy - r, cx + r, cy + r], 120, 240, fill=(255, 255, 255, int(200 * (1 - u) * ring)), width=4)


def avatar(look, pose, size: int = 110) -> Image.Image:
    """圆形头像：小人的上半身。"""
    k = 4 if size < 140 else 5
    spr, (fx, fy) = ca.render(pose, k, look)
    box = Image.new("RGBA", (size, size), (250, 244, 236, 255))
    body_mid = (ca.OY + ca.BH / 2) * k * pose.squash          # 身体（脸）的中心放在圆的中心偏下一点
    ca._put(box, spr, (size / 2 - fx, size / 2 + 10 - body_mid))
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
    box.putalpha(m)
    return box


def call_card(im: Image.Image, x, y, name: str, sub: str, look, pose, a: float = 1.0, accent=(80, 200, 120),
              ended: bool = False, heart: bool = False) -> None:
    """来电卡片：圆形头像（通话的人）+ 名字 + 状态 + 接听/挂断键。"""
    if a <= 0.01:
        return
    w, h = 470, 150
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 28, fill=(28, 30, 40, 235), outline=(255, 255, 255, 40), width=2)
    card.alpha_composite(avatar(look, pose, 110), (20, 20))
    d.text((150, 50), name, font=font(34), fill=(255, 255, 255), anchor="lm")
    if heart:                                                  # 名字后面一颗小爱心（字体里没有 ❤）
        nx = 150 + d.textlength(name, font=font(34)) + 12
        card.alpha_composite(ca._pixel(ca.HEART_SHAPE, ca.HEART, 5), (int(nx), 36))
    d.text((150, 98), sub, font=font(22, False), fill=(190, 196, 210), anchor="lm")
    col = (220, 60, 60) if ended else accent
    d.ellipse([w - 90, h / 2 - 32, w - 26, h / 2 + 32], fill=col)
    d.text((w - 58, h / 2), "✆", font=ImageFont.truetype(r"C:\Windows\Fonts\seguisym.ttf", 34), fill=(255, 255, 255),
           anchor="mm")
    ca._put(im, ca._fade(card, a), (x, y))


def bubble(im: Image.Image, x, y, text: str, size=34, a=1.0, col=(255, 255, 255), fg=(40, 30, 30), jag=False,
           tail=(0, 1), max_w=560) -> tuple[int, int]:
    """对话气泡（左上角在 x, y）；jag=True 是锯齿形的（生气）；tail 是尾巴朝向。返回气泡大小。"""
    f = font(size)
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lines, cur = [], ""
    for ch in text:
        if d0.textlength(cur + ch, font=f) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    lines.append(cur)
    tw = max(d0.textlength(ln, font=f) for ln in lines)
    w, h = int(tw + 56), int(len(lines) * size * 1.35 + 36)
    b = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    if jag:
        pts = []
        n = 18
        for k in range(n):
            ang = k / n * 2 * math.pi
            r = 1.0 if k % 2 == 0 else 0.86
            pts.append((20 + w / 2 + r * (w / 2 + 10) * math.cos(ang), 20 + h / 2 + r * (h / 2 + 10) * math.sin(ang)))
        d.polygon(pts, fill=col)
    else:
        d.rounded_rectangle([20, 20, 20 + w, 20 + h], 26, fill=col)
        tx, ty = 20 + w * (0.2 if tail[0] <= 0 else 0.8), 20 + h
        d.polygon([(tx - 14, ty - 2), (tx + 14, ty - 2), (tx + tail[0] * 18, ty + 24)], fill=col)
    for k, ln in enumerate(lines):
        d.text((20 + 28, 20 + 18 + k * size * 1.35), ln, font=f, fill=fg)
    ca._put(im, ca._fade(b, a), (x - 20, y - 20))
    return w, h


def comment_card(text: str, size: int = 50, max_w: int = 1100) -> Image.Image:
    """大字评论卡片（开头浮现的那条）：深色半透明底、引号、白字、「—— 网易云评论」。"""
    f = font(size)
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lines, cur = [], ""
    for ch in text:
        if d0.textlength(cur + ch, font=f) > max_w and ch not in "，。！？、 ":
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    lines.append(cur)
    tw = max(d0.textlength(ln, font=f) for ln in lines)
    w, h = int(tw + 140), int(len(lines) * size * 1.4 + 130)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 30, fill=(16, 18, 30, 200), outline=(255, 255, 255, 50), width=2)
    d.text((40, 28), "“", font=font(90), fill=(198, 30, 38))
    for k, ln in enumerate(lines):
        d.text((90, 60 + k * size * 1.4), ln, font=f, fill=(250, 246, 240))
    d.text((w - 40, h - 36), "—— 网易云评论", font=font(22, False), fill=(190, 186, 196), anchor="rm")
    return im


# ---------------------------------------------------------------- 家里道具
def dining(d: ImageDraw.ImageDraw, x0, x1, top) -> None:
    d.rectangle([x0, top, x1, top + 18], fill=(196, 140, 96))
    d.rectangle([x0 + 20, top + 18, x0 + 40, top + 200], fill=(150, 104, 70))
    d.rectangle([x1 - 40, top + 18, x1 - 20, top + 200], fill=(150, 104, 70))


def braised_pork(im: Image.Image, cx, cy, t: float, s: float = 1.0) -> None:
    """一盘红烧肉，冒着热气。"""
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse([cx - 80 * s, cy - 18 * s, cx + 80 * s, cy + 22 * s], fill=(245, 245, 240))
    d.ellipse([cx - 64 * s, cy - 12 * s, cx + 64 * s, cy + 14 * s], fill=(150, 60, 30))
    rnd = random.Random(5)
    for _ in range(9):
        px, py = cx + (rnd.random() - 0.5) * 100 * s, cy + (rnd.random() - 0.6) * 18 * s - 8 * s
        d.rounded_rectangle([px - 13 * s, py - 10 * s, px + 13 * s, py + 10 * s], 4, fill=(176, 72, 34))
        d.rectangle([px - 13 * s, py - 10 * s, px + 13 * s, py - 5 * s], fill=(240, 200, 160))
    for k in range(3):                                         # 热气
        u = (t * 0.5 + k / 3) % 1
        x = cx + (k - 1) * 30 * s + 8 * math.sin(t * 2 + k)
        y = cy - 30 * s - u * 70 * s
        d.ellipse([x - 8 * s, y - 8 * s, x + 8 * s, y + 8 * s], fill=(255, 255, 255, int(120 * (1 - u))))


def rice(d, cx, cy, s=1.0):
    d.ellipse([cx - 34 * s, cy - 6 * s, cx + 34 * s, cy + 30 * s], fill=(90, 120, 180))
    d.ellipse([cx - 30 * s, cy - 18 * s, cx + 30 * s, cy + 8 * s], fill=(252, 252, 248))


def mini_player(im: Image.Image, x, y, cover: Image.Image, title: str, artist: str, t: float, a: float = 1.0) -> None:
    """网易云播放的小窗：封面（转动的唱片）+ 歌名歌手 + 进度条。"""
    if a <= 0.01:
        return
    w, h = 460, 150
    p = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 24, fill=(30, 30, 36, 240), outline=(255, 255, 255, 50), width=2)
    disc = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse([0, 0, 119, 119], fill=(20, 20, 24))
    c = cover.convert("RGBA").resize((76, 76), Image.LANCZOS)
    m = Image.new("L", (76, 76), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 75, 75], fill=255)
    c.putalpha(m)
    disc.alpha_composite(c, (22, 22))
    disc = disc.rotate(-t * 40, Image.BICUBIC)
    p.alpha_composite(disc, (16, 15))
    d.ellipse([w - 70, 20, w - 30, 60], fill=(198, 30, 38))
    d.polygon([(w - 56, 30), (w - 56, 50), (w - 40, 40)], fill=(255, 255, 255))
    d.text((150, 44), title, font=font(30), fill=(255, 255, 255), anchor="lm")
    d.text((150, 84), artist, font=font(22, False), fill=(190, 190, 200), anchor="lm")
    d.rounded_rectangle([150, 112, w - 30, 118], 3, fill=(80, 80, 90))
    d.rounded_rectangle([150, 112, 150 + (w - 180) * ((t * 0.04) % 1), 118], 3, fill=(198, 30, 38))
    ca._put(im, ca._fade(p, a), (x, y))


def person(im, look, pose, x, floor, scale):
    spr, (fx, fy) = ca.render(pose, scale, look)
    sh = ca.shadow(pose, scale)
    shade = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    shade.putalpha(sh)
    ca._put(im, shade, (x - sh.width / 2, floor - sh.height / 2))
    ca._put(im, spr, (x - fx, floor - fy))
    ca.draw_fx(im, pose, (x, floor), scale)
