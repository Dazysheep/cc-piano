"""结尾小剧场「回家」：快到结尾时，画面中间浮现一个「视频小窗」（叠在音轨画面上），里面是家：
1. 男生推门回家，女生坐在餐桌旁挥手（桌上是红烧肉和两碗饭，窗外还是那个半月）；
2. 他坐下，两个人聊了会天（对话气泡）；
3. 女生拿起手机打开网易云播放这首歌，手机上方浮现一个小窗口：转动的唱片（这首歌的封面）+ 歌名歌手；
4. 两个人闭眼跟着歌轻轻摇，然后站起来向观众鞠躬；
5. 镜头从远往近推，小窗越来越大，直到画面消失（渐黑）。
舞台带上的两个小人在小窗出现前走出画面（回家去了），所以不会同时出现两次。

脚本放在 tracks/templates/ending/<名称>/v<N>.json（版本不覆盖），歌曲 json 写 "ending": {"name": "home", ...覆盖项}。
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import clawd_anim as ca
import scenes as sc
import visions

DIR = Path(__file__).resolve().parent / "templates" / "ending"
PW, PH = 1280, 720                     # 小窗大小


def load_script(spec: dict | str | None) -> dict:
    spec = {"name": spec} if isinstance(spec, str) else dict(spec or {})
    name = spec.pop("name", "home")
    ver = spec.pop("version", None)
    d = DIR / name
    vs = sorted(int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit())
    if not vs:
        raise FileNotFoundError(f"没有这个结尾脚本：{name}")
    base = json.loads((d / f"v{ver or vs[-1]}.json").read_text(encoding="utf-8"))
    for k, v in spec.items():
        base[k] = {**base[k], **v} if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base


class Home:
    """家里的一帧（PW×PH）。u：结尾进度 0~1（按脚本 beats 分段）。"""
    TABLE = 500
    BOY_SEAT, GIRL_SEAT = 360, 930          # 坐在餐桌两头，面对面

    def __init__(self, script: dict, cover: Image.Image, title: str, artist: str):
        self.s, self.cover, self.title, self.artist = script, cover, title, artist
        bg = Image.new("RGB", (PW, PH), (78, 58, 52))
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 590, PW, PH], fill=(112, 82, 62))                 # 木地板
        for x in range(0, PW, 90):
            d.line([x, 590, x - 40, PH], fill=(100, 72, 54), width=3)
        win = sc.sky(300, 230)
        sc.half_moon(win, 210, 80, 34)
        sc.skyline(win, 230, seed=3, scale=0.5)
        bg.paste(win, (860, 70))
        d.rectangle([860, 70, 1160, 300], outline=(150, 112, 84), width=10)
        d.line([1010, 70, 1010, 300], fill=(150, 112, 84), width=6)
        d.rectangle([60, 170, 230, 590], fill=(140, 96, 70))               # 门
        d.rectangle([60, 170, 230, 590], outline=(110, 74, 54), width=8)
        d.ellipse([200, 380, 214, 394], fill=(230, 200, 120))
        glow = Image.new("L", (PW, PH), 0)                                   # 吊灯的暖光
        ImageDraw.Draw(glow).ellipse([380, 100, 1000, 640], fill=80)
        bg.paste((255, 214, 150), (0, 0), glow.filter(ImageFilter.GaussianBlur(60)))
        d.line([690, 0, 690, 120], fill=(60, 50, 46), width=4)
        d.polygon([(640, 120), (740, 120), (710, 150), (670, 150)], fill=(240, 200, 130))
        self.bg = bg

    def frame(self, u: float, t: float) -> Image.Image:
        B = self.s["beats"]
        im = self.bg.copy().convert("RGBA")
        k = lambda name: sc.seg(u, *B[name])            # noqa: E731
        enter, chat, play, listen, bow = k("enter"), k("chat"), k("play"), k("listen"), k("bow")
        # 男生：推门进来走到座位 → 坐下 → 听歌摇 → 起身鞠躬
        if u < B["enter"][1]:
            bx = 150 + (self.BOY_SEAT - 150) * enter
            boy = ca.replace(ca.walk_happy(t), turn=1)
            floor_b = 585
        elif u < B["bow"][0]:
            bx, floor_b = self.BOY_SEAT, 585
            if u < B["play"][0]:
                talk = int(t / 0.25) % 2 if B["chat"][0] < u < (B["chat"][0] + B["chat"][1]) / 2 else 0
                boy = ca.Pose(eyes="happy", mouth="open" if talk else "smile", blush=True, lean=2 * math.sin(t * 2))
            elif u < B["listen"][0]:
                boy = ca.Pose(eyes="look_r", mouth="o")
            else:
                boy = ca.Pose(eyes="closed", mouth="smile", lean=5 * math.sin(t * 2.4), fx=[("note", t / 1.6)])
        else:
            bx, floor_b = PW / 2 - 90, 600
            boy = ca.bow(max(0.0, (u - B["bow"][0]) * self.s["seconds_hint"]))
        # 女生：坐着等 → 挥手 → 聊天 → 拿手机放歌 → 听歌摇 → 鞠躬
        gx, floor_g = self.GIRL_SEAT, 585
        if u < B["chat"][0]:
            girl = ca.wave(t) if enter > 0.3 else ca.Pose(eyes="look_l", mouth="smile")
        elif u < B["play"][0]:
            talk = int(t / 0.22) % 2 if u > (B["chat"][0] + B["chat"][1]) / 2 else 0
            girl = ca.Pose(eyes="happy", mouth="open" if talk else "smile", lean=-2 * math.sin(t * 2))
        elif u < B["listen"][0]:
            girl = ca.Pose(eyes="look_r", mouth="smile", arm_r="out")
        elif u < B["bow"][0]:
            girl = ca.Pose(eyes="closed", mouth="smile", lean=-5 * math.sin(t * 2.4), arm_r="out",
                           fx=[("note", t / 1.4), ("note", t / 1.4 + 0.5)])
        else:
            gx, floor_g = PW / 2 + 90, 600
            girl = ca.bow(max(0.0, (u - B["bow"][0]) * self.s["seconds_hint"]))
        sitting = B["enter"][1] <= u < B["bow"][0]
        d = ImageDraw.Draw(im)
        if u < B["bow"][0]:                                              # 餐桌在两人中间，两头是椅子
            for cx_, side in ((self.BOY_SEAT, -1), (self.GIRL_SEAT, 1)):
                d.rectangle([cx_ - 70, 520, cx_ + 70, 540], fill=(150, 100, 70))
                d.rectangle([cx_ + side * 60 - 8, 360, cx_ + side * 60 + 8, 540], fill=(130, 88, 62))
                d.rectangle([cx_ - 60, 540, cx_ - 48, 590], fill=(120, 80, 56))
                d.rectangle([cx_ + 48, 540, cx_ + 60, 590], fill=(120, 80, 56))
            sc.dining(d, 470, 820, self.TABLE)
            sc.braised_pork(im, 645, self.TABLE - 14, t, 1.0)
            sc.rice(d, 530, self.TABLE - 22, 0.8)
            sc.rice(d, 760, self.TABLE - 22, 0.8)
        if sitting:                                                      # 坐着：腿收起来，面对面
            boy = ca.replace(boy, legs="sit", turn=abs(boy.turn))
            girl = ca.replace(girl, legs="sit", turn=-abs(girl.turn))
            floor_b = floor_g = 530
        sc.person(im, ca.MALE, boy, bx, floor_b, 6)
        sc.person(im, ca.FEMALE, girl, gx, floor_g, 6)
        # 聊天气泡
        lines = self.s["chat"]
        if B["chat"][0] < u < B["play"][0]:
            mid = (B["chat"][0] + B["chat"][1]) / 2
            if u < mid:
                a = min(sc.seg(u, B["chat"][0], B["chat"][0] + 0.03), 1 - sc.seg(u, mid - 0.02, mid))
                sc.bubble(im, gx - 230, 250, lines["girl"], 28, a, (255, 228, 236), (120, 40, 70), max_w=420)
            else:
                a = min(sc.seg(u, mid, mid + 0.03), 1 - sc.seg(u, B["play"][0] - 0.02, B["play"][0]))
                sc.bubble(im, bx - 120, 250, lines["boy"], 28, a, (255, 255, 255), (60, 40, 40), max_w=420)
                visions.heart(im, bx + 120, 230 - 20 * ((t * 0.8) % 1), 4, a)
        # 手机 + 网易云小窗
        if u >= B["play"][0] and u < B["bow"][0]:
            px, py = gx - 80, floor_g - 110
            sc.phone(im, px, py, ang=-10, t=t, screen=(198, 30, 38), s=1.2)
            a = sc.seg(u, B["play"][0] + 0.02, B["play"][0] + 0.07) * (1 - sc.seg(u, B["bow"][0] - 0.03, B["bow"][0]))
            sc.mini_player(im, px - 230, py - 270, self.cover, self.title, self.artist, t, a)
        if u >= B["bow"][0]:
            visions.spark(im, PW / 2 - 40, 200, 4, 0.5 + 0.5 * math.sin(t * 4))
            visions.spark(im, PW / 2 + 60, 170, 3, 0.5 + 0.5 * math.cos(t * 3))
        return im


class Crossing:
    """结尾变体「擦肩」（《最佳损友》，取自评论 卡罗拉阔）：傍晚的十字路口，人潮里遇见老朋友 → 他抬手抬到一半，
    尴尬地改成摸后脑勺 → 男生微微笑着点头 → 老朋友转身走进人群 → 绿灯，男生一个人站着，手机震了（老朋友：「在吗」）
    → 女生走过来，两个人鞠躬。脚本 scene = "crossing"，beats：crowd / see / raise / nod / leave / phone / bow。"""
    FLOOR = 640
    BOY_X, FRIEND_X = 470, 840

    def __init__(self, script: dict, cover: Image.Image, title: str, artist: str):
        self.s = script
        bg = Image.new("RGB", (PW, PH))
        d = ImageDraw.Draw(bg)
        for y in range(PH):                                           # 傍晚的天：紫 → 橙
            k = min(y / 430, 1)
            d.line([0, y, PW, y], fill=(int(70 + 180 * k), int(54 + 100 * k), int(100 + 10 * k)))
        d.ellipse([880, 250, 1000, 370], fill=(255, 196, 120))         # 落日
        sc.skyline(bg, 430, seed=21, col=(60, 46, 70), scale=1.0)
        d.rectangle([0, 430, PW, 540], fill=(70, 66, 78))               # 马路 + 斑马线
        for x in range(120, 1100, 70):
            d.rectangle([x, 446, x + 40, 524], fill=(214, 210, 214))
        d.rectangle([0, 540, PW, PH], fill=(150, 128, 120))             # 人行道
        for x in range(0, PW, 120):
            d.line([x, 540, x - 30, PH], fill=(138, 116, 110), width=3)
        d.rectangle([1160, 230, 1170, 560], fill=(50, 50, 60))          # 红绿灯杆
        self.bg = bg
        rnd = random.Random(7)
        cols = [(200, 170, 120), (170, 160, 190), (230, 160, 170), (140, 180, 150), (190, 140, 120), (160, 170, 210),
                (220, 200, 150), (150, 150, 160)]
        self.crowd = []                                               # 人潮：不同颜色的小人左右穿行
        for i in range(15):                                           # 大多在后排，前排只有 3 个（主角要看得清）
            floor = 700 if i < 3 else rnd.choice((570, 588, 604))
            self.crowd.append({"look": ca.recolor(cols[i % len(cols)]), "x": rnd.uniform(0, PW), "floor": floor,
                               "v": rnd.choice((-1, 1)) * rnd.uniform(70, 130), "ph": rnd.random()})
        self.f_cap, self.f_cap_s, self.f_q = sc.font(30), sc.font(22, False), sc.font(36)

    def _boy(self, u, t, B):
        k = lambda name: sc.seg(u, *B[name])            # noqa: E731
        if u < B["crowd"][1]:
            return ca.replace(ca.walk(t), turn=1), 300 + (self.BOY_X - 300) * k("crowd")
        if u < B["raise"][0]:
            return ca.Pose(eyes="wide", mouth="o"), self.BOY_X
        if u < B["nod"][0]:
            return ca.Pose(eyes="open", mouth="closed", lean=1), self.BOY_X
        if u < B["leave"][0]:
            v = k("nod")
            return ca.Pose(eyes="happy", mouth="smile", squash=1 - 0.06 * math.sin(v * math.pi * 2)), self.BOY_X
        if u < B["phone"][0]:
            return ca.Pose(eyes="look_r", mouth="smile"), self.BOY_X
        if u < B.get("bow", [9, 9])[0]:                    # 没有 bow 这一段：看着手机笑到最后
            v = k("phone")
            return (ca.Pose(eyes="down" if v < 0.3 else "happy", mouth="o" if v < 0.3 else "grin", arm_r="out",
                            blush=v > 0.3, fx=[("spark", t / 0.9)] if v > 0.3 else []), self.BOY_X)
        v = k("bow")
        if v < 0.35:
            return ca.replace(ca.walk_happy(t), turn=1), self.BOY_X + (PW / 2 - 140 - self.BOY_X) * v / 0.35
        return ca.bow((v - 0.35) * (B["bow"][1] - B["bow"][0]) * self.s["seconds_hint"]), PW / 2 - 140

    def _friend(self, u, t, B):
        k = lambda name: sc.seg(u, *B[name])            # noqa: E731
        if u < B["crowd"][1]:
            return ca.replace(ca.walk(t + 0.3), turn=-1), 1150 + (self.FRIEND_X - 1150) * k("crowd")
        if u < B["raise"][0]:
            return ca.Pose(eyes="wide", mouth="o", turn=-1), self.FRIEND_X
        if u < B["nod"][0]:
            v = k("raise")
            if v < 0.5:                                  # 兴奋地把手抬起来……
                return (ca.Pose(eyes="happy", mouth="open", turn=-1, arm_l="out" if v < 0.25 else "up",
                                hop=1.0 * math.sin(min(v / 0.5, 1) * math.pi)), self.FRIEND_X)
            return (ca.Pose(eyes="down", mouth="smile", turn=-1, arm_l="head", blush=True,   # ……改成摸后脑勺
                            fx=[("sweat", t / 1.0)]), self.FRIEND_X)
        if u < B["leave"][0]:
            return ca.Pose(eyes="happy", mouth="smile", turn=-1, arm_l="head",
                           squash=1 - 0.05 * math.sin(k("nod") * math.pi * 2)), self.FRIEND_X
        if u < B["leave"][1]:                            # 转身走进人群
            return ca.replace(ca.walk(t), turn=1), self.FRIEND_X + 520 * k("leave")
        return None, 0

    def frame(self, u: float, t: float) -> Image.Image:
        B = self.s["beats"]
        im = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(im, "RGBA")
        green = u >= B["phone"][0]
        for i, col in enumerate(((235, 60, 60), (70, 210, 110))):   # 红绿灯
            on = (i == 1) == green
            d.rounded_rectangle([1140, 230 + i * 64, 1190, 286 + i * 64], 8, fill=(30, 30, 36))
            d.ellipse([1148, 238 + i * 64, 1182, 278 + i * 64], fill=col if on else (60, 60, 66))
        thin = sc.seg(u, B["phone"][0], B["phone"][0] + 0.06)          # 绿灯后人潮散开
        people = []
        for c in self.crowd:
            x = (c["x"] + c["v"] * t) % (PW + 200) - 100
            a = 1 - thin
            if a > 0.02:
                people.append((c["floor"], c["look"], ca.replace(ca.walk(t + c["ph"]), turn=1 if c["v"] > 0 else -1), x, 4, a))
        boy, bx = self._boy(u, t, B)
        people.append((self.FLOOR, ca.MALE, boy, bx, 6, 1.0))
        fr, fx = self._friend(u, t, B)
        if fr is not None:
            fade = 1 - sc.seg(u, B["leave"][0] + 0.6 * (B["leave"][1] - B["leave"][0]), B["leave"][1])
            people.append((self.FLOOR, ca.OLD_FRIEND, fr, fx, 6, fade))
        if "bow" in B and u >= B["bow"][0]:                          # 女生从右边走过来，一起鞠躬
            v = sc.seg(u, *B["bow"])
            if v < 0.35:
                girl, gx = ca.replace(ca.walk_happy(t), turn=-1), PW + 60 - (PW + 60 - (PW / 2 + 140)) * v / 0.35
            else:
                girl, gx = ca.bow((v - 0.35) * (B["bow"][1] - B["bow"][0]) * self.s["seconds_hint"]), PW / 2 + 140
            people.append((self.FLOOR, ca.FEMALE, girl, gx, 6, 1.0))
        for floor, look, pose, x, scale, a in sorted(people, key=lambda p: p[0]):
            if a >= 0.99:
                sc.person(im, look, pose, x, floor, scale)
            else:
                layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
                sc.person(layer, look, pose, x, floor, scale)
                im.alpha_composite(ca._fade(layer, a))
        if B["phone"][0] <= u < B.get("bow", [9, 9])[0]:             # 手机震了：老朋友发来「在吗」
            v = sc.seg(u, *B["phone"])
            sc.phone(im, bx + 80, self.FLOOR - 130, ang=-10, ring=1.0 if v < 0.3 else 0.0, t=t, screen=(237, 237, 237))
            a = sc.seg(v, 0.15, 0.35) * (1 - sc.seg(v, 0.92, 1.0) if "bow" in B else 1.0)
            if a > 0.01:
                card = Image.new("RGBA", (420, 110), (0, 0, 0, 0))
                dc = ImageDraw.Draw(card)
                dc.rounded_rectangle([0, 0, 419, 109], 24, fill=(250, 250, 250, 240))
                card.alpha_composite(sc.avatar(ca.OLD_FRIEND, ca.Pose(eyes="happy", mouth="smile"), 76), (16, 17))
                dc.text((108, 32), self.s["phone"]["name"], font=self.f_cap_s, fill=(120, 120, 130), anchor="lm")
                dc.text((108, 74), self.s["phone"]["text"], font=self.f_cap, fill=(20, 20, 20), anchor="lm")
                ca._put(im, ca._fade(card, a), (bx - 120, self.FLOOR - 420 - 20 * (1 - a)))
        # 字幕：评论原句（前半段）、结尾的问题（后半段）
        cap = self.s.get("caption")
        if cap:
            a = sc.seg(u, 0.02, 0.06) * (1 - sc.seg(u, B["nod"][1] - 0.04, B["nod"][1]))
            if a > 0.01:
                lay = Image.new("RGBA", (PW, 110), (0, 0, 0, 0))
                dl = ImageDraw.Draw(lay)
                dl.text((PW / 2, 34), cap["text"], font=self.f_cap, fill=(255, 250, 240), anchor="mm", stroke_width=4,
                        stroke_fill=(30, 20, 30))
                dl.text((PW / 2, 78), "—— " + cap["by"], font=self.f_cap_s, fill=(235, 225, 230), anchor="mm",
                        stroke_width=3, stroke_fill=(30, 20, 30))
                ca._put(im, ca._fade(lay, a), (0, 40))
        q = self.s.get("question")
        if q:
            a = sc.seg(u, B["phone"][0] + 0.04, B["phone"][0] + 0.08)
            if a > 0.01:
                lay = Image.new("RGBA", (PW, 80), (0, 0, 0, 0))
                ImageDraw.Draw(lay).text((PW / 2, 40), q, font=self.f_q, fill=(255, 250, 240), anchor="mm",
                                         stroke_width=5, stroke_fill=(30, 20, 30))
                ca._put(im, ca._fade(lay, a), (0, 50))
        if "bow" in B and u >= B["bow"][0] + 0.35 * (B["bow"][1] - B["bow"][0]):
            visions.spark(im, PW / 2 - 40, 330, 4, 0.5 + 0.5 * math.sin(t * 4))
            visions.spark(im, PW / 2 + 60, 300, 3, 0.5 + 0.5 * math.cos(t * 3))
        return im


SCENES = {"home": Home, "crossing": Crossing}


class HomeEnding:
    """叠在音轨画面上的结尾小窗：t0 浮现，t1 = 成片最后一帧。"""

    def __init__(self, script: dict, cover: Image.Image, title: str, artist: str, t0: float, t1: float):
        self.s, self.t0, self.t1 = script, t0, t1
        self.s["seconds_hint"] = t1 - t0
        self.home = SCENES[self.s.get("scene", "home")](self.s, cover, title, artist)
        sh = Image.new("L", (PW + 120, PH + 120), 0)
        ImageDraw.Draw(sh).rounded_rectangle([60, 70, PW + 60, PH + 70], 36, fill=170)
        self.shadow = sh.filter(ImageFilter.GaussianBlur(26))
        m = Image.new("L", (PW, PH), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, PW - 1, PH - 1], 30, fill=255)
        self.mask = m

    def __call__(self, im: Image.Image, t: float) -> None:
        if t < self.t0:
            return
        D = self.t1 - self.t0
        u = (t - self.t0) / D
        z0 = self.s["zoom_from"]                         # 最后这一段：镜头往前推，直到画面消失
        appear = sc.seg(t, self.t0, self.t0 + 0.8)
        zoom = sc.seg(u, z0, 1.0)
        pic = self.home.frame(u, t - self.t0)
        pic.putalpha(self.mask)
        k = (0.86 + 0.14 * appear) * (1 + 1.9 * zoom ** 1.6)
        w, h = int(PW * k), int(PH * k)
        pic = pic.resize((w, h), Image.LANCZOS if zoom < 0.01 else Image.BILINEAR)
        W, H = im.size
        cx, cy = W / 2, H / 2 - 20 * (1 - zoom)
        if zoom < 0.5:
            s = self.shadow.resize((int(self.shadow.width * k), int(self.shadow.height * k)))
            im.paste((0, 0, 0), (int(cx - s.width / 2), int(cy - s.height / 2)),
                     s.point(lambda v: int(v * appear * (1 - zoom * 2))))
        if appear < 1:
            pic.putalpha(pic.getchannel("A").point(lambda v: int(v * appear)))
        rgba = im.convert("RGBA")
        ca._put(rgba, pic, (cx - w / 2, cy - h / 2))
        fade = sc.seg(u, self.s["fade_from"], 1.0)
        if fade > 0:
            rgba = Image.blend(rgba, Image.new("RGBA", rgba.size, (0, 0, 0, 255)), fade)
        im.paste(rgba.convert("RGB"))
