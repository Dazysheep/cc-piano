"""男生小人读完评论后，头顶「想象云朵」里浮现的画面。

每个画面是一个函数：时间（秒，从云朵展开算起）→ RGBA 图（SIZE 大小，背景透明）。画面里只有东西本身（人物、太阳、
窗户……），没有底色，所以叠在音轨上时音轨从空隙里还看得见；每个东西外面描一圈深色边，压在波形上也看得清。
人物都用 clawd_anim 的小人：男生、女生，以及从男生改出来的配角（爸爸戴帽子、妈妈围围巾、朋友换颜色）。

评论卡片里写 "vision": "<画面名>" 就会用到。预览：python tracks/visions.py --export → assets/clawd/visions/
"""
import argparse
import math
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import clawd_anim as ca

SIZE = (360, 210)
S = 2                                   # 画面里小人的像素格大小
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
SUN, SUN_HI = (255, 176, 92), (255, 214, 140)
MOON = (246, 236, 200)
GROUND = (120, 92, 84)
GLASS, HONEY = (230, 236, 246), (238, 170, 60)
LEAF, PETAL, PETAL2 = (110, 176, 110), (246, 140, 170), (255, 220, 120)
CLOUD, RAIN = (226, 230, 240), (140, 180, 236)
WOOD, PAPER = (150, 104, 76), (250, 247, 240)
PHONE = (60, 64, 80)


# ---------------------------------------------------------------- 小工具
def _new() -> Image.Image:
    return Image.new("RGBA", SIZE, (0, 0, 0, 0))


def person(im, look, pose, x, floor, scale=S):
    """在 (x, floor) 站一个小人（x 是脚底中心）。"""
    spr, (fx, fy) = ca.render(pose, scale, look)
    ca._put(im, spr, (x - fx, floor - fy))
    ca.draw_fx(im, pose, (x, floor), scale)


def heart(im, x, y, scale=3, a=1.0, col=ca.HEART):
    ca._put(im, ca._fade(ca._pixel(ca.HEART_SHAPE, col, scale), a), (x, y))


def spark(im, x, y, scale=2, a=1.0):
    ca._put(im, ca._fade(ca._pixel(ca.SPARK_SHAPE, ca.SPARK, scale), a), (x, y))


def ground(d, y, x0=20, x1=340):
    d.rectangle([x0, y, x1, y + 3], fill=GROUND)


def sun(d, cx, cy, r, rays=True, t=0.0):
    if rays:
        for k in range(10):
            ang = k / 10 * 2 * math.pi + t * 0.4
            r0, r1 = r + 6, r + 14 + 3 * math.sin(t * 3 + k)
            d.line([cx + r0 * math.cos(ang), cy + r0 * math.sin(ang), cx + r1 * math.cos(ang),
                    cy + r1 * math.sin(ang)], fill=SUN_HI, width=3)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SUN)


def puff(d, cx, cy, w, col=CLOUD):
    """一朵小云（实心，画面里的云，不是外面的想象框）。"""
    for dx, dy, r in ((-0.3, 0.1, 0.22), (0, -0.1, 0.3), (0.3, 0.1, 0.22), (0.12, 0.15, 0.22), (-0.12, 0.15, 0.2)):
        d.ellipse([cx + dx * w - r * w, cy + dy * w - r * w, cx + dx * w + r * w, cy + dy * w + r * w], fill=col)


def rain(d, t, x0, x1, y0, y1, n=14, seed=3):
    for k in range(n):
        x = x0 + ((k * 97 + seed * 31) % 1000) / 1000 * (x1 - x0)
        y = y0 + ((t * 260 + k * 53) % (y1 - y0))
        d.line([x, y, x - 3, y + 10], fill=RAIN, width=2)


def text(d, xy, s, size, fill, anchor="mm"):
    d.text(xy, s, font=ImageFont.truetype(FONT, size), fill=fill, anchor=anchor)


def flower(d, x, y, k=1.0, col=PETAL):
    d.line([x, y, x, y - 18 * k], fill=LEAF, width=3)
    d.ellipse([x - 9, y - 12 * k, x - 1, y - 6 * k], fill=LEAF)
    cy = y - 22 * k
    for a in range(5):
        ang = a / 5 * 2 * math.pi
        px, py = x + 6 * k * math.cos(ang), cy + 6 * k * math.sin(ang)
        d.ellipse([px - 4 * k, py - 4 * k, px + 4 * k, py + 4 * k], fill=col)
    d.ellipse([x - 3 * k, cy - 3 * k, x + 3 * k, cy + 3 * k], fill=PETAL2)


def outline(im: Image.Image, col=(28, 20, 24), px: int = 2) -> Image.Image:
    """给画面里的东西描一圈深色边（不加底色），压在音轨波形上也看得清。"""
    a = im.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    ring = a.filter(ImageFilter.MaxFilter(px * 2 + 1))
    base = Image.new("RGBA", im.size, (*col, 0))
    base.putalpha(ring.point(lambda v: int(v * 0.85)))
    base.alpha_composite(im)
    return base


# ---------------------------------------------------------------- 画面
def sunset_walk(t):
    """夕阳下牵着手走。"""
    im = _new()
    d = ImageDraw.Draw(im)
    sun(d, 250, 120, 42, rays=False)
    d.rectangle([150, 120, 350, 170], fill=(0, 0, 0, 0))
    ground(d, 170)
    off = (t * 14) % 40
    walk = ca.walk_happy(t)
    person(im, ca.MALE, replace(walk, eyes="happy", arm_r="out", arm_l="down"), 110 + off * 0.2, 170)
    person(im, ca.FEMALE, replace(ca.walk_happy(t + 0.25), arm_l="out", arm_r="down"), 170 + off * 0.2, 170)
    heart(im, 132 + 10 * math.sin(t * 2), 40 - (t * 20) % 30, 3, 0.9)
    return im


def hug(t):
    """紧紧抱在一起。"""
    im = _new()
    ground(ImageDraw.Draw(im), 175, 80, 280)
    k = math.sin(t * 2.4)
    person(im, ca.MALE, ca.Pose(lean=8 + 2 * k, eyes="closed", mouth="smile", arm_r="out", blush=True), 158, 175)
    person(im, ca.FEMALE, ca.Pose(lean=-8 - 2 * k, eyes="closed", mouth="smile", arm_l="out", turn=-1), 212, 175)
    for i in range(3):
        u = (t * 0.6 + i / 3) % 1
        heart(im, 170 + 40 * math.sin(u * 6 + i), 80 - u * 60, 3, 1 - u)
    return im


def together(t):
    """终于在一起：两个人爱心眼，冒爱心。"""
    im = _new()
    ground(ImageDraw.Draw(im), 175, 60, 300)
    person(im, ca.MALE, ca.love(t), 140, 175)
    person(im, ca.FEMALE, replace(ca.love(t + 0.4), turn=-1), 225, 175)
    heart(im, 168, 22 + 4 * math.sin(t * 3), 5)
    return im


def farewell(t):
    """告别：她拖着行李箱走远，他在原地挥手。"""
    im = _new()
    d = ImageDraw.Draw(im)
    ground(d, 175)
    u = min(t / 3.0, 1)
    x = 220 + 90 * u
    person(im, ca.FEMALE, replace(ca.walk(t), turn=1, eyes="closed"), x, 175, 2)
    d.rectangle([x + 34, 140, x + 54, 172], fill=(120, 140, 190))           # 行李箱
    d.rectangle([x + 40, 132, x + 48, 140], outline=(80, 90, 120), width=2)
    person(im, ca.MALE, ca.Pose(arm_r="wave" if int(t / 0.3) % 2 else "up", eyes="sad", mouth="smile"), 100, 175)
    return im


def honey_jar(t):
    """隔着一罐蜂蜜看喜欢的人的后脑勺。"""
    im = _new()
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([200, 48, 320, 182], 18, fill=(*HONEY, 150), outline=GLASS, width=4)
    d.rectangle([214, 34, 306, 50], fill=(196, 140, 90))
    person(im, ca.FEMALE, ca.Pose(turn=-1, eyes="closed", lean=3 * math.sin(t * 1.5)), 262, 170, 2)
    glow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([206, 54, 314, 176], 14, fill=(*HONEY, 90))
    im.alpha_composite(glow)
    person(im, ca.MALE, ca.Pose(eyes="look_r", mouth="smile", blush=True, lean=-3), 100, 182)
    return im


def no_sky(t):
    """喜欢你以后，好久没抬头看天：头顶阳光和云，他低着头看不到。"""
    im = _new()
    d = ImageDraw.Draw(im)
    sun(d, 80, 50, 22, t=t)
    puff(d, 200 + 10 * math.sin(t * 0.6), 40, 90)
    puff(d, 300, 62, 60)
    ground(d, 180, 100, 260)
    person(im, ca.MALE, ca.Pose(eyes="down", mouth="frown", squash=0.95, lean=-2), 180, 180)
    return im


def father_back(t):
    """爸爸的背影：戴帽子的爸爸往远处走，他在后面看着。"""
    im = _new()
    ground(ImageDraw.Draw(im), 180)
    u = min(t / 4, 1)
    person(im, ca.DAD, replace(ca.walk(t * 0.6), turn=1, lean=2), 240 + 40 * u, 180, 3)
    person(im, ca.MALE, ca.Pose(eyes="sad", mouth="closed", lean=-2, fx=[("tear", t / 1.4)]), 90, 180)
    heart(im, 150, 70 - 10 * math.sin(t * 2), 3, 0.8)
    return im


def gift_phone(t):
    """打暑假工攒钱，给爸爸换了新手机。"""
    im = _new()
    d = ImageDraw.Draw(im)
    ground(d, 180, 40, 320)
    person(im, ca.MALE, ca.Pose(arm_r="out", eyes="happy", mouth="grin"), 110, 180)
    px = 160 + 6 * math.sin(t * 3)
    d.rounded_rectangle([px, 118, px + 18, 148], 3, fill=PHONE, outline=(200, 210, 230), width=2)
    d.rectangle([px + 3, 122, px + 15, 142], fill=(120, 190, 240))
    person(im, ca.DAD, replace(ca.happy(t), turn=-1), 250, 180, 3)
    spark(im, 220, 30, 3, 0.5 + 0.5 * math.sin(t * 4))
    return im


def dad_rain(t):
    """爸爸在外面累死累活：雨里背着包往前走，满头汗。"""
    im = _new()
    d = ImageDraw.Draw(im)
    puff(d, 180, 28, 150, (170, 176, 196))
    rain(d, t, 40, 320, 40, 170)
    ground(d, 182)
    person(im, ca.DAD, ca.Pose(lean=10, legs="step0" if int(t / 0.3) % 2 else "step1", eyes="down", squash=0.94,
                               fx=[("sweat", t / 1.0)]), 190, 182, 3)
    d.rectangle([138, 118, 160, 150], fill=(96, 84, 74))                    # 背包
    return im


def exam_countdown(t):
    """高考倒计时：日历上的数字，他握拳给自己打气。"""
    im = _new()
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([200, 40, 312, 150], 8, fill=PAPER, outline=(200, 194, 184), width=3)
    d.rectangle([200, 40, 312, 70], fill=(226, 84, 84))
    text(d, (256, 56), "高考", 18, (255, 255, 255))
    text(d, (256, 108), "24", 44, (60, 50, 50))
    text(d, (256, 138), "天", 14, (120, 110, 110))
    ground(d, 182, 30, 330)
    person(im, ca.MALE, ca.hope(t), 110, 182)
    return im


def sunrise(t):
    """慢慢好起来：太阳升起来，小花开了，他蹦起来。"""
    im = _new()
    d = ImageDraw.Draw(im)
    u = min(t / 2.5, 1)
    sun(d, 270, 150 - 70 * u, 30, t=t)
    d.rectangle([0, 160, 360, 210], fill=(0, 0, 0, 0))
    ground(d, 160)
    for i, x in enumerate((60, 200, 320)):
        flower(d, x, 160, min(1, u * 1.3 - i * 0.1) if u > i * 0.1 else 0.01, PETAL if i % 2 else PETAL2)
    person(im, ca.MALE, ca.happy(t), 130, 160)
    return im


def reader_smile(t):
    """世界上有个特别幸福的人，她正在读这句话：她捧着纸笑，周围闪光。"""
    im = _new()
    ground(ImageDraw.Draw(im), 180, 80, 280)
    person(im, ca.FEMALE, ca.Pose(arm_l="hold", arm_r="hold", held="paper_open", eyes="happy", mouth="grin",
                                  lean=3 * math.sin(t * 2)), 180, 180, 3)
    for k in range(4):
        u = (t * 0.7 + k / 4) % 1
        spark(im, 70 + k * 70, 30 + 20 * math.sin(k * 2 + t), 3, math.sin(u * math.pi))
    return im


def alone_window(t):
    """深夜一个人：窗外月亮，他抱膝坐着。"""
    im = _new()
    d = ImageDraw.Draw(im)
    d.rectangle([200, 30, 320, 130], outline=WOOD, width=6)
    d.line([260, 30, 260, 130], fill=WOOD, width=4)
    d.line([200, 80, 320, 80], fill=WOOD, width=4)
    d.ellipse([272, 40, 304, 72], fill=MOON)
    d.ellipse([264, 36, 294, 66], fill=(0, 0, 0, 0))
    ground(d, 182, 40, 330)
    person(im, ca.MALE, ca.lonely(t), 120, 182)
    return im


def small_flower(t):
    """小确幸：一朵小花慢慢长出来，他蹲着看。"""
    im = _new()
    d = ImageDraw.Draw(im)
    ground(d, 176, 60, 300)
    u = min(t / 2, 1)
    flower(d, 230, 176, 0.4 + 1.2 * u)
    spark(im, 250, 60, 3, 0.5 + 0.5 * math.sin(t * 3))
    person(im, ca.MALE, ca.Pose(legs="sit", eyes="happy", mouth="smile", blush=True), 140, 176)
    return im


def _photo(w, h, sunset=False) -> Image.Image:
    """一张小合照：白边相纸，里面两个小人并排（sunset=True 时是橙色黄昏底）。"""
    p = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.rectangle([0, 0, w - 1, h - 1], fill=PAPER)
    d.rectangle([4, 4, w - 5, h - 14], fill=(240, 150, 80) if sunset else (150, 196, 236))
    k = 1 if w < 90 else 2
    person(p, ca.MALE, ca.Pose(eyes="happy", mouth="grin", arm_r="out"), w * 0.36, h - 16, k)
    person(p, ca.OLD_FRIEND, ca.Pose(eyes="happy", mouth="grin", arm_l="out", turn=-1), w * 0.64, h - 16, k)
    return p


def photo_flip(t):
    """《最佳损友》：「我记得我向别人炫耀过你。后来你成了我的禁忌。」——举着合照炫耀 → 照片翻过去，背面贴着封条 → 收进口袋。"""
    im = _new()
    ground(ImageDraw.Draw(im), 182, 30, 330)
    flip = min(max((t - 3.2) / 1.2, 0), 1)                  # 0：正面；1：翻到背面
    away = min(max((t - 5.2) / 1.0, 0), 1)                  # 收起来
    for i, x in enumerate((228, 300)):                       # 旁边听他炫耀的两个小人
        look = ca.recolor((170, 160, 190)) if i else ca.recolor((200, 170, 120))
        pose = ca.Pose(eyes="wide" if flip < 0.5 else "look_l", mouth="o" if flip < 0.5 else "closed", turn=-1)
        person(im, look, pose, x, 182)
    proud = flip < 0.5
    boy = ca.Pose(eyes="happy" if proud else "down", mouth="grin" if proud else "closed", arm_r="up" if away < 0.5 else "down",
                  lean=4 * math.sin(t * 3) if proud else 0, fx=[("spark", t / 0.8)] if proud else [])
    person(im, ca.MALE, boy, 120, 182)
    if away < 1:
        pw, ph = 96, 78
        sx = abs(math.cos(flip * math.pi))                    # 翻面：横向压扁再展开
        front = flip < 0.5
        p = _photo(pw, ph) if front else Image.new("RGBA", (pw, ph), PAPER + (255,))
        if not front:                                         # 背面：交叉的封条
            d = ImageDraw.Draw(p)
            d.line([8, 8, pw - 8, ph - 8], fill=(214, 70, 70), width=12)
            d.line([pw - 8, 8, 8, ph - 8], fill=(214, 70, 70), width=12)
        p = p.resize((max(2, int(pw * max(sx, 0.04))), ph), Image.NEAREST)
        k = 1 - 0.7 * away
        p = p.resize((max(2, int(p.width * k)), max(2, int(ph * k))), Image.NEAREST)
        cx, cy = 150 + 10 * away, 70 + 80 * away
        ca._put(im, ca._fade(p, 1 - away), (cx - p.width / 2, cy - p.height / 2))
    return im


def dusk_stuck(t):
    """《最佳损友》：「只是滞留在了某一个黄昏，从此也没能参与对方的日日夜夜。」——两人坐在台阶上看夕阳，定格成一张橙色的照片；
    一个人站起来走出照片，照片外的天空日夜飞快交替，照片里他还坐在黄昏里。"""
    im = _new()
    d = ImageDraw.Draw(im)
    fx0, fy0, fx1, fy1 = 40, 40, 220, 190                    # 那张照片（黄昏）
    d.rectangle([fx0 - 6, fy0 - 6, fx1 + 6, fy1 + 6], fill=PAPER)
    for y in range(fy0, fy1):                                 # 橙色渐变
        k = (y - fy0) / (fy1 - fy0)
        d.line([fx0, y, fx1, y], fill=(int(250 - 30 * k), int(150 - 50 * k), int(80 - 20 * k)))
    d.ellipse([150, 90, 196, 136], fill=SUN_HI)
    d.rectangle([fx0, 150, fx1, fy1], fill=(150, 90, 70))     # 台阶
    leave = min(max((t - 2.4) / 2.2, 0), 1)
    person(im, ca.MALE, ca.Pose(legs="sit", eyes="closed" if leave > 0.3 else "happy", mouth="smile" if leave < 0.3 else "closed",
                                turn=1), 95, 152)
    if leave < 0.08:
        person(im, ca.OLD_FRIEND, ca.Pose(legs="sit", eyes="happy", mouth="smile", turn=1), 150, 152)
    else:                                                     # 站起来，走出照片（往右，走进日夜交替的天空）
        gx = 150 + 170 * min((leave - 0.08) / 0.92, 1)
        person(im, ca.OLD_FRIEND, ca.replace(ca.walk(t), turn=1), gx, 182)
    if leave > 0.2:                                           # 照片外：日月飞快轮转
        ph = (t - 2.8) * 1.6
        ang = ph * 2 * math.pi
        cx, cy = 290 + 50 * math.cos(ang), 90 - 50 * math.sin(ang)
        if math.sin(ang) > -0.2:
            if int(ph) % 2 == 0:
                sun(d, cx, cy, 14, rays=True, t=t)
            else:
                d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=MOON)
                d.ellipse([cx - 6, cy - 18, cx + 18, cy + 8], fill=(0, 0, 0, 0))
        ground(d, 182, 230, 345)
    return im


def eighty_bubble(t):
    """《最佳损友》：「立誓八十岁也要混在一起。转眼间到了今天，竟然和陌生人没什么区别。」——
    先冒出想象泡：两个白眉毛的老 CC 拄拐下棋；泡泡啵地破掉 → 公交站，两个小人各看各的手机，中间隔着一个座位。"""
    im = _new()
    d = ImageDraw.Draw(im)
    pop = 3.4
    if t < pop:
        r = min(t / 0.6, 1)
        cx, cy, rw, rh = 180, 100, 160 * r, 92 * r
        d.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=(250, 246, 240, 70), outline=(255, 255, 255), width=3)
        if r > 0.9:
            d.rectangle([152, 128, 208, 136], fill=WOOD)                       # 棋盘桌
            d.rectangle([160, 120, 200, 128], fill=(230, 200, 140))
            for k in range(4):
                d.ellipse([162 + k * 10, 121, 168 + k * 10, 127], fill=(40, 40, 40) if k % 2 else (250, 250, 250))
            for x, turn in ((120, 1), (240, -1)):
                person(im, ca.ELDER, ca.Pose(eyes="happy", mouth="grin", turn=turn, lean=3 * math.sin(t * 2 + x),
                                             legs="sit"), x, 140)
                d.line([x + 22 * turn, 104, x + 26 * turn, 142], fill=WOOD, width=3)   # 拐杖
    elif t < pop + 0.5:                                        # 啵：几颗小火花
        u = (t - pop) / 0.5
        for k in range(6):
            ang = k / 6 * 2 * math.pi
            spark(im, 176 + 90 * u * math.cos(ang), 96 + 60 * u * math.sin(ang), 2, 1 - u)
    else:                                                      # 公交站
        d.rectangle([60, 60, 300, 70], fill=(90, 110, 140))                    # 站台顶棚
        d.rectangle([66, 70, 72, 182], fill=(90, 110, 140))
        d.rectangle([290, 70, 296, 182], fill=(90, 110, 140))
        d.rectangle([150, 84, 210, 110], fill=(230, 236, 246))                 # 站牌
        text(d, (180, 97), "公交站", 13, (60, 70, 90))
        d.rectangle([84, 150, 278, 156], fill=WOOD)                            # 长椅
        ground(d, 182, 40, 330)
        for x, turn in ((110, 1), (250, -1)):
            person(im, ca.MALE if x < 180 else ca.OLD_FRIEND, ca.Pose(legs="sit", eyes="down", arm_r="hold", turn=turn), x, 152)
            d.rectangle([x - 4 + 10 * turn, 126, x + 4 + 10 * turn, 138], fill=PHONE)
    return im


def pillow_fight(t):
    """《最佳损友》：「互损不会翻脸……迷茫的时候拉一把，难过的时候抱一下。」——互扔枕头做鬼脸 → 一个摔倒，另一个伸手拉起来 → 抱一下。"""
    im = _new()
    d = ImageDraw.Draw(im)
    ground(d, 180, 40, 320)
    if t < 2.8:                                                # 互扔枕头
        u = (t / 0.7) % 2
        x = 120 + 120 * (u if u < 1 else 2 - u)
        y = 120 - 40 * math.sin((u % 1) * math.pi)
        person(im, ca.MALE, ca.Pose(eyes="happy", mouth="grin", arm_r="up" if u < 0.3 or u > 1.7 else "down"), 110, 180)
        person(im, ca.OLD_FRIEND, ca.Pose(eyes="narrow", mouth="grin", arm_l="up" if 0.7 < u < 1.3 else "down", turn=-1), 250, 180)
        d.rounded_rectangle([x - 16, y - 10, x + 16, y + 10], 6, fill=PAPER, outline=(210, 206, 200), width=2)
    elif t < 4.6:                                              # 摔倒，伸手拉一把
        u = min((t - 2.8) / 1.6, 1)
        person(im, ca.MALE, ca.Pose(legs="sit", eyes="sad" if u < 0.5 else "happy", mouth="o" if u < 0.5 else "smile",
                                    arm_r="out" if u > 0.4 else "down", lean=-10 * (1 - u)), 120, 180)
        person(im, ca.OLD_FRIEND, ca.Pose(eyes="open", mouth="smile", arm_l="out", turn=-1, lean=-8), 236, 180)
    else:                                                      # 抱一下
        k = math.sin(t * 2.4)
        person(im, ca.MALE, ca.Pose(lean=8 + 2 * k, eyes="closed", mouth="smile", arm_r="out", blush=True), 158, 180)
        person(im, ca.OLD_FRIEND, ca.Pose(lean=-8 - 2 * k, eyes="closed", mouth="smile", arm_l="out", turn=-1), 212, 180)
        for i in range(3):
            u = (t * 0.6 + i / 3) % 1
            heart(im, 170 + 40 * math.sin(u * 6 + i), 80 - u * 60, 3, 1 - u)
    return im


VISIONS = {f.__name__: (f, zh) for f, zh in [
    (photo_flip, "炫耀过你 → 成了禁忌（合照翻面）"), (dusk_stuck, "停在某一个黄昏"),
    (eighty_bubble, "说好八十岁 → 公交站的陌生人"), (pillow_fight, "损友：互损、拉一把、抱一下"),
    (sunset_walk, "夕阳下牵手走"), (hug, "拥抱"), (together, "在一起（爱心）"), (farewell, "告别（行李箱）"),
    (honey_jar, "隔着蜂蜜罐看喜欢的人"), (no_sky, "好久没抬头看天"), (father_back, "爸爸的背影"),
    (gift_phone, "给爸爸换手机"), (dad_rain, "爸爸雨里奔波"), (exam_countdown, "高考倒计时"),
    (sunrise, "慢慢好起来（日出）"), (reader_smile, "正在读这句话的幸福的人"), (alone_window, "深夜窗前一个人"),
    (small_flower, "小确幸（小花）"),
]}


# ---------------------------------------------------------------- 手绘画面（douyin/handdrawn 工作室按每首歌重新画的，2026-10-28 起）
# assets/handdrawn/<歌>/index.json 登记场景，<场景>/f0000.png… 是 12fps 的逐帧（522×305，已是云里的大小）。
# 画面名加 hd_ 前缀；放完停在最后一帧。返回的图带 info["hd"]，comment_scene 就不再做像素放大。
HD_DIR = Path(__file__).resolve().parent.parent / "assets" / "handdrawn"


def _hd_scenes() -> dict:
    import json
    out = {}
    for idx in sorted(HD_DIR.glob("*/index.json")) if HD_DIR.is_dir() else []:
        for name, info in json.loads(idx.read_text(encoding="utf-8")).items():
            d = idx.parent / name
            n = len(list(d.glob("f*.png")))
            if n:
                out[f"hd_{name}"] = {"dir": d, "n": n, "fps": info.get("fps", 12), "zh": info.get("zh", name),
                                     "song": idx.parent.name, "preview": idx.parent / f"{name}.webp"}
    return out


HD = _hd_scenes()
_HD_LAST: dict = {}


def _hd_fn(name: str):
    def fn(t: float) -> Image.Image:
        h = HD[name]
        i = max(0, min(h["n"] - 1, int(t * h["fps"])))
        key = (name, i)
        if _HD_LAST.get(name, (None,))[0] != key:          # 每个画面只缓存当前一帧，省内存
            im = Image.open(h["dir"] / f"f{i:04d}.png").convert("RGBA")
            im.info["hd"] = True
            _HD_LAST[name] = (key, im)
        return _HD_LAST[name][1]
    return fn


VISIONS.update({name: (_hd_fn(name), f"手绘·{h['zh']}") for name, h in HD.items()})


def draw(name: str, t: float) -> Image.Image | None:
    """画面名 → 这一时刻的画面（带深色描边）；没有这个画面时返回 None。"""
    if name not in VISIONS:
        return None
    if name in HD:                                     # 手绘画面自带墨线，也已经是云里的成品尺寸
        return VISIONS[name][0](t)
    return outline(VISIONS[name][0](t))


def export() -> Path:
    out = Path(__file__).resolve().parent.parent / "assets" / "clawd" / "visions"
    out.mkdir(parents=True, exist_ok=True)
    tiles = []
    for name, (_, zh) in VISIONS.items():
        if name in HD:                                 # 手绘画面的预览由 handdrawn/export.py 生成
            continue
        frames = [draw(name, i / 15) for i in range(45)]
        frames[0].save(out / f"{name}.gif", save_all=True, append_images=frames[1:], duration=66, loop=0,
                       disposal=2, transparency=0)
        frames[30].save(out / f"{name}.png")
        tiles.append((name, zh, frames[30]))
    cols = 4
    sheet = Image.new("RGBA", (cols * (SIZE[0] + 20), ((len(tiles) + cols - 1) // cols) * (SIZE[1] + 50)), (34, 26, 30, 255))
    d = ImageDraw.Draw(sheet)
    for i, (name, zh, im) in enumerate(tiles):
        x, y = (i % cols) * (SIZE[0] + 20) + 10, (i // cols) * (SIZE[1] + 50) + 10
        sheet.alpha_composite(im, (x, y))
        d.text((x + 4, y + SIZE[1] + 6), f"{name}  {zh}", font=ImageFont.truetype(FONT, 16), fill=(240, 230, 220))
    sheet.convert("RGB").save(out / "overview.jpg", quality=90)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="想象画面库")
    ap.add_argument("--export", action="store_true")
    if ap.parse_args().export:
        print("已导出到", export())
