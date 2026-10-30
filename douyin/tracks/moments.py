"""跟着歌词走的「主题动画」+「只听某一轨」（Solo）。

主题动画（Moment）：在某句歌词唱到时，音轨区域里浮现一个中等大小的画面（背景透明，只有东西本身 + 深色描边），
慢慢出现、停留几秒、慢慢消失。每个画面是一个函数：进度 u(0~1)、秒数 t → RGBA 图。歌曲 json 写：
  "moments": [{"kind": "question_mark", "from": 30.5, "to": 37.0}, ...]（视频时间）
Solo：歌曲 json 写 "solos": [{"track": "vocals", "from": 40, "to": 46, "label": "只听人声"}]：
  - 画面：这一轨亮起、S 键变黄，其他轨压暗，顶部一个小牌子「🎧 只听人声」；
  - 声音：出片时那几秒换成这一轨的分离音轨（solo_music()，前后 0.3 秒交叉淡化，响度对齐原曲）。
"""
import math

import numpy as np
from PIL import Image, ImageDraw

import clawd_anim as ca
import daw
import scenes as sc
import visions

PW, PH = 640, 380                 # 主题画面大小
RED, WHITE = (226, 60, 70), (250, 248, 244)


def _new():
    return Image.new("RGBA", (PW, PH), (0, 0, 0, 0))


def person(im, look, pose, x, floor, scale=4):
    sc.person(im, look, pose, x, floor, scale)


# ---------------------------------------------------------------- 主题画面
def question_mark(u: float, t: float) -> Image.Image:
    """Who am I?：像素方块一块块飞进来拼成一个大问号（专辑封面就是一个问号），男生抬头看着它。"""
    im = _new()
    d = ImageDraw.Draw(im)
    Q = [".XXXXX.", "XX...XX", "XX...XX", ".....XX", "....XX.", "...XX..", "...XX..", ".......", "...XX.."]
    cells = [(x, y) for y, row in enumerate(Q) for x, ch in enumerate(row) if ch == "X"]
    s = 30
    ox, oy = PW / 2 - 3.5 * s + 60, 18
    for i, (x, y) in enumerate(cells):
        k = sc.ease(u * 4.5 - i * 0.07)
        fx, fy = ox + x * s, oy + y * s
        sx, sy = fx + (1 - k) * (math.sin(i * 1.7) * 260), fy + (1 - k) * (-200 - i * 8)
        if k > 0.01:
            c = WHITE if (x + y) % 2 else (220, 216, 210)
            d.rectangle([sx, sy, sx + s - 3, sy + s - 3], fill=(*c, int(255 * min(1, k * 1.5))))
    person(im, ca.MALE, ca.Pose(eyes="look_up", mouth="o" if u < 0.6 else "closed", lean=-2 * math.sin(t)), PW / 2 - 200, PH - 20)
    return visions.outline(im)


def hold_string(u: float, t: float) -> Image.Image:
    """afraid to let go：一只手紧紧攥着红色爱心气球的绳子，风一阵阵把气球往外拽，手越攥越紧，就是不松开。"""
    im = _new()
    d = ImageDraw.Draw(im)
    gust = 0.5 + 0.5 * math.sin(t * 2.6)
    hx, hy = 210, 300
    bx = hx + 150 + 90 * gust
    by = 120 - 20 * gust
    pts = [(hx + 20, hy - 10)]
    for k in range(1, 9):                                   # 绳子：被风吹得发抖的弧线
        v = k / 8
        pts.append((hx + 20 + (bx - hx - 20) * v + 6 * math.sin(t * 9 + k) * v,
                    hy - 10 + (by + 60 - hy + 10) * v - 30 * math.sin(math.pi * v)))
    d.line(pts, fill=(240, 236, 230), width=3)
    visions.heart(im, bx - 45, by - 40, 18, 1.0)             # 气球（大号像素爱心）
    d.ellipse([hx - 40, hy - 40, hx + 40, hy + 30], fill=ca.BODY)   # 手：小人颜色的拳头
    for k in range(4):
        d.rectangle([hx - 34 + k * 18, hy - 46, hx - 22 + k * 18, hy - 20], fill=ca.HI)
    d.rectangle([hx - 26, hy + 26, hx + 20, hy + 90], fill=ca.SHADE)
    for k in range(3):                                      # 风
        y = 60 + k * 70
        x0 = (t * 260 + k * 170) % (PW + 200) - 100
        d.line([x0, y, x0 + 90, y - 6], fill=(220, 230, 250, 160), width=3)
    return visions.outline(im)


def typing_dots(u: float, t: float) -> Image.Image:
    """let me know：手机聊天窗口里「对方正在输入…」的三个点一直跳，消息始终没有发过来。"""
    im = _new()
    d = ImageDraw.Draw(im)
    x0, y0, w, h = PW / 2 - 120, 10, 240, 360
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 28, fill=(28, 30, 38), outline=(200, 205, 220), width=4)
    d.rounded_rectangle([x0 + 12, y0 + 30, x0 + w - 12, y0 + h - 30], 12, fill=(236, 238, 242))
    d.text((x0 + w / 2, y0 + 50), "对方正在输入…", font=sc.font(18, False), fill=(120, 124, 136), anchor="mm")
    d.rounded_rectangle([x0 + w - 150, y0 + 80, x0 + w - 24, y0 + 120], 14, fill=(150, 220, 120))
    d.text((x0 + w - 87, y0 + 100), "你还会回来吗", font=sc.font(17), fill=(30, 50, 30), anchor="mm")
    by = y0 + 150
    d.rounded_rectangle([x0 + 24, by, x0 + 104, by + 40], 14, fill=WHITE)
    for k in range(3):                                      # 三个点轮流跳
        jump = max(0.0, math.sin(t * 6 - k * 0.9)) * 6
        d.ellipse([x0 + 40 + k * 20, by + 14 - jump, x0 + 52 + k * 20, by + 26 - jump], fill=(140, 144, 156))
    return visions.outline(im)


def rain_umbrella(u: float, t: float) -> Image.Image:
    """I'm sad, I know：男生头顶一朵小雨云在下雨；女生从旁边走过来，替他撑起一把伞。"""
    im = _new()
    d = ImageDraw.Draw(im)
    bx, floor = PW / 2 - 40, PH - 24
    visions.puff(d, bx, 70, 150, (150, 156, 176))
    cover = sc.ease((u - 0.45) / 0.25)                        # 伞撑起来以后雨就淋不到他了
    visions.rain(d, t, bx - 70, bx + 70, 90, floor - 40 if cover < 0.5 else 150, n=12)
    person(im, ca.MALE, ca.Pose(eyes="sad" if cover < 0.6 else "happy", mouth="frown" if cover < 0.6 else "smile",
                                squash=0.95, fx=[("tear", t / 1.2)] if cover < 0.6 else []), bx, floor)
    gx = PW + 40 - (PW + 40 - (bx + 90)) * sc.ease(u / 0.45)  # 女生走过来
    g = ca.walk_happy(t) if u < 0.45 else ca.Pose(eyes="happy", mouth="smile", arm_l="up", blush=True)
    if u < 0.45:
        g = ca.replace(g, turn=-1)
    person(im, ca.FEMALE, g, gx, floor)
    if u > 0.3:                                             # 伞：举在两人头顶
        ux = gx - 40 * cover - 10
        uy = 150 - 30 * cover
        d.pieslice([ux - 110, uy - 60, ux + 110, uy + 60], 180, 360, fill=(240, 120, 150))
        for k in range(5):
            d.line([ux, uy, ux - 110 + k * 55, uy], fill=(200, 90, 120), width=2)
        d.line([ux, uy, ux, uy + 110], fill=(90, 70, 70), width=4)
    return visions.outline(im)


def mend_heart(u: float, t: float) -> Image.Image:
    """broken heart：一颗裂开的像素心，碎片慢慢飞回去，最后补好、发光。"""
    im = _new()
    k = sc.ease((u - 0.25) / 0.5)
    big = ca._pixel(ca.HEART_SHAPE, ca.HEART, 44)
    w, h = big.size
    left, right = big.crop((0, 0, w // 2, h)), big.crop((w // 2, 0, w, h))
    gap = (1 - k) * 70
    tilt = (1 - k) * 14
    cx, cy = PW / 2, PH / 2 - 10
    ca._put(im, left.rotate(tilt, Image.NEAREST, expand=True), (cx - w / 2 - gap, cy - h / 2))
    ca._put(im, right.rotate(-tilt, Image.NEAREST, expand=True), (cx + gap - 6, cy - h / 2))
    if k > 0.95:
        visions.spark(im, cx - 140, cy - 120, 4, 0.5 + 0.5 * math.sin(t * 5))
        visions.spark(im, cx + 110, cy - 90, 3, 0.5 + 0.5 * math.cos(t * 4))
    return visions.outline(im)


def _glass(d: ImageDraw.ImageDraw, x, y, a=255, tilt=0.0):
    """一只啤酒杯（左上角 x, y）：琥珀色酒、白色泡沫、玻璃描边和把手。"""
    w, h = 90, 130
    dx = tilt * 18
    d.rounded_rectangle([x + dx, y, x + w + dx, y + h], 10, fill=(240, 176, 60, a))
    d.rounded_rectangle([x + dx - 6, y - 26, x + w + dx + 6, y + 14], 16, fill=(252, 250, 244, a))
    d.rounded_rectangle([x + dx, y, x + w + dx, y + h], 10, outline=(255, 244, 220, a), width=5)
    d.arc([x + w + dx - 10, y + 24, x + w + dx + 36, y + 96], -90, 90, fill=(255, 244, 220, a), width=9)


def clink_glass(u: float, t: float) -> Image.Image:
    """前奏：两只酒杯碰一下，泡沫溅起来；之后左边那只慢慢淡掉，只剩一只。"""
    im = _new()
    d = ImageDraw.Draw(im)
    k = sc.ease(u / 0.28)
    hit = 0.26 < u < 0.42
    gap = 150 * (1 - k)
    left_a = int(255 * (1 - sc.seg(u, 0.55, 0.85)))
    _glass(d, PW / 2 - 104 - gap, 175, left_a, tilt=0.4 * k)
    _glass(d, PW / 2 + 14 + gap, 175, 255, tilt=-0.4 * k)
    if hit:                                                 # 碰杯：泡沫溅起来 + 火花
        v = (u - 0.26) / 0.16
        for j in range(7):
            ang = math.pi * (0.15 + 0.7 * j / 6)
            r = 40 + 90 * v
            x, y = PW / 2 + r * math.cos(ang) * 1.3, 155 - r * math.sin(ang)
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(252, 250, 244, int(255 * (1 - v))))
        visions.spark(im, PW / 2 - 14, 70, 5, 1 - v)
    return visions.outline(im)


def photo_split(u: float, t: float) -> Image.Image:
    """第一段主歌：一张两人合照，中间出现一道裂缝，往两边慢慢分开。"""
    im = _new()
    pw, ph = 300, 240
    p = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    dp = ImageDraw.Draw(p)
    dp.rectangle([0, 0, pw - 1, ph - 1], fill=visions.PAPER)
    dp.rectangle([12, 12, pw - 13, ph - 44], fill=(150, 196, 236))
    person(p, ca.MALE, ca.Pose(eyes="happy", mouth="grin", arm_r="out"), pw * 0.34, ph - 46, 5)
    person(p, ca.OLD_FRIEND, ca.Pose(eyes="happy", mouth="grin", arm_l="out", turn=-1), pw * 0.68, ph - 46, 5)
    crack = sc.seg(u, 0.15, 0.4)
    split = sc.ease(sc.seg(u, 0.4, 0.85))
    pts = [(pw / 2 + (9 if i % 2 else -9), i * ph / 10) for i in range(11)]   # 锯齿形裂缝
    if crack > 0:
        n = max(2, int(11 * crack))
        ImageDraw.Draw(p).line(pts[:n], fill=(60, 40, 40), width=4)
    if split <= 0:
        ca._put(im, p, (PW / 2 - pw / 2, PH / 2 - ph / 2))
    else:                                                   # 沿裂缝切成两半，往两边分开、各自歪一点
        m = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(m).polygon([(0, 0)] + pts + [(0, ph)], fill=255)
        left, right = p.copy(), p.copy()
        left.putalpha(Image.composite(p.getchannel("A"), Image.new("L", p.size, 0), m))
        right.putalpha(Image.composite(Image.new("L", p.size, 0), p.getchannel("A"), m))
        gap = 90 * split
        ca._put(im, left.rotate(6 * split, Image.NEAREST, expand=False), (PW / 2 - pw / 2 - gap, PH / 2 - ph / 2 + 10 * split))
        ca._put(im, right.rotate(-6 * split, Image.NEAREST, expand=False), (PW / 2 - pw / 2 + gap, PH / 2 - ph / 2 + 10 * split))
    return visions.outline(im)


def fork_road(u: float, t: float) -> Image.Image:
    """副歌：一条路分成两条岔路，两个小剪影各走一条，越走越远；路口浮出评论里的诗句。"""
    im = _new()
    d = ImageDraw.Draw(im)
    road = (120, 110, 130)
    fx, fy = PW / 2, 230                                    # 岔口
    d.polygon([(fx - 60, PH), (fx + 60, PH), (fx + 22, fy), (fx - 22, fy)], fill=road)
    d.polygon([(fx - 22, fy), (fx + 4, fy), (70, 40), (30, 40)], fill=road)
    d.polygon([(fx - 4, fy), (fx + 22, fy), (PW - 30, 40), (PW - 70, 40)], fill=road)
    k = sc.ease(sc.seg(u, 0.1, 0.9))
    lx, ly = fx + (110 - fx) * k, fy + (100 - fy) * k + 10
    rx, ry = fx + (PW - 110 - fx) * k, fy + (100 - fy) * k + 10
    sz = max(2, int(4 - 2 * k))
    person(im, ca.MALE, ca.replace(ca.walk(t), turn=-1), lx - 18, ly, sz)
    person(im, ca.OLD_FRIEND, ca.replace(ca.walk(t + 0.3), turn=1), rx + 18, ry, sz)
    a = int(255 * sc.seg(u, 0.25, 0.4))
    if a:
        f = sc.font(30)
        d.text((PW / 2, PH - 64), "人生南北多歧路 君向潇湘我向秦", font=f, fill=(255, 246, 230, a), anchor="mm",
               stroke_width=4, stroke_fill=(20, 16, 24, a))
        d.text((PW / 2, PH - 26), "—— 落日归山海_us", font=sc.font(18, False), fill=(220, 214, 220, a), anchor="mm",
               stroke_width=3, stroke_fill=(20, 16, 24, a))
    return im


KINDS = {"question_mark": (question_mark, "Who am I?：像素方块拼成大问号"),
         "clink_glass": (clink_glass, "最佳损友前奏：碰杯，之后只剩一只杯子"),
         "photo_split": (photo_split, "最佳损友主歌：合照裂开，往两边分开"),
         "fork_road": (fork_road, "最佳损友副歌：岔路，两个人各走一条"),
         "hold_string": (hold_string, "afraid to let go：攥紧气球的绳子不松手"),
         "typing_dots": (typing_dots, "let me know：对方正在输入…却一直没发来"),
         "rain_umbrella": (rain_umbrella, "I'm sad：下雨了，她来撑伞"),
         "mend_heart": (mend_heart, "broken heart：碎掉的心慢慢补好")}


class Moments:
    """叠在音轨画面上的主题动画（cx, cy：画面中心；默认在时间线左半边，避开男生头顶的想象云朵）。"""

    ZOOM = 1.45

    def __init__(self, items: list[dict], cx: float | None = None, cy: float | None = None, bottom: int = 170):
        self.items = [m for m in items if m.get("kind") in KINDS]
        self.cx = cx or (daw.TL_X + daw.W) / 2 - 120              # 时间线中间偏左
        self.cy = cy or (daw.LANE_TOP + (daw.H - bottom)) / 2
        w, h = int(PW * self.ZOOM) + 160, int(PH * self.ZOOM) + 120   # 一圈柔和的暗晕，让画面从波形里跳出来
        halo = Image.new("L", (w, h), 0)
        ImageDraw.Draw(halo).ellipse([40, 30, w - 40, h - 30], fill=150)
        from PIL import ImageFilter
        self.halo = halo.filter(ImageFilter.GaussianBlur(50))

    def __call__(self, im: Image.Image, t: float) -> None:
        for m in self.items:
            a, b = float(m["from"]), float(m["to"])
            if not a - 0.01 <= t <= b:
                continue
            u = (t - a) / (b - a)
            alpha = min(sc.seg(t, a, a + 0.8), 1 - sc.seg(t, b - 0.7, b))
            pic = KINDS[m["kind"]][0](u, t - a)
            k = (0.9 + 0.1 * sc.ease((t - a) / 0.8)) * self.ZOOM
            pic = pic.resize((int(PW * k), int(PH * k)), Image.NEAREST)
            im.paste((0, 0, 0), (int(self.cx - self.halo.width / 2), int(self.cy - self.halo.height / 2)),
                     self.halo.point(lambda v, a=alpha: int(v * a)))
            rgba = im.convert("RGBA")
            ca._put(rgba, ca._fade(pic, alpha), (self.cx - pic.width / 2, self.cy - pic.height / 2))
            im.paste(rgba.convert("RGB"))


class SoloLanes:
    """只听某一轨：这一轨亮起（描边 + S 键变黄），其他轨压暗，顶部小牌子写「只听 X」。"""

    def __init__(self, solos: list[dict], view):
        self.solos, self.view = solos, view
        self.keys = [t["key"] for t in view.tracks]
        self.f = sc.font(30)

    def __call__(self, im: Image.Image, t: float) -> None:
        for s in self.solos:
            a, b = float(s["from"]), float(s["to"])
            if not a <= t <= b or s["track"] not in self.keys:
                continue
            k = min(sc.seg(t, a, a + 0.35), 1 - sc.seg(t, b - 0.35, b))
            i = self.keys.index(s["track"])
            lh = self.view.lane_h
            y0, y1 = daw.LANE_TOP + i * lh, daw.LANE_TOP + (i + 1) * lh - 6
            ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            for j in range(len(self.keys)):                 # 其他轨压暗
                if j != i:
                    d.rectangle([0, daw.LANE_TOP + j * lh, daw.W, daw.LANE_TOP + (j + 1) * lh - 6],
                                fill=(0, 0, 0, int(150 * k)))
            d.rounded_rectangle([daw.TL_X - 4, y0 - 3, daw.W - 6, y1 + 3], 10, outline=(255, 214, 110, int(230 * k)),
                                width=4)
            sx, sy = daw.HEADER_W - 70, y0 + lh - 34          # S 键变黄
            d.rounded_rectangle([sx, sy, sx + 26, sy + 22], 5, fill=(255, 200, 60, int(255 * k)))
            d.text((sx + 13, sy + 11), "S", font=sc.font(16), fill=(30, 20, 10, int(255 * k)), anchor="mm")
            label = s.get("label", "只听这一轨")
            tw = d.textlength(label, font=self.f)
            lx, ly = (daw.TL_X + daw.W) / 2 - tw / 2 - 24, daw.LANE_TOP + 10
            d.rounded_rectangle([lx, ly, lx + tw + 48, ly + 52], 26, fill=(255, 200, 60, int(235 * k)))
            d.text((lx + 24, ly + 26), label, font=self.f, fill=(30, 20, 10, int(255 * k)), anchor="lm",
                   embedded_color=False)
            rgba = im.convert("RGBA")
            rgba.alpha_composite(ov)
            im.paste(rgba.convert("RGB"))


def solo_music(src: np.ndarray, stems: dict, sr: int, start: float, solos: list[dict], out_path) -> None:
    """把原曲在 Solo 时间段换成对应的分离音轨（响度按那一段对齐原曲的 70%，前后 0.3 秒交叉淡化），写 wav。
    src：整首原曲 (n, 2)；stems：{track: (n, 2)}；时间按视频时间 + start 换算到原曲。"""
    import soundfile as sf
    out = src.astype(np.float32).copy()
    fade = int(0.3 * sr)
    for s in solos:
        st = stems.get(s["track"])
        if st is None:
            continue
        a, b = int((start + float(s["from"])) * sr), int((start + float(s["to"])) * sr)
        a, b = max(0, a), min(len(out), b)
        if b - a < 2 * fade:
            continue
        seg_src, seg_st = out[a:b], st[a:b].astype(np.float32)
        g = 0.7 * (np.sqrt(np.mean(seg_src ** 2)) + 1e-6) / (np.sqrt(np.mean(seg_st ** 2)) + 1e-6)
        g = min(g, 4.0)
        w = np.ones(b - a, np.float32)
        w[:fade] = np.linspace(0, 1, fade)
        w[-fade:] = np.linspace(1, 0, fade)
        out[a:b] = seg_src * (1 - w[:, None]) + seg_st * g * w[:, None]
    sf.write(str(out_path), np.clip(out, -1, 1), sr)
