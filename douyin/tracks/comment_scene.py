"""评论故事的舞台：画面底部的「网易云评论」文件夹 + CC 小人读评论。

每条评论出现之前，小人走到文件夹旁 → 打开文件夹 → 抽出一张纸 → 举着读 → 把纸抛起来，纸飞到空中变成评论卡片
（卡片由 stage.CommentStory 画，起点就是这张纸）→ 小人按这条评论的情绪（mood）做动作；独白卡片时小人走到舞台中间。
尾声：剩下的评论卡片飞回文件夹，文件夹合上，小人抬头看最后一句话。
小人的动作来自 clawd_anim（每段动画也单独导出在 assets/clawd/animations/）。

两人模式（模板 cast: "duo"，duo_scene.py 组装）：小人缩小（scale 4）、舞台带变矮；评论卡片写了 vision 时，男生读完后
头顶冒出三个小圆点，展开成「想象云朵」（只有白色描边，里面透明，音轨照样看得见），云里浮现 visions.py 的画面；
尾声不再抬头，而是和唱歌的女生一起蹦跳着走到画面中间，向观众鞠躬（bow_finale）。
"""
import math
from dataclasses import replace

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import clawd_anim as ca
import daw
import visions

STAGE_BAND = 210                 # 底部舞台带高度（像素）
SCALE = 6                        # 小人像素格大小
WALK_SPEED = 600                 # 走路速度（像素/秒）
T_OPEN, T_PULL, T_TOSS = 0.5, 0.8, 0.7    # 从容时的时长；卡片来得快时按比例压缩（最多压到 45%）
READ_MIN, READ_MAX = 0.3, 1.6
EMOTE_MIN, SOLO_EMOTE_MIN = 1.3, 2.0     # 每条评论之后至少留给情绪动作的时间


def _ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class CommentFolder:
    """立体文件夹：后片 + 露出的纸边 + 前片（打开时向前下翻）。前片上是自己画的「红色圆形 + 白色音符」图标和
    「网易云评论」字样（不使用官方 logo 文件）。"""
    W, H = 250, 150

    def __init__(self, theme: dict, x: float, floor: float, k: float = 1.0):
        self.x, self.floor, self.k = x, floor, k   # 左下角；k：整体缩放（两人模式小一些）
        self.f = ImageFont.truetype(theme["font_cjk"], 22)
        self.back = self._back()
        self.front = self._front()
        if k != 1.0:
            self.back = self.back.resize((round(self.back.width * k), round(self.back.height * k)), Image.LANCZOS)
            self.front = self.front.resize((round(self.front.width * k), round(self.front.height * k)), Image.LANCZOS)
            self.W, self.H = round(self.W * k), round(self.H * k)

    def _back(self) -> Image.Image:
        w, h = self.W, self.H
        im = Image.new("RGBA", (w + 20, h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([10, 20, 10 + w * 0.42, 44], radius=8, fill=(160, 32, 40, 255))      # 标签页
        d.rounded_rectangle([10, 32, 10 + w, 32 + h], radius=12, fill=(176, 36, 44, 255))
        for k, dx in enumerate((26, 60, 104)):                                                  # 露出的纸
            d.rectangle([10 + dx, 18 - k * 4, 10 + dx + 110, 32 + 30], fill=(250, 247, 240, 255),
                        outline=(210, 204, 194, 255))
            for j in range(3):
                d.line([16 + dx, 26 - k * 4 + j * 8, 10 + dx + 96, 26 - k * 4 + j * 8], fill=(180, 174, 164, 255), width=2)
        return im

    def _front(self) -> Image.Image:
        w, h = self.W, int(self.H * 0.78)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=12, fill=(214, 52, 58, 255))
        d.rectangle([0, 0, w - 1, 6], fill=(236, 92, 96, 255))                                   # 顶边高光
        r = 26                                                                                  # 图标：红底白音符
        cx, cy = 40, h / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
        d.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4], fill=(198, 30, 38, 255))
        d.rectangle([cx + 2, cy - 14, cx + 6, cy + 8], fill=(255, 255, 255, 255))                # 音符杆
        d.ellipse([cx - 9, cy + 2, cx + 6, cy + 14], fill=(255, 255, 255, 255))                  # 音符头
        d.polygon([(cx + 6, cy - 14), (cx + 16, cy - 8), (cx + 6, cy - 6)], fill=(255, 255, 255, 255))
        d.text((cx + r + 14, cy), "网易云评论", font=self.f, fill=(255, 245, 240, 255), anchor="lm")
        return im

    def mouth(self) -> tuple[float, float]:
        """文件夹口（卡片飞回来的位置）。"""
        return self.x + self.W * 0.45, self.floor - self.H + 10

    def draw(self, im: Image.Image, open_amt: float) -> None:
        k = self.k
        bx, by = int(self.x - 10 * k), int(self.floor - self.H - 32 * k)
        sh = Image.new("L", (self.W + 60, 50), 0)                                               # 地面阴影
        ImageDraw.Draw(sh).ellipse([10, 10, self.W + 50, 40], fill=120)
        im.paste((0, 0, 0), (int(self.x - 30), int(self.floor - 22)), sh.filter(ImageFilter.GaussianBlur(8)))
        im.paste(self.back, (bx, by), self.back)
        # 前片：打开时以底边为轴向前翻倒（竖直方向压扁 + 往下移），露出里面的纸
        k = 1 - 0.75 * _ease(open_amt)
        fh = max(4, int(self.front.height * k))
        fr = self.front.resize((self.front.width, fh), Image.BILINEAR)
        if open_amt > 0.01:
            fr = Image.blend(fr, Image.new("RGBA", fr.size, (90, 10, 16, 255)), 0.25 * _ease(open_amt))
            fr.putalpha(self.front.getchannel("A").resize(fr.size))
        im.paste(fr, (int(self.x), int(self.floor - fh)), fr)


CLOUD_W, CLOUD_H = 500, 310
FLOOR_UP = 34                    # 地面离画面底边的距离


def duo_home(scale: int) -> float:
    """两人模式（缩小的小人和文件夹）里男生干活的位置。"""
    fk = 0.72 if scale < SCALE else 1.0
    return daw.W - round(CommentFolder.W * fk) - 70 - 150 * scale / SCALE


def cloud_box(x: float, scale: int) -> tuple[float, float, float, float]:
    """小人在 x 时，头顶想象云朵占的区域 (x0, y0, x1, y1)：在头顶偏左上方，不出画面。"""
    head_y = daw.H - FLOOR_UP - (ca.BH + ca.DEPTH + 6) * scale
    cx = min(max(x - 130, CLOUD_W / 2 + 20), daw.W - CLOUD_W / 2 - 20)
    cy = head_y - 70 - CLOUD_H / 2
    return cx - CLOUD_W / 2, cy - CLOUD_H / 2, cx + CLOUD_W / 2, cy + CLOUD_H / 2


class CommentScene:
    """舞台调度：根据 CommentStory 的卡片时间排出小人的动作表，并告诉卡片从哪里飞出、收拢到哪里。"""

    def __init__(self, story, theme: dict, view, band: int = STAGE_BAND, scale: int = SCALE,
                 visions_on: bool = False, bow_finale: dict | None = None, center_min: float = 0.0,
                 pace: float = 1.0):
        """scale：小人像素格大小；visions_on：读完评论冒想象云朵；bow_finale：{"walk": 出发时间, "x": 鞠躬位置}，
        给了就用「走到中间鞠躬」的尾声；center_min：独白时最多往左走到哪（两人模式左半边是女生和歌词）。"""
        self.story, self.view = story, view
        self.scale, self.visions_on, self.bow = scale, visions_on, bow_finale
        self.pace = pace                                      # >1：开文件夹、抽纸、读、抛、情绪动作都放慢（留足时间）
        k = scale / SCALE
        self.k = k
        self.floor = daw.H - FLOOR_UP
        fk = 0.72 if scale < SCALE else 1.0
        self.folder = CommentFolder(theme, daw.W - round(CommentFolder.W * fk) - 70, self.floor, fk)
        self.home = self.folder.x - 150 * k                   # 小人在文件夹左边干活
        self.center = max((daw.PLAYHEAD_X + self.home) / 2, center_min)   # 独白时走到舞台中间
        story.dim = False
        story.gather_to = self.folder.mouth()
        self.segs: list[dict] = []
        self._plan()

    # ---------------------------------------------------------------- 排动作表
    def _add(self, a, b, clip, x0, x1=None, **kw):
        if b - a > 0.01:
            self.segs.append({"a": a, "b": b, "clip": clip, "x0": x0, "x1": x0 if x1 is None else x1, **kw})

    def _plan(self):
        cards = sorted(self.story.cards, key=lambda c: c["t0"])
        x, free = self.home, 0.0                 # free：上一条评论的情绪动作至少要做到什么时候
        last_mood = None                         # 上一段情绪动作（时间不够时截短它）
        for c in cards:
            t0 = c["t0"]
            walk = abs(x - self.home) / WALK_SPEED
            room = t0 - free - walk              # 留给「开文件夹 → 抽 → 读 → 抛」的时间
            P = self.pace
            base = (T_OPEN + T_PULL + T_TOSS) * P
            k = min(1.0, max(0.45, (room - READ_MIN) / base))
            t_open, t_pull, t_toss = T_OPEN * P * k, T_PULL * P * k, T_TOSS * P * k
            read = min(READ_MAX * P, max(READ_MIN, room - base * k))
            s = t0 - walk - t_open - t_pull - read - t_toss
            if last_mood is not None:            # 上一段情绪动作做到这次出发为止（不够长也只能让位）
                last_mood["b"] = max(last_mood["a"] + 0.2, s)
                s = last_mood["b"]
            elif s > 0:
                self._add(0.0, s, "idle", x)
            t = s
            self._add(t, t + walk, "walk", x, self.home)
            t += walk
            self._add(t, t + t_open, "open_folder", self.home, open=True)
            t += t_open
            self._add(t, t + t_pull, "pull_card", self.home, open=True)
            t += t_pull
            read = max(0.1, t0 - t_toss - t)     # 前面被让位挤掉的时间从读里扣
            self._add(t, t + read, "read", self.home)
            self._add(t0 - t_toss, t0, "toss", self.home, paper=True)
            c["origin"] = (self.home, self.floor - 250 * self.k)   # 纸飞到这里，卡片从这里展开
            mood = c.get("mood") if c.get("mood") in ca.CLIPS else "nostalgic"
            end = c["t1"] + self.story.OUT
            if c.get("solo"):                                # 独白：走到舞台中间再表达情绪
                w = abs(self.center - self.home) / WALK_SPEED
                self._add(t0, t0 + w, "walk", self.home, self.center)
                self._add(t0 + w, end, mood, self.center, mood=True, card=c)
                x, free = self.center, t0 + w + SOLO_EMOTE_MIN * self.pace
            else:
                self._add(t0, end, mood, self.home, mood=True, card=c)
                x, free = self.home, t0 + EMOTE_MIN * self.pace
            last_mood = self.segs[-1]
        fin = self.story.finale
        if fin:                                              # 尾声：走回文件夹，打开，卡片飞回，合上，抬头
            g0 = fin["t0"] - self.story.GATHER
            for g in self.segs:
                g["b"] = min(g["b"], g0) if g["a"] < g0 else g["b"]
            self.segs = [g for g in self.segs if g["b"] - g["a"] > 0.01]
            last = self.segs[-1]["b"] if self.segs else 0.0
            if last < g0:
                self._add(last, g0, "idle", x)
            w = abs(x - self.home) / WALK_SPEED
            self._add(g0, g0 + w, "walk", x, self.home)
            self._add(g0 + w, fin["t0"], "open_folder", self.home, open=True)
            if self.bow:
                self._add(fin["t0"], self.bow["walk"], "hope", self.home)
            else:
                self._add(fin["t0"], fin["t1"] + 3, "hope", self.home)
        elif self.segs:
            end = self.bow["walk"] if self.bow else self.segs[-1]["b"] + 30
            self._add(self.segs[-1]["b"], end, "idle", x)
        if self.bow:                                         # 两人模式的尾声：蹦跳着走到中间，鞠躬
            a = self.bow["walk"]
            for g in self.segs:
                g["b"] = min(g["b"], a) if g["a"] < a else g["b"]
            self.segs = [g for g in self.segs if g["b"] - g["a"] > 0.01 and g["a"] < a]
            x0 = self.segs[-1]["x1"] if self.segs else self.home
            w = max(0.6, abs(x0 - self.bow["x"]) / (WALK_SPEED * 0.75))
            self._add(a, a + w, "walk_happy", x0, self.bow["x"], walk=True)
            if self.bow.get("exit"):                         # 走出画面（结尾小剧场里回家了）
                self._add(a + w, a + w + 60, "idle", self.bow["x"], hidden=True)
            else:
                self._add(a + w, a + w + 60, "bow", self.bow["x"])
        # 想象云朵：从这条评论的情绪动作开始，一直飘到下一条评论抛出来之前（他在下面接着干活），卡片写了 vision 才有；
        # 云朵停在想到它时小人头顶的位置，不跟着走
        self.clouds = []
        moods = [g for g in self.segs if g.get("card")]
        for i, g in enumerate(moods):
            c = g["card"]
            if not (self.visions_on and visions.VISIONS.get(c.get("vision"))):
                continue
            nxt = moods[i + 1]["card"]["t0"] - 0.75 if i + 1 < len(moods) else g["b"]
            if self.bow:
                nxt = min(nxt, self.bow["walk"])
            b = max(g["a"] + 1.6, nxt)
            self.clouds.append({"a": g["a"] + 0.2, "b": b, "x": g["x0"], "card": c})
        for k in range(len(self.clouds) - 1):                # 前后两朵不重叠
            self.clouds[k]["b"] = min(self.clouds[k]["b"], self.clouds[k + 1]["a"] - 0.05)

    # ---------------------------------------------------------------- 每帧
    def _seg(self, t):
        cur = None
        for g in self.segs:
            if g["a"] <= t < g["b"]:
                cur = g
        if cur is None:                                      # 第一张卡片前、最后之后：待机
            before = [g for g in self.segs if g["b"] <= t]
            x = before[-1]["x1"] if before else self.home
            return {"a": 0, "b": 1e9, "clip": "idle", "x0": x, "x1": x}
        return cur

    def _open(self, t) -> float:
        k = 0.0
        for g in self.segs:
            if g.get("open"):
                k = max(k, min(_ease((t - g["a"]) / 0.25), _ease((g["b"] + 0.25 - t) / 0.25)))
        return k

    def __call__(self, im: Image.Image, t: float) -> None:
        fz = self.story._focus(t)                            # 独白时压暗背景（舞台上的小人和文件夹不变暗）
        if fz > 0.01:
            im.paste(Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.32 * fz))
        self.folder.draw(im, self._open(t))
        g = self._seg(t)
        lt = t - g["a"]
        u = min(1.0, lt / max(g["b"] - g["a"], 1e-6))
        if g.get("hidden"):                                   # 走出画面了：只剩文件夹
            return
        walking = g["clip"] == "walk" or g.get("walk")
        x = g["x0"] + (g["x1"] - g["x0"]) * (u if walking else 1.0)
        clip = ca.CLIPS[g["clip"]]
        # 单次动作（开文件夹、抽纸、抛纸…）按这一段的长度整段播完（被压缩时播快一点）
        p = clip.pose(lt if clip.loop or g["clip"] == "bow" else u * clip.duration)
        if walking and g["x1"] < g["x0"]:
            p = replace(p, turn=-abs(p.turn), lean=-p.lean)
        S = self.scale
        canvas_sh = ca.shadow(p, S)
        im.paste((0, 0, 0), (int(x - canvas_sh.width / 2), int(self.floor - canvas_sh.height / 2)), canvas_sh)
        spr, (fx, fy) = ca.render(p, S)
        rgba = im.convert("RGBA")
        ca._put(rgba, spr, (x - fx, self.floor - fy))
        ca.draw_fx(rgba, p, (x, self.floor), S)
        for cl in getattr(self, "clouds", []):
            if cl["a"] <= t <= cl["b"]:
                self._cloud(rgba, cl, t, cl["x"])
        tt = g["b"] - g["a"] if g.get("paper") and self.pace != 1.0 else T_TOSS   # 放慢时按这一次抛纸的实际时长
        if g.get("paper") and lt > tt * 0.35:                # 抛出去的纸：转着飞向卡片展开的位置
            v = _ease((lt - tt * 0.35) / (tt * 0.65))
            ox, oy = x, self.floor - 120 * self.k
            tx, ty = x, self.floor - 250 * self.k
            px_, py_ = ox + (tx - ox) * v, oy + (ty - oy) * v - math.sin(v * math.pi) * 30
            paper = Image.new("RGBA", (46, 34), (250, 247, 240, 255))
            ImageDraw.Draw(paper).rectangle([0, 0, 45, 33], outline=(210, 204, 194, 255), width=2)
            paper = paper.rotate(v * 300, Image.BILINEAR, expand=True)
            ca._put(rgba, paper, (px_ - paper.width / 2, py_ - paper.height / 2))
        im.paste(rgba.convert("RGB"))

    # ---------------------------------------------------------------- 想象云朵
    CLOUD_W, CLOUD_H = CLOUD_W, CLOUD_H
    PIC_ZOOM = 1.45                                    # 云里的画面放大一点，看得清

    def _cloud_mask(self) -> Image.Image:
        """云朵形状（L 图）：一个圆角矩形，四周鼓出几个半圆。缓存。"""
        if not hasattr(self, "_mask"):
            w, h = self.CLOUD_W, self.CLOUD_H
            m = Image.new("L", (w, h), 0)
            d = ImageDraw.Draw(m)
            d.ellipse([20, 40, w - 20, h - 30], fill=255)                 # 大椭圆打底
            n = 11                                                        # 边上一圈挨得很紧的圆，形成圆滚滚的云边
            for k in range(n):
                ang = k / n * 2 * math.pi
                cx = w / 2 + (w / 2 - 62) * math.cos(ang)
                cy = h / 2 + 5 + (h / 2 - 58) * math.sin(ang)
                r = 58 if math.sin(ang) < 0.3 else 48                     # 上面的鼓包大一些
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
            self._mask = m
        return self._mask

    def cloud_box(self, x: float) -> tuple[float, float, float, float]:
        return cloud_box(x, self.scale)

    def _cloud(self, rgba: Image.Image, g: dict, t: float, x: float) -> None:
        """头顶冒出三个小圆点 → 展开成云朵（只描边，里面透明）→ 云里浮现画面；结束时反过来收回。"""
        a, b = g["a"], g["b"]
        grow = _ease((t - a) / 0.7)
        shrink = _ease((b - t) / 0.35)
        k = min(grow, shrink)
        head_y = self.floor - (ca.BH + ca.DEPTH + 6) * self.scale
        w, h = self.CLOUD_W, self.CLOUD_H
        bx0, by0, bx1, by1 = self.cloud_box(x)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        d = ImageDraw.Draw(rgba, "RGBA")
        # 三个小圆点：从头顶往云朵左下角一个个冒出来
        dots = [(x - 18, head_y - 16, 6), (x - 44, head_y - 38, 9), (x - 76, head_y - 62, 12)]
        for i, (dx, dy, r) in enumerate(dots):
            v = min(_ease((t - a - i * 0.12) / 0.2), shrink)
            if v > 0.02:
                rr = r * v
                d.ellipse([dx - rr, dy - rr, dx + rr, dy + rr], outline=(255, 255, 255, int(230 * v)), width=3)
        ck = _ease((t - a - 0.3) / 0.4)
        ck = min(ck, shrink)
        if ck <= 0.02:
            return
        m = self._cloud_mask()
        sw, sh = max(8, int(w * (0.5 + 0.5 * ck))), max(8, int(h * (0.5 + 0.5 * ck)))
        mm = m.resize((sw, sh), Image.BILINEAR)
        solid = mm.point(lambda v: 255 if v > 128 else 0)
        ring = ImageChops.subtract(solid, solid.filter(ImageFilter.MinFilter(7)))    # 只留 3 像素宽的边
        ring = ring.point(lambda v: int(v * 0.92 * ck))
        white = Image.new("RGBA", (sw, sh), (255, 255, 255, 0))
        white.putalpha(ring)
        ca._put(rgba, white, (cx - sw / 2, cy - sh / 2))
        pic = visions.draw(g["card"]["vision"], max(0.0, t - a - 0.6))
        vk = min(_ease((t - a - 0.6) / 0.4), shrink)
        if pic is not None and vk > 0.02:
            if not pic.info.get("hd"):                                   # 手绘画面已经是云里的大小
                pic = pic.resize((int(pic.width * self.PIC_ZOOM), int(pic.height * self.PIC_ZOOM)), Image.NEAREST)
            box = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))            # 画面只露在云朵里面
            box.alpha_composite(pic, (int(sw / 2 - pic.width / 2), int(sh / 2 - pic.height / 2 + 6)))
            inner = mm.filter(ImageFilter.MinFilter(9))
            box.putalpha(ImageChops.multiply(box.getchannel("A"), inner))
            ca._put(rgba, ca._fade(box, vk), (cx - sw / 2, cy - sh / 2))
