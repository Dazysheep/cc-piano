"""开头小剧场「加班的夜」（替代原来单独的拨片开头，最后接上拨片开头，再进入音轨画面）。

1. 夜空和半月，画面中间浮现最戳人的那条评论；歌响起，歌名歌手浮现在左上角。
2. 镜头从月亮往下摇，经过高楼，推进一扇亮着的窗：男生 CC 小人在高楼里的办公桌前读评论（窗外也是半月）。
3. 读到那条评论：评论从屏幕里浮起来，头顶冒出想象云朵（visions 画面），很有感触。
4. 老板来电：来电卡片里是老板（灰色 + 红领带，生气冒烟），电话里一直冒出乱码气泡（！……#（@……），他被吼得扭头把手机拿远；老板挂断。
5. 他很难受；女朋友来电：卡片里是女生小人（爱心眼），粉色气泡「今晚早点回来呀，做了你最爱吃的红烧肉」；他哭了，伸手摸桌上女朋友送的老虎扭蛋机。
6. 拨片开头在右边的空白处浮现，整个画面从右往左拉，直到歌曲封面到正中；歌名从左上角移到封面下面；同时他收拾东西、关灯，走出画面离开公司。

脚本（文字、时间分配）放在 tracks/templates/opening/<名称>/v<N>.json，版本不覆盖；歌曲 json 里写 "opening": {"name": "office", ...覆盖项}。
时间分配 beats 是占整段开头的比例（0~1），开头总长由模板的 intro 秒数（卡点后）决定。
"""
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import clawd_anim as ca
import flick_intro
import scenes as sc
import sfx
import visions

DIR = Path(__file__).resolve().parent / "templates" / "opening"
W, H = 1920, 1080


def load_script(spec: dict | str | None) -> dict:
    """{"name": "office", "version": 1, ...覆盖项} → 合并后的脚本。"""
    spec = {"name": spec} if isinstance(spec, str) else dict(spec or {})
    name = spec.pop("name", "office")
    ver = spec.pop("version", None)
    d = DIR / name
    vs = sorted(int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit())
    if not vs:
        raise FileNotFoundError(f"没有这个开头脚本：{name}")
    base = json.loads((d / f"v{ver or vs[-1]}.json").read_text(encoding="utf-8"))
    for k, v in spec.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return base


# ====================================================================== 外景：夜空 → 高楼
class Exterior:
    TILT = 1150                                     # 镜头往下摇的距离（像素）

    def __init__(self):
        world_h = H + self.TILT
        self.world = sc.sky(W, world_h).convert("RGB")
        sc.half_moon(self.world, 1380, 250, 70)
        sc.skyline(self.world, world_h, seed=11, col=(16, 20, 40), scale=1.4)
        d = ImageDraw.Draw(self.world)
        bx0, bx1, top = 560, 1360, H + 40           # 中间这栋高楼
        d.rectangle([bx0, top, bx1, world_h], fill=(26, 30, 52))
        rnd = random.Random(2)
        self.win = (900, world_h - 470, 1020, world_h - 380)       # 他的那扇窗（亮着暖光）
        for y in range(top + 40, world_h - 40, 120):
            for x in range(bx0 + 40, bx1 - 80, 150):
                lit = rnd.random() < 0.18
                d.rectangle([x, y, x + 110, y + 80], fill=(255, 214, 140) if lit else (44, 50, 80))
        d.rectangle(self.win, fill=(255, 220, 150))
        d.rectangle([self.win[0], self.win[1], self.win[2], self.win[3]], outline=(255, 240, 200), width=4)

    def frame(self, t: float, u: float, zoom: float = 0.0) -> Image.Image:
        y = u * self.TILT
        im = self.world.crop((0, int(y), W, int(y) + H))
        sc.stars(im, t, 80, seed=4, y_max=max(0, 700 - y), dy=0)
        if zoom > 0.001:                            # 推进那扇亮着的窗
            cx, cy = (self.win[0] + self.win[2]) / 2, (self.win[1] + self.win[3]) / 2 - y
            k = 1 + 9 * zoom ** 2
            bw, bh = W / k, H / k
            box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
            im = im.crop(tuple(int(v) for v in box)).resize((W, H), Image.BILINEAR)
        return im


# ====================================================================== 内景：高楼办公室
class Office:
    DESK = 740
    BOY_X = 1160

    def __init__(self, script: dict):
        self.s = script
        bg = Image.new("RGB", (W, H), (34, 38, 56))
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 860, W, H], fill=(26, 28, 40))
        win = sc.sky(680, 510)                       # 大窗户：夜空、半月、城市
        sc.half_moon(win, 520, 130, 46)
        sc.skyline(win, 510, seed=5, scale=0.8)
        bg.paste(win, (140, 110))
        d.rectangle([140, 110, 820, 620], outline=(70, 74, 96), width=14)
        d.line([480, 110, 480, 620], fill=(70, 74, 96), width=10)
        d.line([140, 365, 820, 365], fill=(70, 74, 96), width=10)
        self.bg = bg
        self.boss_lines = script.get("boss", {}).get("lines", [])

    # ---- 他的动作（姿态, x, 拿手机的位置/None）
    def boy(self, t: float, B: dict) -> tuple[ca.Pose, float, tuple | None]:
        x = self.BOY_X
        if t < B["feel"][0]:                         # 读评论：盯着右边的屏幕
            scan = ["look_r", "open", "look_r"][int(t / 0.5) % 3]
            return ca.Pose(eyes=scan if (t % 2.4) > 0.12 else "blink", lean=2 * math.sin(t * 1.4)), x, None
        if t < B["boss"][0]:                         # 读到了：脸红、眯眼，有点想哭又想笑
            u = sc.seg(t, *B["feel"])
            return ca.Pose(eyes="happy" if u > 0.25 else "wide", mouth="smile", blush=True, lean=-3 * u,
                           arm_l="hug", arm_r="hug", fx=[("spark", t / 1.4)] if u > 0.4 else []), x, None
        if t < B["sad"][0]:                          # 老板来电
            u = sc.seg(t, *B["boss"])
            if u < 0.14:                             # 吓一跳
                return ca.Pose(eyes="wide", mouth="o", hop=1.5 * math.sin(u / 0.14 * math.pi)), x, None
            if u < 0.88:                             # 被吼：扭头、把手机拿得远远的
                away = sc.ease((u - 0.14) / 0.2)
                return (ca.Pose(eyes="narrow" if int(t / 0.4) % 2 else "closed", mouth="frown", lean=-16 * away,
                                turn=-1 if away > 0.5 else 1, arm_r="out", dx=0.6 * math.sin(t * 30) * away,
                                fx=[("sweat", t / 0.9)]),
                        x, (x + 150 + 40 * away, self.DESK - 120))
            return ca.Pose(eyes="sad", mouth="frown", arm_r="out"), x, (x + 140, self.DESK - 110)
        if t < B["partner"][0]:                      # 难受
            return ca.Pose(eyes="sad", mouth="frown", squash=0.95, lean=-2, fx=[("tear", t / 1.3)]), x, None
        if t < B["pull"][0]:                         # 女朋友来电：哭着笑，伸手摸扭蛋机
            u = sc.seg(t, *B["partner"])
            if u < 0.12:
                return ca.Pose(eyes="look_r", mouth="o"), x, None
            reach = u > 0.55
            return (ca.Pose(eyes="sad" if int(t / 1.6) % 2 == 0 else "closed", mouth="smile", blush=True,
                            arm_r="out", arm_l="out" if reach else "down", lean=-4 if reach else 0,
                            fx=[("tear", t / 1.0), ("tear", t / 1.0 + 0.5)]),
                    x, (x + 120, self.DESK - 120))
        if t < B["flick"][0]:                        # 拉扭蛋机的摇杆：往左探身，左手往下一拉
            u = sc.seg(t, *B["pull"])
            k = math.sin(min(u / 0.7, 1) * math.pi * 0.5) if u < 0.7 else 1 - (u - 0.7) / 0.3 * 0.4
            return (ca.Pose(eyes="closed" if u < 0.5 else "happy", mouth="smile", blush=True, lean=-10 - 8 * k,
                            arm_l="out", squash=1 - 0.06 * k, fx=[("tear", t / 1.2)] if u < 0.4 else [("spark", t)]),
                    x - 40 * sc.ease(u / 0.3), None)
        u = (t - B["flick"][0]) / max(B["flick"][1] - B["flick"][0], 1e-6)   # 收拾东西下班：站起来、走出画面
        if u < 0.15:
            return ca.Pose(eyes="happy", mouth="smile", hop=2 * math.sin(u / 0.15 * math.pi)), x - 40, None
        k = min(1.0, (u - 0.15) / 0.75)
        return ca.replace(ca.walk(t), turn=-1, lean=-4), (x - 40) - (x + 260) * k, None

    def frame(self, t: float, B: dict, cover_pic=None) -> Image.Image:
        im = self.bg.copy().convert("RGBA")
        sc.stars(im, t, 25, seed=9, y_max=330)       # 窗外的星星（会被窗框挡住一点，没关系）
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 0)))
        leave = sc.seg(t, *B["flick"])
        lights = 1 - sc.ease((leave - 0.55) / 0.35)    # 他走出去以后关灯
        d = ImageDraw.Draw(im)
        sc.lamp(im, 820, self.DESK, lights)
        sc.monitor(im, 1300, 470, 360, 230, t, lights)
        pose, x, hand = self.boy(t, B)
        sc.person(im, ca.MALE, pose, x, self.DESK + 40, 8)
        sc.desk(d, 760, 1800, self.DESK)
        pull = sc.seg(t, *B["pull"])
        lever = math.sin(min(pull / 0.7, 1) * math.pi * 0.5) * (1 - sc.seg(t, B["flick"][0], B["flick"][0] + 0.5))
        touch = B["partner"][0] + 0.55 * (B["partner"][1] - B["partner"][0]) < t < B["pull"][0]
        shake = 1.0 if touch or 0.3 < pull < 1.0 else 0.0
        drop = (t - B["pull"][0] - 0.45 * (B["pull"][1] - B["pull"][0])) / 0.6 if pull > 0.45 else -1.0
        sc.gacha(im, 930, self.DESK, t, shake, lever=lever, drop=drop)
        if shake or 0 <= drop < 2:
            visions.spark(im, 960, self.DESK - 260, 4, 0.5 + 0.5 * math.sin(t * 5))
        # 手机：在桌上响 → 拿在手里
        boss_ring = B["boss"][0] < t < B["boss"][0] + 0.14 * (B["boss"][1] - B["boss"][0])
        gf_ring = B["partner"][0] < t < B["partner"][0] + 0.12 * (B["partner"][1] - B["partner"][0])
        if hand:
            sc.phone(im, hand[0], hand[1], ang=-12, t=t, screen=(70, 150, 90))
        elif leave < 0.15:
            sc.phone(im, 1240, self.DESK - 6, ang=90, ring=1.0 if (boss_ring or gf_ring) else 0.0, t=t,
                     screen=(60, 120, 200))
        # 读到的那条评论：从屏幕里浮起来；想象云朵
        if B["feel"][0] - 0.3 < t < B["boss"][0]:
            u = sc.seg(t, B["feel"][0] - 0.3, B["feel"][0] + 0.6)
            out = 1 - sc.seg(t, B["boss"][0] - 0.4, B["boss"][0])
            card = sc.comment_card(self.s["comment"], 40, 820)
            k = 0.5 + 0.5 * u
            card = card.resize((int(card.width * k), int(card.height * k)), Image.LANCZOS)
            cx, cy = 1480 - 380 * u, 590 - 420 * u
            ca._put(im, ca._fade(card, min(u * 1.5, 1) * out), (cx - card.width / 2, cy - card.height / 2))
            pic = visions.draw(self.s.get("vision", "reader_smile"), max(0.0, t - B["feel"][0]))
            if pic is not None:
                v = sc.seg(t, B["feel"][0] + 0.3, B["feel"][0] + 0.9) * out
                cloud_around(im, pic, x - 120, self.DESK - 420, v)
        # 来电卡片 + 电话里的声音
        self.calls(im, t, B, hand)
        if lights < 1:                               # 关灯：整体暗下来
            im = Image.blend(im, Image.new("RGBA", im.size, (8, 10, 20, 255)), 0.55 * (1 - lights))
        return im

    def calls(self, im, t, B, hand):
        b0, b1 = B["boss"]
        if b0 + 0.1 * (b1 - b0) < t < b1 + 0.4:
            u = sc.seg(t, b0, b1)
            ended = u >= 0.88
            mad = ca.Pose(eyes="narrow", mouth="open", dx=0.5 * math.sin(t * 25), fx=[("steam", t / 0.7)])
            a = sc.seg(t, b0 + 0.1 * (b1 - b0), b0 + 0.18 * (b1 - b0)) * (1 - sc.seg(t, b1, b1 + 0.4))
            secs = max(0, int(t - b0 - 0.5))
            sc.call_card(im, 1360, 60, self.s["boss"]["name"], "通话已结束" if ended else f"通话中 00:{secs:02d}",
                         sc.BOSS, mad, a, ended=ended)
            if hand and not ended and u > 0.2:       # 乱码气泡从手机里一个个冒出来
                k = int((t - b0) / 0.45)
                for j in range(3):
                    i = k - j
                    if i < 0:
                        continue
                    age = (t - b0) - i * 0.45
                    if age > 1.3:
                        continue
                    line = self.boss_lines[i % len(self.boss_lines)]
                    ox = hand[0] + 20 + (i % 3) * 60
                    oy = hand[1] - 120 - age * 120 - (i % 2) * 40
                    sc.bubble(im, ox, oy, line, 30 + (i % 2) * 6, 1 - age / 1.3, (230, 60, 60), (255, 255, 255),
                              jag=True, max_w=420)
            if ended and hand:
                sc.bubble(im, hand[0] + 30, hand[1] - 120, "嘟——嘟——", 26, 0.9, (60, 64, 80), (220, 220, 230))
        p0, p1 = B["partner"]
        if p0 + 0.08 * (p1 - p0) < t < B["pull"][0] + 0.6:
            a = sc.seg(t, p0 + 0.08 * (p1 - p0), p0 + 0.16 * (p1 - p0)) * (1 - sc.seg(t, B["pull"][0], B["pull"][0] + 0.6))
            gf = ca.Pose(eyes="heart", mouth="smile", blush=True, lean=4 * math.sin(t * 2), fx=[("heart", t / 1.3)])
            secs = max(0, int(t - p0 - 0.4))
            sc.call_card(im, 1360, 60, self.s["partner"]["name"], f"通话中 00:{secs:02d}", ca.FEMALE, gf, a,
                         accent=(240, 110, 150), heart=True)
            u = sc.seg(t, p0, p1)
            if hand and u > 0.18:
                v = sc.seg(t, p0 + 0.18 * (p1 - p0), p0 + 0.3 * (p1 - p0)) * a
                sc.bubble(im, hand[0] - 40, hand[1] - 250, self.s["partner"]["line"], 32, v, (255, 214, 226),
                          (120, 40, 70), max_w=520)
                for j in range(2):                   # 电话里飘出小爱心
                    w_ = (t * 0.7 + j / 2) % 1
                    visions.heart(im, hand[0] + 20 + 30 * j, hand[1] - 40 - w_ * 80, 4, (1 - w_) * v)


# ====================================================================== 内景变体「在吗」（《最佳损友》）
WECHAT_GREEN = (149, 236, 105)


class ChatOffice(Office):
    """同一个工位，故事换成：手机亮了 → 老朋友的朋友圈 → 聊天框（两条旧消息，打字又删掉）→ 想起一条评论，
    交给扭蛋机决定 → 拉杆，扭蛋里开出一张唱片 → 拨片开头。他不下班，扣下手机闭眼听歌。
    脚本：scene = "chat"，beats 用 comment / tilt / feed / chat / think / pull / flick / center / hold。"""
    PHONE = (1290, 50, 1870, 900)                   # 右边放大的手机屏幕

    def __init__(self, script: dict):
        super().__init__(script)
        self.fr = script["friend"]
        self.f_ui, self.f_ui_s, self.f_head = sc.font(32, False), sc.font(24, False), sc.font(36)

    def boy(self, t: float, B: dict):
        x = self.BOY_X
        hand = (x + 120, self.DESK - 120)
        if t < B["feed"][0]:                         # 读评论：盯着屏幕
            scan = ["look_r", "open", "look_r"][int(t / 0.5) % 3]
            return ca.Pose(eyes=scan if (t % 2.4) > 0.12 else "blink", lean=2 * math.sin(t * 1.4)), x, None
        if t < B["chat"][0]:                         # 手机亮了：拿起来看朋友圈，看了很久
            u = sc.seg(t, *B["feed"])
            if u < 0.15:
                return ca.Pose(eyes="look_r", mouth="o"), x, None
            return ca.Pose(eyes="down" if u < 0.7 else "sad", mouth="closed", arm_r="out", lean=-2), x, hand
        if t < B["think"][0]:                        # 打字又删掉
            u = sc.seg(t, *B["chat"])
            deleting = 0.55 < u < 0.66 or 0.86 < u < 0.95
            return (ca.Pose(eyes="narrow" if deleting else "down", mouth="frown" if deleting else "closed", arm_r="out",
                            lean=-3, dx=0.4 * math.sin(t * 22) if 0.15 < u < 0.45 or 0.66 < u < 0.8 else 0,
                            fx=[("sweat", t / 1.1)] if u > 0.86 else []), x, hand)
        if t < B["pull"][0]:                         # 想起那条评论 → 看向扭蛋机
            u = sc.seg(t, *B["think"])
            return ca.Pose(eyes="look_up" if u < 0.6 else "look_l", mouth="o" if u < 0.6 else "smile",
                           lean=-4 * sc.ease((u - 0.6) / 0.4)), x, None
        if t < B["flick"][0]:                        # 拉扭蛋机的摇杆
            u = sc.seg(t, *B["pull"])
            k = math.sin(min(u / 0.7, 1) * math.pi * 0.5) if u < 0.7 else 1 - (u - 0.7) / 0.3 * 0.4
            opened = u > 0.75
            return (ca.Pose(eyes="wide" if 0.6 < u < 0.75 else ("happy" if opened else "closed"),
                            mouth="smile" if u < 0.6 or opened else "o", blush=opened, lean=-10 - 8 * k,
                            arm_l="out", squash=1 - 0.06 * k, fx=[("spark", t)] if opened else []),
                    x - 40 * sc.ease(u / 0.3), None)
        # 笑了，把手机扣在桌上，闭眼跟着歌轻轻晃
        return (ca.Pose(eyes="closed", mouth="smile", blush=True, lean=4 * math.sin(t * 2.2),
                        fx=[("note", t / 1.6), ("note", t / 1.6 + 0.5)]), x - 40, None)

    # ---- 放大的手机屏幕：朋友圈 / 聊天
    def _screen(self, t: float, B: dict) -> Image.Image | None:
        x0, y0, x1, y1 = self.PHONE
        w, h = x1 - x0, y1 - y0
        feed = B["feed"][0] + 0.18 * (B["feed"][1] - B["feed"][0]) <= t < B["chat"][0]
        chat = B["chat"][0] <= t < B["think"][0] + 0.4
        if not (feed or chat):
            return None
        p = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(p)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 46, fill=(24, 24, 30))
        d.rounded_rectangle([14, 14, w - 15, h - 15], 36, fill=(237, 237, 237))
        d.rounded_rectangle([w / 2 - 60, 26, w / 2 + 60, 50], 12, fill=(24, 24, 30))      # 刘海
        if feed:
            self._feed(p, d, t, w, h)
        else:
            self._chat(p, d, t, B, w, h)
        return p

    def _feed(self, p, d, t, w, h):
        d.rectangle([14, 60, w - 15, 130], fill=(250, 250, 250))
        d.text((w / 2, 96), "朋友圈", font=self.f_head, fill=(30, 30, 30), anchor="mm")
        p.alpha_composite(sc.avatar(ca.OLD_FRIEND, ca.Pose(eyes="happy", mouth="grin"), 90), (30, 156))
        d.text((136, 160), self.fr["name"], font=self.f_head, fill=(87, 107, 149))
        d.text((136, 214), self.s["feed"]["text"], font=self.f_ui, fill=(30, 30, 30))
        ph = Image.new("RGBA", (330, 250), (40, 34, 52, 255))      # 照片：一群他不认识的小人围着烤炉撸串
        dp = ImageDraw.Draw(ph)
        for k in range(14):
            sx, sy = (k * 53) % 330, 10 + (k * 37) % 80
            dp.rectangle([sx, sy, sx + 2, sy + 2], fill=(255, 230, 160))                    # 小彩灯
        dp.rectangle([110, 168, 230, 186], fill=(70, 70, 80))                              # 烤炉
        for k in range(5):
            dp.line([118 + k * 24, 164, 132 + k * 24, 150], fill=(200, 120, 70), width=5)
        looks = [ca.recolor(c) for c in ((200, 170, 120), (170, 160, 190), (230, 160, 170))]
        for i, (lx, look) in enumerate(zip((60, 280, 100), looks)):
            sc.person(ph, look, ca.Pose(eyes="happy", mouth="grin", arm_l="up" if i % 2 else "down", arm_r="up",
                                        hop=1 * abs(math.sin(t * 3 + i))), lx if i < 2 else 250, 238, 3)
        sc.person(ph, ca.OLD_FRIEND, ca.Pose(eyes="happy", mouth="grin", arm_r="up", arm_l="up"), 170, 238, 3)
        p.alpha_composite(ph.resize((410, 310), Image.NEAREST), (136, 270))
        d.text((136, 604), "2 小时前", font=self.f_ui_s, fill=(150, 150, 150))
        d.text((w - 46, 604), "12", font=self.f_ui_s, fill=(87, 107, 149), anchor="ra")
        p.alpha_composite(ca._pixel(ca.HEART_SHAPE, (87, 107, 149), 3), (w - 100, 608))      # 点赞的小爱心

    def _bubble(self, d, x, y, text, mine: bool, w_max: int):
        lines, cur = [], ""
        for ch in text:
            if d.textlength(cur + ch, font=self.f_ui) > w_max:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
        tw = max(d.textlength(ln, font=self.f_ui) for ln in lines)
        bw, bh = tw + 40, len(lines) * 44 + 26
        bx = x - bw if mine else x
        d.rounded_rectangle([bx, y, bx + bw, y + bh], 10, fill=WECHAT_GREEN if mine else (255, 255, 255))
        for k, ln in enumerate(lines):
            d.text((bx + 20, y + 12 + k * 44), ln, font=self.f_ui, fill=(20, 20, 20))
        return bh

    def _chat(self, p, d, t, B, w, h):
        c = self.s["chat"]
        d.rectangle([14, 60, w - 15, 130], fill=(237, 237, 237))
        d.text((44, 96), "‹", font=sc.font(48, False), fill=(30, 30, 30), anchor="lm")
        d.text((w / 2, 96), self.fr["name"], font=self.f_head, fill=(30, 30, 30), anchor="mm")
        d.line([14, 130, w - 15, 130], fill=(214, 214, 214), width=2)
        y = 160
        for msg in c["history"]:
            d.text((w / 2, y + 12), msg["date"], font=self.f_ui_s, fill=(160, 160, 160), anchor="mm")
            y += 44
            mine = msg["from"] == "me"
            look = ca.MALE if mine else ca.OLD_FRIEND
            av = sc.avatar(look, ca.Pose(eyes="happy" if not mine else "open", mouth="smile"), 72)
            p.alpha_composite(av, (w - 100 if mine else 28, int(y)))
            bh = self._bubble(d, w - 116 if mine else 116, y, msg["text"], mine, w - 250)
            y += max(bh, 72) + 30
        # 输入框：打字 → 删掉 → 再打「在吗」→ 又删掉，只剩光标在闪
        u = sc.seg(t, *B["chat"])
        first, second = c["drafts"]
        typed = ""
        for a, b, txt, mode in ((0.15, 0.45, first, "type"), (0.45, 0.55, first, "hold"), (0.55, 0.65, first, "del"),
                                (0.65, 0.8, second, "type"), (0.8, 0.86, second, "hold"), (0.86, 0.95, second, "del")):
            if a <= u < b:
                k = (u - a) / (b - a)
                typed = txt[:int(round(len(txt) * k))] if mode == "type" else (
                    txt if mode == "hold" else txt[:int(round(len(txt) * (1 - k)))])
        iy = h - 130
        d.rectangle([14, iy - 16, w - 15, h - 40], fill=(246, 246, 246))
        d.rounded_rectangle([36, iy, w - 140, iy + 60], 8, fill=(255, 255, 255))
        d.text((52, iy + 30), typed, font=self.f_ui, fill=(20, 20, 20), anchor="lm")
        if int(t / 0.45) % 2 == 0:
            cx = 54 + d.textlength(typed, font=self.f_ui)
            d.line([cx, iy + 14, cx, iy + 46], fill=(30, 180, 60), width=3)
        d.rounded_rectangle([w - 124, iy + 6, w - 36, iy + 54], 8, fill=(7, 193, 96) if typed else (200, 200, 200))
        d.text((w - 80, iy + 30), "发送", font=self.f_ui_s, fill=(255, 255, 255), anchor="mm")

    def frame(self, t: float, B: dict, cover_pic=None) -> Image.Image:
        im = self.bg.copy().convert("RGBA")
        sc.stars(im, t, 25, seed=9, y_max=330)
        d = ImageDraw.Draw(im)
        sc.lamp(im, 820, self.DESK, 1.0)
        sc.monitor(im, 1300, 470, 360, 230, t, 1.0)
        pose, x, hand = self.boy(t, B)
        sc.person(im, ca.MALE, pose, x, self.DESK + 40, 8)
        sc.desk(d, 760, 1800, self.DESK)
        pull = sc.seg(t, *B["pull"])
        lever = math.sin(min(pull / 0.7, 1) * math.pi * 0.5) * (1 - sc.seg(t, B["flick"][0], B["flick"][0] + 0.5))
        think_end = B["think"][0] + 0.6 * (B["think"][1] - B["think"][0]) < t < B["pull"][0]
        shake = 1.0 if think_end or 0.3 < pull < 1.0 else 0.0
        drop_t0 = B["pull"][0] + 0.45 * (B["pull"][1] - B["pull"][0])
        drop = min((t - drop_t0) / 0.6, 1.0) if pull > 0.45 else -1.0
        opened = drop >= 1.0
        sc.gacha(im, 930, self.DESK, t, shake, lever=lever, drop=-1.0 if opened else drop)
        if shake:
            visions.spark(im, 960, self.DESK - 260, 4, 0.5 + 0.5 * math.sin(t * 5))
        if opened:                                   # 扭蛋打开：两半分开，里面升起一张唱片
            k = sc.ease((t - drop_t0 - 0.6) / 0.7)
            gone = sc.seg(t, B["center"][0] - 0.4, B["center"][0])
            bx, by = 960, self.DESK - 12
            d2 = ImageDraw.Draw(im, "RGBA")
            for side in (-1, 1):
                ox = bx + side * 22 * k
                d2.chord([ox - 13, by - 13, ox + 13, by + 13], 180 if side < 0 else 0, 360 if side < 0 else 180,
                         fill=(240, 90, 110) if side < 0 else (250, 250, 250))
            record(im, bx, by - 30 - 330 * k, 46 + 40 * k, self.s["record_label"], t, 1 - gone)
        # 手机：在桌上响 → 拿在手里 → 扣在桌上
        ring = B["feed"][0] < t < B["feed"][0] + 0.15 * (B["feed"][1] - B["feed"][0])
        if hand:
            sc.phone(im, hand[0], hand[1], ang=-12, t=t, screen=(237, 237, 237))
        elif t < B["feed"][0] + 0.15 * (B["feed"][1] - B["feed"][0]):
            sc.phone(im, 1240, self.DESK - 6, ang=90, ring=1.0 if ring else 0.0, t=t, screen=(60, 120, 200))
        else:
            sc.phone(im, 1240, self.DESK - 6, ang=90, t=t, screen=(30, 30, 38))
        scr = self._screen(t, B)                     # 放大的手机屏幕（淡入淡出）
        if scr is not None:
            a = min(sc.seg(t, B["feed"][0] + 0.18 * (B["feed"][1] - B["feed"][0]),
                           B["feed"][0] + 0.3 * (B["feed"][1] - B["feed"][0])),
                    1 - sc.seg(t, B["think"][0], B["think"][0] + 0.4))
            sh = Image.new("RGBA", (scr.width + 80, scr.height + 80), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle([40, 50, scr.width + 40, scr.height + 50], 46, fill=(0, 0, 0, 120))
            ca._put(im, ca._fade(sh.filter(ImageFilter.GaussianBlur(18)), a), (self.PHONE[0] - 40, self.PHONE[1] - 40))
            ca._put(im, ca._fade(scr, a), self.PHONE[:2])
        # 想起的那条评论（浮在左上，头顶想象云里是扭蛋机在发光）
        th0, th1 = B["think"]
        if th0 < t < B["pull"][0] + 0.4:
            a = sc.seg(t, th0, th0 + 0.6) * (1 - sc.seg(t, B["pull"][0], B["pull"][0] + 0.4))
            card = sc.comment_card(self.s["think"]["comment"], 38, 760)
            ca._put(im, ca._fade(card, a), (x - card.width / 2 - 200, 140 + 20 * (1 - a)))
            v = sc.seg(t, th0 + 0.6 * (th1 - th0), th0 + 0.75 * (th1 - th0)) * a
            if v > 0:
                sc.bubble(im, x - 60, self.DESK - 360, self.s["think"]["line"], 32, v, (255, 255, 255), (60, 40, 40),
                          max_w=420)
        return im


def record(im: Image.Image, cx, cy, r, label: str, t: float, a: float = 1.0) -> None:
    """一张小唱片：黑胶纹路 + 红色标签 + 下面的歌名（慢慢转、发光）。"""
    if a <= 0.01:
        return
    s = int(r * 2 + 8)
    p = Image.new("RGBA", (s, s + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    c = s / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=(22, 22, 26))
    for k in range(3):
        rr = r * (0.55 + 0.13 * k)
        d.arc([c - rr, c - rr, c + rr, c + rr], int(t * 90) % 360, int(t * 90) % 360 + 70, fill=(80, 80, 90), width=2)
    d.ellipse([c - r * 0.36, c - r * 0.36, c + r * 0.36, c + r * 0.36], fill=(198, 30, 38))
    d.ellipse([c - 3, c - 3, c + 3, c + 3], fill=(240, 240, 240))
    d.text((c, s + 26), label, font=sc.font(26), fill=(255, 246, 230), anchor="mm", stroke_width=4,
           stroke_fill=(20, 16, 24))
    ca._put(im, ca._fade(p, a), (cx - c, cy - c))
    visions.spark(im, cx + r * 0.8, cy - r, 3, a * (0.5 + 0.5 * math.sin(t * 5)))


SCENES = {"office": Office, "chat": ChatOffice}


def cloud_around(im: Image.Image, pic: Image.Image, cx: float, cy: float, a: float) -> None:
    """简化的想象云朵：白色描边的云 + 里面的画面（只在云里显示）。"""
    if a <= 0.02:
        return
    w, h = 460, 290
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([20, 40, w - 20, h - 30], fill=255)
    for k in range(11):
        ang = k / 11 * 2 * math.pi
        x, y = w / 2 + (w / 2 - 60) * math.cos(ang), h / 2 + 5 + (h / 2 - 56) * math.sin(ang)
        r = 54 if math.sin(ang) < 0.3 else 44
        d.ellipse([x - r, y - r, x + r, y + r], fill=255)
    from PIL import ImageChops, ImageFilter
    solid = m.point(lambda v: 255 if v > 128 else 0)
    ring = ImageChops.subtract(solid, solid.filter(ImageFilter.MinFilter(7))).point(lambda v: int(v * 0.95 * a))
    white = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    white.putalpha(ring)
    pic = pic.resize((int(pic.width * 1.3), int(pic.height * 1.3)), Image.NEAREST)
    box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    box.alpha_composite(pic, (int(w / 2 - pic.width / 2), int(h / 2 - pic.height / 2 + 6)))
    box.putalpha(ImageChops.multiply(box.getchannel("A"), solid.filter(ImageFilter.MinFilter(9))))
    ca._put(im, ca._fade(box, a), (cx - w / 2, cy - h / 2))
    ca._put(im, white, (cx - w / 2, cy - h / 2))
    dd = ImageDraw.Draw(im, "RGBA")
    for i, (dx, dy, r) in enumerate(((60, 210, 7), (40, 175, 10), (12, 140, 13))):
        dd.ellipse([cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r], outline=(255, 255, 255, int(230 * a)), width=3)


# ====================================================================== 合成整段开头
class Opening:
    PANEL = (70, 110, 930, 910)                     # 左边拨片动画的区域（半透明深色底，不用图片虚化背景）

    def __init__(self, script: dict, final: Path, others: list[Path], seconds: float, fps: int, title: str,
                 artist: str):
        self.s, self.S, self.fps = script, seconds, fps
        beats = dict(script["beats"])
        if "pan" in beats and "flick" not in beats:  # v1 脚本：最后一段 pan 拆成 拉摇杆 / 拨片 / 封面到中间
            a, b = beats.pop("pan")
            beats.update(pull=[a - 0.04, a], flick=[a, b - 0.06], center=[b - 0.06, b])
        self.B = {k: [a * seconds, b * seconds] for k, (a, b) in beats.items()}
        self.ext, self.office = Exterior(), SCENES[script.get("scene", "office")](script)
        main = Image.open(final)
        imgs = [Image.open(p) for p in others]
        while len(imgs) < 5:
            imgs.append(flick_intro.variant(main, len(imgs)))
        x0, y0, x1, y1 = self.PANEL
        f0 = self.B["flick"][0]
        self.flick_t0 = f0
        self.fl = flick_intro.Flick(imgs[:5] + [main], x1 - x0, H, fps, seconds - f0, "", "", fade_in=False)
        self.title, self.artist = title, artist
        self.card = sc.comment_card(script["comment"])
        self.f_title, self.f_artist = sc.font(58), sc.font(30, False)
        self.cover = self.fl.cards[-1]
        self.size = self.fl.size                      # 封面最后的边长（和正片转场接得上）
        self.left_c = (x0 + self.fl.cx, self.fl.cy)   # 拨片动画里封面停的位置
        self.mid_c = (W / 2, H * 0.455)               # 移到画面中间

    # ---- 拨片动画的卡片层（透明背景，只有卡片和阴影）
    def _cards(self, t: float, skip_last: bool) -> Image.Image:
        fl = self.fl
        x0, y0, x1, y1 = self.PANEL
        layer = Image.new("RGBA", (x1 - x0, H), (0, 0, 0, 0))
        p0, p1 = fl.pos(t), fl.pos(t + 1 / self.fps)
        k = int(min(6, max(1, math.ceil(abs(p1 - p0) * fl.spacing / 18))))   # 快速滑动时几张叠在一起做拖影
        acc = None
        for j in range(k):
            tj = t + j / (k * self.fps)
            img = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            pos = fl.pos(tj)
            settle = min(1.0, max(0.0, (tj - fl.t_done) / 0.6))
            for i in sorted(range(fl.n), key=lambda i: -abs(pos - i)):
                dlt = pos - i
                if abs(dlt) > 2.2 or (skip_last and i == fl.n - 1):
                    continue
                d = min(abs(dlt), 1.6)
                scale = 1 - 0.16 * d
                alpha = (1 - 0.55 * d / 1.6) * (1 - settle if i != fl.n - 1 else 1)
                if alpha <= 0.01:
                    continue
                sz = max(8, int(fl.size * scale))
                y = fl.cy + dlt * fl.spacing
                card = fl.cards[i].resize((sz, sz), Image.BILINEAR)
                sh = fl.shadow.resize((int(fl.shadow.width * scale), int(fl.shadow.height * scale)), Image.BILINEAR)
                off = int(60 * scale)
                shade = Image.new("RGBA", sh.size, (0, 0, 0, 0))
                shade.putalpha(sh.point(lambda v, a=alpha: int(v * a)))
                ca._put(img, shade, (fl.cx - sz / 2 - off, y - sz / 2 - off + 18 * scale))
                ca._put(img, ca._fade(card, alpha), (fl.cx - sz / 2, y - sz / 2))
            arr = np.asarray(img, np.float32)
            acc = arr if acc is None else acc + arr
        layer = Image.fromarray((acc / k).astype(np.uint8))
        m = Image.new("L", layer.size, 0)            # 只在面板范围里显示（卡片从面板上下边缘滑进滑出）
        ImageDraw.Draw(m).rounded_rectangle([0, y0, x1 - x0, y1], 36, fill=255)
        from PIL import ImageChops
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), m.filter(ImageFilter.GaussianBlur(10))))
        return layer

    def _title(self, im: Image.Image, t: float) -> None:
        """歌名歌手：先在左上角，封面移到中间时一起移到封面下面，最后淡出交给音轨画面。"""
        a = sc.seg(t, 1.0, 1.8) * (1 - sc.seg(t, self.S - 0.3, self.S - 0.02))
        if a <= 0.01:
            return
        d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        tw = max(d0.textlength(self.title, font=self.f_title), d0.textlength(self.artist, font=self.f_artist))
        u = sc.seg(t, *self.B["center"])
        x = 70 + (W / 2 - tw / 2 - 70) * u
        y = 56 + (self.mid_c[1] + self.size / 2 + 36 - 56) * u
        layer = Image.new("RGBA", (int(tw) + 40, 120), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        ax = (tw / 2 - d0.textlength(self.title, font=self.f_title) / 2) * u
        ax2 = (tw / 2 - d0.textlength(self.artist, font=self.f_artist) / 2) * u
        for col, sw in (((10, 10, 18), 4), ((250, 246, 240), 0)):     # 深色描边：压在亮的地方也看得清
            dl.text((ax + 4, 2), self.title, font=self.f_title, fill=col, stroke_width=sw, stroke_fill=(10, 10, 18))
            dl.text((ax2 + 4, 72), self.artist, font=self.f_artist, fill=col if sw else (210, 206, 216),
                    stroke_width=sw, stroke_fill=(10, 10, 18))
        ca._put(im, ca._fade(layer, a), (x, y))

    def background(self, t: float) -> Image.Image:
        """不含拨片卡片和歌名的画面（外景 / 办公室），最后一段逐渐压暗。"""
        B = self.B
        t0, t1 = B["tilt"]
        if t < t1:
            u = sc.seg(t, t0, t1)
            zoom = sc.seg(t, t1 - 0.9, t1)
            im = self.ext.frame(t, u, zoom).convert("RGBA")
            if zoom > 0:                             # 推进窗户时淡入办公室
                inner = self.office.frame(t, B)
                im = Image.blend(im, inner, sc.ease((zoom - 0.4) / 0.6))
        else:
            im = self.office.frame(t, B)
        dim = sc.seg(t, *B["center"])
        if dim > 0:                                  # 封面移到中间时，办公室慢慢暗下去
            im = Image.blend(im, Image.new("RGBA", im.size, (6, 8, 16, 255)), 0.5 * dim)
        return im

    def frame(self, t: float) -> Image.Image:
        B = self.B
        im = self.background(t)
        c0, c1 = B["comment"]                        # 开头那条评论
        fi = float(self.s.get("comment_fade_in", 0.8))          # 0：第一帧就完整显示（学习笔记：开头 2 秒留人）
        a = (sc.seg(t, c0, c0 + fi) if fi > 0 else 1.0) * (1 - sc.seg(t, c1 - 0.6, c1))
        if a > 0.01:
            card = self.card
            k = 0.94 + 0.06 * sc.ease(t / 2) if fi > 0 else 1.0
            card = card.resize((int(card.width * k), int(card.height * k)), Image.LANCZOS)
            ca._put(im, ca._fade(card, a), (W / 2 - card.width / 2, H * 0.56 - card.height / 2 - 30 * (1 - a)))
        self._title(im, t)                           # 歌名画在卡片下面：移到封面下方的路上从封面后面穿过
        f0, f1 = B["flick"]
        if t >= f0:                                  # 拉下摇杆：左边浮现拨片动画（半透明深色底，盖在画面上层）
            x0, y0, x1, y1 = self.PANEL
            show = sc.seg(t, f0, f0 + 0.4) * (1 - sc.seg(t, *B["center"]))
            if show > 0.01:
                panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(panel).rounded_rectangle([x0, y0, x1, y1], 36, fill=(10, 12, 24, int(120 * show)),
                                                        outline=(255, 255, 255, int(40 * show)), width=2)
                im.alpha_composite(panel)
            moving = t >= B["center"][0]
            cards = self._cards(t - f0, skip_last=moving)
            cards = ca._fade(cards, min(1.0, sc.seg(t, f0, f0 + 0.3)))
            if moving:                               # 其他卡片随面板淡出
                cards = ca._fade(cards, 1 - sc.seg(t, *B["center"]))
            im.alpha_composite(cards, (x0, 0))
            if moving:                               # 封面停稳后从左边移到画面正中
                u = sc.seg(t, *B["center"])
                cx = self.left_c[0] + (self.mid_c[0] - self.left_c[0]) * u
                cy = self.left_c[1] + (self.mid_c[1] - self.left_c[1]) * u - math.sin(math.pi * u) * 30
                fl = self.fl
                off = 60
                shade = Image.new("RGBA", fl.shadow.size, (0, 0, 0, 0))
                shade.putalpha(fl.shadow)
                ca._put(im, shade, (cx - self.size / 2 - off, cy - self.size / 2 - off + 18))
                ca._put(im, self.cover, (cx - self.size / 2, cy - self.size / 2))
        return im.convert("RGB")

    def sound(self, tail: float) -> np.ndarray:
        n = int((self.S + tail) * sfx.SR)
        buf = np.zeros(n, np.float32)
        B = self.B
        sfx._add(buf, B["flick"][0], self.fl.sound(tail, None) * 0.9)
        sfx._add(buf, B["pull"][0] + 0.35 * (B["pull"][1] - B["pull"][0]), sfx.thump(0.55))      # 摇杆拉到底
        sfx._add(buf, B["pull"][0] + 0.6 * (B["pull"][1] - B["pull"][0]), _tone(1760, 0.25, 0.25))   # 扭蛋掉出来
        if self.s.get("scene") == "chat":
            return self._chat_sound(buf)
        sfx._add(buf, B["boss"][0] + 0.05, ringtone(0.14 * (B["boss"][1] - B["boss"][0]), 0.35))
        sfx._add(buf, B["boss"][0] + 0.2 * (B["boss"][1] - B["boss"][0]),
                 garble(0.66 * (B["boss"][1] - B["boss"][0]), angry=True) * 0.32)
        sfx._add(buf, B["boss"][0] + 0.88 * (B["boss"][1] - B["boss"][0]), hangup() * 0.3)
        sfx._add(buf, B["partner"][0] + 0.03, ringtone(0.12 * (B["partner"][1] - B["partner"][0]), 0.25, soft=True))
        sfx._add(buf, B["partner"][0] + 0.2 * (B["partner"][1] - B["partner"][0]),
                 garble(0.4 * (B["partner"][1] - B["partner"][0]), angry=False) * 0.16)
        return buf


    def _chat_sound(self, buf: np.ndarray) -> np.ndarray:
        """「在吗」：消息提示音、打字 / 删字的键盘声、扭蛋打开的叮。"""
        B = self.B
        f0, f1 = B["feed"]
        sfx._add(buf, f0 + 0.05, (_tone(1568, 0.12, 0.25) + np.pad(_tone(2093, 0.12, 0.2), (int(0.1 * sfx.SR), 0))[
            :int(0.12 * sfx.SR)]))
        c0, c1 = B["chat"]
        L = c1 - c0
        first, second = self.s["chat"]["drafts"]
        for a, b, n in ((0.15, 0.45, len(first)), (0.55, 0.65, len(first)), (0.65, 0.8, len(second)),
                        (0.86, 0.95, len(second))):
            for i in range(n):
                sfx._add(buf, c0 + L * (a + (b - a) * i / max(n, 1)), tap(0.12 if (a, b) != (0.55, 0.65) else 0.09))
        p0, p1 = B["pull"]
        sfx._add(buf, p0 + 0.45 * (p1 - p0) + 0.62, _tone(2349, 0.4, 0.22))           # 扭蛋打开：叮
        return buf


# ---------------------------------------------------------------- 声音：铃声、电话里的乱码声、挂断音
def tap(amp: float = 0.12) -> np.ndarray:
    """手机键盘的一下轻敲。"""
    n = int(0.03 * sfx.SR)
    rnd = np.random.default_rng(5)
    env = np.exp(-np.arange(n) / sfx.SR * 160)
    return (sfx._band(rnd.standard_normal(n).astype(np.float32), 1500, 6000) * env * amp).astype(np.float32)

def _tone(f: float, dur: float, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(dur * sfx.SR)) / sfx.SR
    env = np.minimum(1, t / 0.01) * np.exp(-t * 6)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * env * amp


def ringtone(dur: float, amp: float = 0.3, soft: bool = False) -> np.ndarray:
    notes = [1047, 1319, 1568, 1319] if soft else [1319, 1047, 1319, 1047]
    out = np.zeros(int(dur * sfx.SR) + sfx.SR, np.float32)
    k, t = 0, 0.0
    while t < dur:
        sfx._add(out, t, _tone(notes[k % 4], 0.22, amp))
        t += 0.16
        k += 1
        if k % 4 == 0:
            t += 0.25
    return out


def garble(dur: float, angry: bool) -> np.ndarray:
    """电话里听不清的说话声：一串快速变调的音节，经过「电话」带通。"""
    rnd = np.random.default_rng(3 if angry else 8)
    n = int(dur * sfx.SR)
    out = np.zeros(n, np.float32)
    t = 0.0
    while t < dur - 0.1:
        sl = rnd.uniform(0.06, 0.16)
        f0 = rnd.uniform(220, 420) if angry else rnd.uniform(420, 620)
        tt = np.arange(int(sl * sfx.SR)) / sfx.SR
        f = f0 * (1 + 0.25 * np.sin(2 * np.pi * rnd.uniform(3, 8) * tt))
        ph = 2 * np.pi * np.cumsum(f) / sfx.SR
        syl = np.sign(np.sin(ph)) * 0.4 + np.sin(3 * ph) * 0.3
        syl *= np.sin(np.pi * tt / sl) ** 2
        sfx._add(out, t, syl.astype(np.float32))
        t += sl + rnd.uniform(0.0, 0.05 if angry else 0.12)
    return sfx._band(out, 400, 3000).astype(np.float32)


def hangup() -> np.ndarray:
    out = np.zeros(int(1.6 * sfx.SR), np.float32)
    for k in range(3):
        tt = np.arange(int(0.25 * sfx.SR)) / sfx.SR
        sfx._add(out, k * 0.45, (np.sin(2 * np.pi * 425 * tt) * 0.5).astype(np.float32))
    return out


def render(script: dict, final: Path, others: list[Path], out: Path, seconds: float, fps: int, title: str,
           artist: str, sfx_tail: float = 0.0, progress=None) -> dict:
    """渲染开头小剧场 → out（mp4）+ <out>_sfx.wav。返回值和 flick_intro.render 一样（音轨画面的转场接着用）。"""
    import imageio_ffmpeg
    op = Opening(script, final, others, seconds, fps, title, artist)
    writer = imageio_ffmpeg.write_frames(str(out), (W, H), fps=fps, codec="libx264", pix_fmt_out="yuv420p",
                                         quality=None, output_params=["-crf", "16", "-preset", "medium"],
                                         macro_block_size=1, ffmpeg_log_level="error")
    writer.send(None)
    n = round(seconds * fps)
    for f in range(n):
        writer.send(np.asarray(op.frame(f / fps)).tobytes())
        if progress and f % 30 == 0:
            progress(f, n)
    writer.close()
    # 正片的水墨转场从最后一帧接着演：背景 = 压暗的办公室（不含封面和歌名），封面在画面正中
    t_last = (n - 1) / fps
    last = op.frame(t_last)
    last.save(out.with_suffix(".jpg"), quality=92)
    last.save(out.with_name(out.stem + "_last.png"))
    bg_only = op.background(t_last).convert("RGB")
    first = {"last_frame": bg_only, "full": last, "card": op.cover, "card_center": op.mid_c, "card_size": op.size}
    wav = sfx.write_wav(out.with_name(out.stem + "_sfx.wav"), op.sound(sfx_tail))
    return {"video": out, "sfx": wav, "last_frame": bg_only, "full_last_frame": last, "card": op.cover,
            "card_center": op.mid_c, "card_size": op.size, "first": first}
