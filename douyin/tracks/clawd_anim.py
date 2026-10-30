"""CC 小人（Claude Code 像素小人）的动画库：姿态 → 画面，加上一组可以组合的动画片段。

和 stage.clawd（唱歌用的小人）同一套配色和像素风格，但做了「立体」处理：
  - 身体是一块有厚度的方块：正面 + 顶面（亮）+ 右侧面（暗），像等距视角的积木；
  - 起跳拉长、落地压扁（挤压拉伸），转身时水平缩放模拟转体，走近镜头时整体放大（景深）；
  - 脚下一团柔和的阴影，跳得越高阴影越小越淡（由调用方按 shadow() 画在地面上）。
每个动画片段是「时间 → 姿态」的函数（Clip），可以单独渲染、导出，也可以在 stage 里按时间轴拼起来用。

两个主角（v2）：男生 MALE（原来的样子，读评论）和女生 FEMALE（头顶粉色蝴蝶结、睫毛、蓝眼睛、常带腮红，唱歌）。
外观用 Look 描述（配色 + 配饰），画「想象画面」里的配角也从男生改出来：DAD（大一号、灰一点、戴帽子）、MOM（围巾）、
FRIEND（换个颜色）。每个片段标明属于谁（cast），导出时男女各放一个文件夹。

用法：
  python tracks/clawd_anim.py --export          导出全部片段到 assets/clawd/animations/male/ 和 female/（webm 透明背景
                                                + gif 预览 + manifest.json），总预览页 animations/index.html
  python tracks/clawd_anim.py --export happy    只导出某几个片段
"""
import argparse
import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

VERSION = 2                                   # 改了画法或参数就加一，manifest 里会记录（2：男女两个主角）
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "clawd" / "animations"

BODY, HI, SHADE = (217, 119, 87), (236, 152, 120), (184, 92, 64)
TOP, SIDE = (244, 172, 140), (150, 72, 50)    # 顶面（受光）和右侧面（背光）
EYE, MOUTH, TONGUE = (38, 24, 20), (58, 22, 20), (206, 86, 86)
TEAR, BLUSH = (132, 190, 246), (240, 110, 120)
PAPER, PAPER_LINE, PAPER_EDGE = (250, 247, 240), (176, 170, 160), (210, 204, 194)
HEART, SPARK, STEAM = (236, 72, 96), (255, 226, 120), (235, 235, 240)

GW, GH = 48, 40                               # 精灵网格
OX, OY = 12, 16                               # 身体正面左上角
BW, BH = 24, 14                               # 身体正面大小
DEPTH = 3                                     # 顶面/侧面的厚度（格）


@dataclass(frozen=True)
class Look:
    """外观：配色 + 配饰。默认值就是原来的 CC 小人（男生），画出来和 v1 一模一样。"""
    body: tuple = BODY
    hi: tuple = HI
    shade: tuple = SHADE
    top: tuple = TOP
    side: tuple = SIDE
    iris: tuple | None = None        # 瞳孔颜色（None = 全黑眼睛）
    lashes: bool = False             # 睫毛
    bow: tuple | None = None         # 头顶蝴蝶结颜色
    blush: bool = False              # 常驻腮红
    hat: tuple | None = None         # 帽子颜色（爸爸）
    scarf: tuple | None = None       # 围巾颜色（妈妈）


def _tone(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def recolor(base: tuple, **kw) -> Look:
    """从一个身体颜色派生整套配色（亮面、暗面、顶面、侧面）。"""
    return Look(body=base, hi=_tone(base, 1.09), shade=_tone(base, 0.85), top=_tone(base, 1.13),
                side=_tone(base, 0.69), **kw)


MALE = Look()
FEMALE = Look(lashes=True, bow=(242, 120, 160), blush=True)      # 眼睛和男生一样是黑色（用户 2026-10-25 改回）
DAD = recolor((176, 112, 88), hat=(70, 64, 80))
MOM = recolor((226, 138, 106), scarf=(126, 168, 214))
FRIEND = recolor((120, 150, 200))
OLD_FRIEND = recolor((96, 170, 150), scarf=(236, 196, 90))     # 《最佳损友》里的老朋友：青绿色 + 黄围巾
ELDER = recolor((214, 200, 186), hat=(120, 110, 104))          # 八十岁的样子：淡灰身体 + 帽子
LOOKS = {"male": MALE, "female": FEMALE, "dad": DAD, "mom": MOM, "friend": FRIEND, "old_friend": OLD_FRIEND,
         "elder": ELDER}
BOW_DARK = (196, 78, 120)


@dataclass
class Pose:
    hop: float = 0.0            # 离地高度（格）
    squash: float = 1.0         # 竖直缩放（<1 压扁，>1 拉长；水平方向自动反向，体积不变）
    lean: float = 0.0           # 倾斜角度（度，正 = 往右倒）
    turn: float = 1.0           # 朝向：1 面向右前，-1 面向左前，接近 0 是侧身（转身的中间帧）
    depth: float = 1.0          # 景深缩放（走近镜头 > 1）
    dx: float = 0.0             # 水平抖动（格）
    eyes: str = "open"          # open blink closed happy sad wide down look_l look_r look_up heart narrow
    mouth: str = "closed"       # closed smile grin open o frown
    arm_l: str = "down"         # down up out wave fist hold hug face head（摸后脑勺）
    arm_r: str = "down"
    legs: str = "stand"         # stand step0 step1 sit stomp_l stomp_r
    held: str | None = None     # None / paper（折着的纸）/ paper_open（展开读）
    paper_y: float = 0.0        # 手里纸的上下偏移（格，抽出纸时用）
    blush: bool = False
    fx: list = field(default_factory=list)   # [(种类, 0~1 的进度)]：tear heart spark steam note sweat


# ====================================================================== 画一帧
def _grid(p: Pose, look: Look = MALE) -> Image.Image:
    BODY, HI, SHADE, TOP, SIDE = look.body, look.hi, look.shade, look.top, look.side   # noqa: N806（沿用原来的名字）
    g = Image.new("RGBA", (GW, GH), (0, 0, 0, 0))
    px = g.load()

    def rect(x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                if 0 <= x < GW and 0 <= y < GH:
                    px[x, y] = (*c, 255)

    sit = p.legs == "sit"
    oy = OY + (3 if sit else 0)               # 坐下时身体低一点
    ox = OX
    # 腿（在身体后面先画）
    if sit:                                   # 坐着：腿伸到前面
        for lx in (ox + 3, ox + 17):
            rect(lx, oy + BH, lx + 4, oy + BH + 1, SHADE)
    else:
        for i, lx in enumerate((ox + 2, ox + 6, ox + 16, ox + 20)):
            up = 0
            if p.legs in ("step0", "step1"):
                up = 1 if i % 2 == (0 if p.legs == "step0" else 1) else 0
            elif p.legs == "stomp_l" and i < 2 or p.legs == "stomp_r" and i >= 2:
                up = 2
            rect(lx, oy + BH, lx + 1, oy + BH + 2 - up, SHADE if i in (1, 3) else BODY)
    # 立体：顶面（往右上斜出 DEPTH 格）和右侧面
    for k in range(1, DEPTH + 1):
        rect(ox + k, oy - k, ox + BW - 1 + k, oy - k, TOP if k < DEPTH else HI)
        rect(ox + BW - 1 + k, oy - k, ox + BW - 1 + k, oy + BH - 1 - k, SIDE)
    # 正面
    rect(ox, oy, ox + BW - 1, oy + BH - 1, BODY)
    rect(ox, oy, ox + BW - 1, oy, HI)
    rect(ox, oy + BH - 1, ox + BW - 1, oy + BH - 1, SHADE)
    # 眼睛
    for i, ex in enumerate((ox + 5, ox + 17)):
        e = p.eyes
        if e == "blink" or e == "closed":
            rect(ex, oy + 6, ex + 1, oy + 6, EYE)
        elif e == "happy":
            rect(ex, oy + 4, ex + 1, oy + 4, EYE)
            rect(ex - 1, oy + 5, ex - 1, oy + 6, EYE)
            rect(ex + 2, oy + 5, ex + 2, oy + 6, EYE)
        elif e == "sad":
            rect(ex, oy + 5, ex + 1, oy + 6, EYE)
            bx = ex + 2 if i == 0 else ex - 1
            rect(bx, oy + 3, bx, oy + 3, EYE)
        elif e == "wide":
            rect(ex - 1, oy + 2, ex + 2, oy + 7, EYE)
            rect(ex, oy + 3, ex, oy + 3, (255, 255, 255))
        elif e == "down":
            rect(ex, oy + 5, ex + 1, oy + 7, EYE)
        elif e == "narrow":                   # 生气：眼睛压成斜线
            rect(ex, oy + 5, ex + 1, oy + 6, EYE)
            rect(ex + (1 if i == 0 else 0), oy + 3, ex + (2 if i == 0 else 0), oy + 3, EYE)
        elif e == "heart":
            for x, y in ((0, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (2, 1), (3, 1), (0, 2), (1, 2), (2, 2), (1, 3)):
                rect(ex - 1 + x, oy + 3 + y, ex - 1 + x, oy + 3 + y, HEART)
        elif e in ("look_l", "look_r", "look_up"):
            dx = {"look_l": -2, "look_r": 2, "look_up": 0}[e]
            dy = -1 if e == "look_up" else 0
            rect(ex + dx, oy + 3 + dy, ex + 1 + dx, oy + 6 + dy, EYE)
        else:
            rect(ex, oy + 3, ex + 1, oy + 6, EYE)
            if look.iris:                                  # 彩色瞳孔 + 一个高光点
                rect(ex, oy + 5, ex + 1, oy + 6, look.iris)
                rect(ex + (1 if i == 0 else 0), oy + 3, ex + (1 if i == 0 else 0), oy + 3, (255, 255, 255))
        if look.lashes and e not in ("heart", "wide", "narrow"):   # 睫毛：眼睛外侧水平伸出一格（往上翘会像皱眉）
            lx = ex - 1 if i == 0 else ex + 2
            top_y = oy + (6 if e in ("blink", "closed") else 5 if e == "happy" else 3)
            rect(lx, top_y, lx, top_y, EYE)
            if e in ("blink", "closed"):                   # 闭眼：外侧再往下一格，像弯弯的睫毛
                rect(lx + (-1 if i == 0 else 1), top_y + 1, lx + (-1 if i == 0 else 1), top_y + 1, EYE)
    if p.blush or look.blush:
        rect(ox + 2, oy + 8, ox + 4, oy + 9, BLUSH)
        rect(ox + 19, oy + 8, ox + 21, oy + 9, BLUSH)
    # 嘴
    mx = ox + 10
    m = p.mouth
    if m == "smile":
        rect(mx, oy + 9, mx + 3, oy + 9, MOUTH)
        rect(mx - 1, oy + 8, mx - 1, oy + 8, MOUTH)
        rect(mx + 4, oy + 8, mx + 4, oy + 8, MOUTH)
    elif m == "grin":
        rect(mx - 1, oy + 8, mx + 4, oy + 10, MOUTH)
        rect(mx, oy + 10, mx + 3, oy + 10, TONGUE)
    elif m == "open":
        rect(mx, oy + 8, mx + 3, oy + 11, MOUTH)
        rect(mx + 1, oy + 11, mx + 2, oy + 11, TONGUE)
    elif m == "o":
        rect(mx + 1, oy + 8, mx + 2, oy + 10, MOUTH)
    elif m == "frown":
        rect(mx, oy + 9, mx + 3, oy + 9, MOUTH)
        rect(mx - 1, oy + 10, mx - 1, oy + 10, MOUTH)
        rect(mx + 4, oy + 10, mx + 4, oy + 10, MOUTH)
    # 手（在身体前面画，能盖住身体）
    for side, arm in ((-1, p.arm_l), (1, p.arm_r)):
        sx = ox - 4 if side < 0 else ox + BW          # 肩膀外侧的手块左边
        if arm == "up":
            rect(sx, oy - 6, sx + 3, oy + 4, BODY)
            rect(sx, oy - 6, sx + 3, oy - 6, HI)
        elif arm == "wave":
            rect(sx + (-1 if side < 0 else 1), oy - 6, sx + (2 if side < 0 else 4), oy + 1, BODY)
        elif arm == "out":                             # 往外平伸
            ex0 = sx - 3 if side < 0 else sx
            rect(ex0, oy + 5, ex0 + 6, oy + 8, BODY)
            rect(ex0, oy + 8, ex0 + 6, oy + 8, SHADE)
        elif arm == "fist":                            # 弯起手臂握拳
            rect(sx, oy + 2, sx + 3, oy + 8, BODY)
            rect(sx - (1 if side < 0 else -1), oy - 2, sx + 3 - (1 if side < 0 else -1), oy + 1, SHADE)
        elif arm == "hold":                            # 两手在胸前（拿着纸）
            hx = ox + 4 if side < 0 else ox + BW - 8
            rect(hx, oy + 8, hx + 3, oy + 11, HI)
            rect(hx, oy + 11, hx + 3, oy + 11, SHADE)
        elif arm == "hug":                             # 抱住自己：手交叉在身前
            hx = ox + BW - 10 if side < 0 else ox + 6
            rect(hx, oy + 9, hx + 4, oy + 11, HI)
        elif arm == "face":                            # 捂脸：手盖在眼睛上
            hx = ox + 3 if side < 0 else ox + 15
            rect(hx, oy + 2, hx + 5, oy + 7, HI)
            rect(hx, oy + 7, hx + 5, oy + 7, SHADE)
        elif arm == "head":                            # 摸后脑勺：手臂弯上去，手搭在头顶一侧
            rect(sx, oy - 2, sx + 3, oy + 5, BODY)
            hx = ox - 1 if side < 0 else ox + BW - 4
            rect(hx, oy - 4, hx + 4, oy - 1, HI)
        else:                                          # down
            rect(sx, oy + 6, sx + 3, oy + 9, BODY)
            rect(sx, oy + 9, sx + 3, oy + 9, SHADE)
    # 配饰（画在最上面）
    if look.scarf:                                     # 围巾：身体下半截一圈 + 垂下来的一条
        rect(ox, oy + BH - 4, ox + BW - 1, oy + BH - 3, look.scarf)
        rect(ox + 4, oy + BH - 3, ox + 6, oy + BH, _tone(look.scarf, 0.8))
    if look.hat:                                       # 帽子：压在顶面上的帽檐 + 帽身
        rect(ox - 1, oy - DEPTH - 1, ox + BW + DEPTH, oy - DEPTH - 1, look.hat)
        rect(ox + 4, oy - DEPTH - 5, ox + BW - 4 + DEPTH, oy - DEPTH - 2, look.hat)
        rect(ox + 4, oy - DEPTH - 2, ox + BW - 4 + DEPTH, oy - DEPTH - 2, _tone(look.hat, 1.5))
    if look.bow:                                       # 蝴蝶结：头顶左边，两片翅膀 + 中间的结
        bx, by = ox + 3, oy - DEPTH - 4
        dark = BOW_DARK
        for x, y, c in ((0, 0, look.bow), (1, 0, look.bow), (0, 1, look.bow), (1, 1, look.bow), (2, 1, look.bow),
                        (0, 2, look.bow), (1, 2, look.bow), (3, 1, dark), (3, 2, dark), (4, 1, look.bow),
                        (5, 1, look.bow), (6, 0, look.bow), (5, 0, look.bow), (6, 1, look.bow), (5, 2, look.bow),
                        (6, 2, look.bow), (0, 3, dark), (6, 3, dark)):
            rect(bx + x, by + y, bx + x, by + y, c)
    # 手里的纸
    if p.held == "paper":
        py = oy + 4 + p.paper_y
        rect(ox + 8, py, ox + 15, py + 5, PAPER)
        rect(ox + 8, py + 5, ox + 15, py + 5, PAPER_EDGE)
        rect(ox + 9, py + 2, ox + 14, py + 2, PAPER_LINE)
    elif p.held == "paper_open":                       # 展开举在脸前偏下，露出眼睛
        py = oy + 7 + p.paper_y
        rect(ox + 3, py, ox + 20, py + 8, PAPER)
        rect(ox + 3, py + 8, ox + 20, py + 8, PAPER_EDGE)
        for k in range(3):
            rect(ox + 5, py + 2 + k * 2, ox + 18 - (k == 2) * 5, py + 2 + k * 2, PAPER_LINE)
    return g


def render(p: Pose, scale: int = 5, look: Look = MALE) -> tuple[Image.Image, tuple[float, float]]:
    """姿态 → RGBA 图，以及「脚底中心」在图里的坐标（调用方据此摆放、画阴影）。"""
    g = _grid(p, look).resize((GW * scale, GH * scale), Image.NEAREST)
    foot = ((OX + BW / 2) * scale, (OY + BH + 3) * scale)
    sy = p.squash * p.depth
    sx = (1 / p.squash) * p.depth * max(abs(p.turn), 0.18)
    w, h = max(1, int(g.width * sx)), max(1, int(g.height * sy))
    if (w, h) != g.size:
        g = g.resize((w, h), Image.NEAREST)
        foot = (foot[0] * sx, foot[1] * sy)
    if p.turn < 0:
        g = g.transpose(Image.FLIP_LEFT_RIGHT)
        foot = (g.width - foot[0], foot[1])
    if abs(p.lean) > 0.3:                             # 绕脚底倾斜
        pad = max(g.size)
        big = Image.new("RGBA", (g.width + pad * 2, g.height + pad * 2), (0, 0, 0, 0))
        big.paste(g, (pad, pad))
        cx, cy = foot[0] + pad, foot[1] + pad
        big = big.rotate(-p.lean, Image.NEAREST, center=(cx, cy))
        box = big.getbbox() or (0, 0, 1, 1)
        g = big.crop(box)
        foot = (cx - box[0], cy - box[1])
    foot = (foot[0] + p.dx * scale, foot[1] + p.hop * scale)
    return g, foot


def shadow(p: Pose, scale: int = 5) -> Image.Image:
    """脚下的软阴影（L 图，中心即脚底中心）：跳得越高越小越淡。"""
    k = 1 / (1 + max(p.hop, 0) * 0.08)
    w, h = int(BW * scale * 1.1 * k * p.depth), int(BW * scale * 0.22 * k * p.depth)
    m = Image.new("L", (w + 40, h + 40), 0)
    ImageDraw.Draw(m).ellipse([20, 20, 20 + w, 20 + h], fill=int(150 * k))
    return m.filter(ImageFilter.GaussianBlur(8))


# ====================================================================== 特效（画在缩放后的图上，跟着小人走）
def _put(canvas: Image.Image, im: Image.Image, xy: tuple[int, int]) -> None:
    """alpha_composite，超出画布（包括负坐标）的部分裁掉。"""
    x, y = int(xy[0]), int(xy[1])
    box = (max(0, -x), max(0, -y), min(im.width, canvas.width - x), min(im.height, canvas.height - y))
    if box[2] > box[0] and box[3] > box[1]:
        canvas.alpha_composite(im.crop(box), (x + box[0], y + box[1]))


def _pixel(shape: list[str], col, scale: int) -> Image.Image:
    im = Image.new("RGBA", (max(len(r) for r in shape), len(shape)), (0, 0, 0, 0))
    for y, row in enumerate(shape):
        for x, ch in enumerate(row):
            if ch == "X":
                im.putpixel((x, y), (*col, 255))
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


HEART_SHAPE = [".X.X.", "XXXXX", "XXXXX", ".XXX.", "..X.."]
SPARK_SHAPE = ["..X..", "..X..", "XXXXX", "..X..", "..X.."]
NOTE_SHAPE = ["..XX", "..X.X", "..X..", "..X.", "XXX.", "XX.."]
DROP_SHAPE = [".X.", "XXX", "XXX", ".X."]


def draw_fx(canvas: Image.Image, p: Pose, foot_xy: tuple[float, float], scale: int = 5) -> None:
    """把姿态里的特效画到画布上（foot_xy：小人脚底中心在画布上的位置）。"""
    fx, fy = foot_xy
    top = fy - (BH + 3 + 2) * scale * p.squash * p.depth      # 头顶大致高度
    d = ImageDraw.Draw(canvas, "RGBA")
    for kind, u in p.fx:
        u = u % 1.0
        if kind == "tear":                   # 从右眼往下掉
            x = fx + 6 * scale * p.turn
            y = top + 9 * scale + u * 10 * scale
            spr = _pixel(DROP_SHAPE, TEAR, max(1, scale // 2 + 1))
            _put(canvas, _fade(spr, 1 - u), (x, y))
        elif kind == "heart":                # 往上飘、左右摇
            x = fx + math.sin(u * 6.3) * 4 * scale + 10 * scale
            y = top - u * 14 * scale
            _put(canvas, _fade(_pixel(HEART_SHAPE, HEART, scale), 1 - u), (x, y))
        elif kind == "spark":
            for k in range(3):
                v = (u + k / 3) % 1
                x = fx + (-14 + k * 14) * scale
                y = top - 4 * scale - v * 6 * scale
                spr = _pixel(SPARK_SHAPE, SPARK, max(1, scale // 2 + 1))
                _put(canvas, _fade(spr, math.sin(v * math.pi)), (x, y))
        elif kind == "steam":                # 头顶冒气（柔和的圆）
            for k in range(2):
                v = (u + k / 2) % 1
                r = (2 + v * 4) * scale
                x = fx + (-6 + k * 12) * scale
                y = top - v * 10 * scale
                d.ellipse([x - r, y - r, x + r, y + r], fill=(*STEAM, int(160 * (1 - v))))
        elif kind == "note":
            x = fx + 14 * scale + math.sin(u * 6.3) * 3 * scale
            y = top - u * 12 * scale
            _put(canvas, _fade(_pixel(NOTE_SHAPE, (255, 240, 220), scale), 1 - u), (x, y))
        elif kind == "sweat":
            x = fx + 12 * scale
            y = top + 2 * scale + u * 4 * scale
            _put(canvas, _fade(_pixel(DROP_SHAPE, TEAR, scale), 1 - u), (x, y))


def _fade(im: Image.Image, a: float) -> Image.Image:
    if a >= 0.999:
        return im
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda v, a=max(a, 0.0): int(v * a)))
    return out


# ====================================================================== 动画片段
@dataclass
class Clip:
    name: str
    zh: str
    duration: float
    loop: bool
    fn: callable
    cast: tuple = ("male",)          # 这段动画属于谁（导出到对应的文件夹）

    def pose(self, t: float) -> Pose:
        return self.fn(t % self.duration if self.loop else min(t, self.duration))


def _blink(t: float, every: float = 3.1) -> str:
    return "blink" if (t % every) < 0.12 else "open"


def _bounce(u: float) -> tuple[float, float]:
    """一次起跳：u 0~1 → (离地高度, 挤压)。起跳前压扁、空中拉长、落地再压扁。"""
    if u < 0.15:
        return 0.0, 1 - 0.18 * (u / 0.15)
    if u < 0.85:
        v = (u - 0.15) / 0.7
        return 7 * math.sin(v * math.pi), 1.12 - 0.12 * abs(v - 0.5) * 2
    return 0.0, 1 - 0.15 * math.sin((u - 0.85) / 0.15 * math.pi)


def idle(t):
    return Pose(squash=1 + 0.025 * math.sin(t * 2.4), eyes=_blink(t))


def walk(t):
    ph = int(t / 0.18) % 2
    return Pose(hop=0.8 * abs(math.sin(t * math.pi / 0.18)), lean=4, legs="step0" if ph else "step1",
                arm_l="down" if ph else "out", arm_r="out" if ph else "down", eyes=_blink(t))


def open_folder(t):
    u = t / 0.8
    return Pose(lean=8 * math.sin(min(u, 1) * math.pi), arm_r="out", arm_l="down",
                eyes="wide" if u < 0.6 else "open", mouth="o")


def pull_card(t):
    u = min(t / 0.8, 1)
    h, s = (_bounce((u - 0.6) / 0.4) if u > 0.6 else (0.0, 1.0))
    return Pose(hop=h * 0.5, squash=s, arm_l="hold", arm_r="hold", held="paper", paper_y=6 * (1 - u),
                eyes="wide" if u < 0.7 else "happy", mouth="o" if u < 0.7 else "smile")


def read(t):
    scan = ["look_l", "open", "look_r"][int(t / 0.35) % 3]
    return Pose(squash=1 + 0.015 * math.sin(t * 3), lean=2 * math.sin(t * 1.6), arm_l="hold", arm_r="hold",
                held="paper_open", eyes=scan if (t % 2.2) > 0.1 else "blink")


def toss(t):
    u = min(t / 0.7, 1)
    h, s = _bounce(u)
    return Pose(hop=h, squash=s, arm_l="up", arm_r="up", held="paper" if u < 0.35 else None,
                paper_y=-8 * u, eyes="happy", mouth="open")


def sad(t):
    return Pose(squash=0.94 + 0.01 * math.sin(t * 1.5), lean=-3 + 1.5 * math.sin(t * 1.2), eyes="sad",
                mouth="frown", fx=[("tear", t / 1.1)])


def lonely(t):
    rock = math.sin(t * 2.0)
    return Pose(legs="sit", lean=3 * rock, arm_l="hug", arm_r="hug", squash=0.96,
                eyes=["down", "look_l", "down", "look_r"][int(t / 1.2) % 4], mouth="closed")


def happy(t):
    u = (t % 0.55) / 0.55
    h, s = _bounce(u)
    up = int(t / 0.55) % 2
    return Pose(hop=h, squash=s, eyes="happy", mouth="grin", arm_l="up" if up else "down",
                arm_r="down" if up else "up", fx=[("spark", t / 0.9)])


def love(t):
    return Pose(lean=5 * math.sin(t * 2.2), squash=1 + 0.03 * math.sin(t * 4.4), eyes="heart", mouth="smile",
                blush=True, arm_l="hug", arm_r="hug", fx=[("heart", t / 1.3), ("heart", t / 1.3 + 0.5)])


def hope(t):
    u = min(t / 0.6, 1)
    return Pose(hop=1.5 * u + 0.4 * math.sin(t * 3), squash=1 + 0.06 * u, eyes="look_up", mouth="smile",
                arm_r="fist", arm_l="down", fx=[("spark", t / 1.2)])


def laugh(t):
    return Pose(lean=9 * math.sin(t * 9), squash=1 - 0.05 * abs(math.sin(t * 9)), eyes="happy", mouth="open",
                arm_l="hug", arm_r="hug", dx=0.6 * math.sin(t * 18))


def nostalgic(t):
    return Pose(lean=4 * math.sin(t * 1.3), turn=0.85 + 0.15 * math.cos(t * 1.3), eyes="look_up",
                mouth="smile" if (t % 4) > 2 else "closed", fx=[("note", t / 1.6)])


def angry(t):
    stomp = int(t / 0.3) % 2
    return Pose(legs="stomp_l" if stomp else "stomp_r", dx=0.5 * math.sin(t * 40), squash=0.97 + 0.03 * stomp,
                eyes="narrow", mouth="frown", arm_l="fist", arm_r="fist", fx=[("steam", t / 0.8)])


def shy(t):
    return Pose(turn=0.75 + 0.1 * math.sin(t * 2), lean=-4 + 2 * math.sin(t * 2), arm_l="face", arm_r="face",
                blush=True, eyes="closed", mouth="smile", fx=[("sweat", t / 1.4)])


def turn_around(t):
    """转身：正面 → 侧面 → 背面（镜像）→ 正面，用水平缩放模拟转体。"""
    u = (t % 1.2) / 1.2
    return Pose(turn=math.cos(u * 2 * math.pi), eyes=_blink(t), hop=0.6 * math.sin(u * math.pi))


def approach(t):
    """走近镜头：边走边放大（景深）。"""
    u = min(t / 1.6, 1)
    p = walk(t)
    return replace(p, depth=1 + 0.35 * u, lean=2)


# ---------- 女生唱歌（不转身：原地摇头、闭眼享受、踮脚，音符一直飘）
def _notes(t: float, n: int = 2, period: float = 1.4) -> list:
    return [("note", t / period + k / n) for k in range(n)]


def sing(t):
    """唱歌：嘴巴开合，按拍左右摇头。"""
    beat = 0.68
    sway = math.sin(t / beat * math.pi)
    mouth = ["open", "o", "open", "smile"][int(t / 0.17) % 4]
    return Pose(lean=5 * sway, dx=0.4 * sway, squash=1 + 0.02 * abs(sway), mouth=mouth, eyes=_blink(t, 2.6),
                arm_l="down", arm_r="down", fx=_notes(t))


def sing_enjoy(t):
    """闭眼享受：微笑、歪头轻晃。"""
    sway = math.sin(t * 1.9)
    return Pose(lean=7 * sway, squash=1 + 0.015 * math.sin(t * 3.8), eyes="closed",
                mouth="smile" if (t % 1.6) < 1.1 else "o", fx=_notes(t, 3, 1.8))


def sing_loud(t):
    """唱得响：举手、踮脚、音符更多。"""
    u = (t % 0.68) / 0.68
    lift = max(0.0, math.sin(u * math.pi))
    return Pose(hop=1.2 * lift, squash=1 + 0.06 * lift, lean=3 * math.sin(t * 4.6), mouth="open", eyes="happy",
                arm_l="up", arm_r="down", fx=_notes(t, 3, 1.0) + [("spark", t / 1.2)])


def nod(t):
    """间奏：闭眼跟着节奏点头。"""
    k = abs(math.sin(t / 0.68 * math.pi))
    return Pose(squash=1 - 0.05 * k, lean=2 * math.sin(t * 1.2), eyes="closed", mouth="smile", fx=_notes(t, 1, 2.2))


def wave(t):
    return Pose(arm_r="wave" if int(t / 0.25) % 2 else "up", eyes="happy", mouth="smile",
                lean=3 * math.sin(t * 5), fx=_notes(t, 1, 2.0))


# ---------- 两人共用
def walk_happy(t):
    """蹦跳着走：每两步小跳一次。"""
    u = (t % 0.5) / 0.5
    h, s = _bounce(u)
    ph = int(t / 0.25) % 2
    return Pose(hop=h * 0.45, squash=s, lean=5, legs="step0" if ph else "step1", eyes="happy", mouth="smile",
                arm_l="up" if ph else "down", arm_r="down" if ph else "up")


def bow(t):
    """鞠躬（面向观众）：身体往下一沉、闭眼、微微前倾，停一下再起身微笑。2.4 秒两次。"""
    u = (t % 1.2) / 1.2
    k = math.sin(min(u / 0.7, 1) * math.pi)
    return Pose(lean=5 * k, squash=1 - 0.22 * k, eyes="closed" if k > 0.2 else "happy",
                mouth="smile",
                fx=[("spark", t / 1.2)] if k < 0.2 else [])


CLIPS = {c.name: c for c in [
    Clip("idle", "待机：呼吸、眨眼", 3.2, True, idle),
    Clip("walk", "走路", 0.72, True, walk),
    Clip("turn_around", "转身一圈", 1.2, True, turn_around),
    Clip("approach", "走近镜头（景深放大）", 1.6, False, approach),
    Clip("open_folder", "伸手打开文件夹", 0.8, False, open_folder),
    Clip("pull_card", "抽出一张评论", 0.8, False, pull_card),
    Clip("read", "举着评论读（眼睛左右扫）", 2.2, True, read),
    Clip("toss", "把评论抛向空中", 0.7, False, toss),
    Clip("sad", "难过：垂头掉泪", 2.2, True, sad),
    Clip("lonely", "孤独：抱膝坐着摇晃", 4.8, True, lonely),
    Clip("happy", "开心：蹦跳挥手", 1.1, True, happy),
    Clip("love", "心动：爱心眼、冒爱心", 2.6, True, love),
    Clip("hope", "希望：握拳抬头", 2.4, False, hope),
    Clip("laugh", "大笑：前仰后合", 1.4, True, laugh),
    Clip("nostalgic", "怀念：抬头望天、飘音符", 3.2, True, nostalgic),
    Clip("angry", "生气：跺脚冒气", 1.2, True, angry),
    Clip("shy", "害羞：捂脸", 2.8, True, shy),
    Clip("sing", "唱歌：嘴巴开合、按拍摇头", 2.72, True, sing, ("female",)),
    Clip("sing_enjoy", "闭眼享受：歪头轻晃", 3.3, True, sing_enjoy, ("female",)),
    Clip("sing_loud", "唱得响：举手踮脚", 1.36, True, sing_loud, ("female",)),
    Clip("nod", "间奏：闭眼点头", 2.72, True, nod, ("female",)),
    Clip("wave", "挥手打招呼", 1.0, True, wave, ("female",)),
    Clip("walk_happy", "蹦跳着走", 1.0, True, walk_happy, ("male", "female")),
    Clip("bow", "鞠躬致谢", 2.4, False, bow, ("male", "female")),
]}
MOODS = ("sad", "lonely", "happy", "love", "hope", "laugh", "nostalgic", "angry", "shy")


def frame(clip: str, t: float, size: tuple[int, int] = (360, 300), scale: int = 5,
          floor_y: float | None = None, look: Look | None = None) -> Image.Image:
    """单独一帧（透明背景，含阴影和特效），导出和预览用。"""
    c = CLIPS[clip]
    p = c.pose(t)
    look = look or LOOKS[c.cast[0]]
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    fy = floor_y or size[1] - 40
    cx = size[0] / 2
    sh = shadow(p, scale)
    shade = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    shade.putalpha(sh)
    _put(canvas, shade, (cx - sh.width / 2, fy - sh.height / 2))
    im, (fx, fyy) = render(p, scale, look)
    _put(canvas, im, (cx - fx, fy - fyy))
    draw_fx(canvas, p, (cx, fy), scale)
    return canvas


# ====================================================================== 导出
CAST_ZH = {"male": "男生（读评论）", "female": "女生（唱歌）"}


def export(names: list[str] | None = None, fps: int = 30) -> list[dict]:
    """每个角色的片段导出到 animations/<角色>/，各自一份 manifest.json；总预览页 animations/index.html。"""
    out = []
    for who in CAST_ZH:
        todo = [n for n in (names or list(CLIPS)) if who in CLIPS[n].cast]
        if todo:
            out += _export_cast(who, todo, fps)
    _index()
    return out


def _export_cast(who: str, names: list[str], fps: int) -> list[dict]:
    import imageio_ffmpeg
    OUT = OUT_DIR / who
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    for name in names:
        c = CLIPS[name]
        dur = c.duration if not c.loop else c.duration * (2 if c.duration < 1.5 else 1)
        n = max(2, round(dur * fps))
        frames = [frame(name, i / fps, look=LOOKS[who]) for i in range(n)]
        # GIF 预览（透明背景）
        frames[0].save(OUT / f"{name}.gif", save_all=True, append_images=frames[1:], duration=int(1000 / fps),
                       loop=0, disposal=2, transparency=0, optimize=False)
        # WebM：VP9 + 透明通道（剪辑软件、网页都能直接用）
        w = imageio_ffmpeg.write_frames(str(OUT / f"{name}.webm"), frames[0].size, fps=fps, codec="libvpx-vp9",
                                        pix_fmt_in="rgba", pix_fmt_out="yuva420p", quality=None,
                                        output_params=["-b:v", "0", "-crf", "30", "-auto-alt-ref", "0"],
                                        macro_block_size=1, ffmpeg_log_level="error")
        w.send(None)
        for f in frames:
            w.send(f.tobytes())
        w.close()
        frames[min(len(frames) - 1, n // 3)].save(OUT / f"{name}.png")
        items.append({"name": name, "zh": c.zh, "duration": round(dur, 2), "loop": c.loop, "fps": fps,
                      "size": list(frames[0].size), "mood": name in MOODS, "cast": who})
        print(f"  {who:6s} {name:12s} {c.zh}  {dur:.2f}s  {n} 帧")
    manifest = OUT / "manifest.json"
    old = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {"clips": []}
    merged = {it["name"]: it for it in old.get("clips", [])}
    merged.update({it["name"]: it for it in items})
    allc = [merged[k] for k in CLIPS if k in merged]
    manifest.write_text(json.dumps({"version": VERSION, "cast": who, "clips": allc}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return items


def _index() -> None:
    sections = []
    for who, zh in CAST_ZH.items():
        mf = OUT_DIR / who / "manifest.json"
        clips = json.loads(mf.read_text(encoding="utf-8"))["clips"] if mf.exists() else []
        cards = "\n".join(
            f'<figure><img src="{who}/{c["name"]}.gif" alt="{c["zh"]}"><figcaption><b>{c["name"]}</b>'
            f'<span>{c["zh"]}</span><small>{c["duration"]} 秒 · {"循环" if c["loop"] else "单次"}'
            f'{" · 情绪" if c["mood"] else ""}</small></figcaption></figure>' for c in clips)
        sections.append(f"<h2>{zh} · {who}/</h2><main>{cards}</main>")
    cards = "\n".join(sections)
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CC 小人动画库</title><style>
body{{margin:0;padding:24px;background:#1b1316;color:#f6e9e2;font:15px/1.5 "Microsoft YaHei",sans-serif}}
h1{{font-size:22px;margin:0 0 4px}} p{{color:#b89a9a;margin:0 0 20px}}
h2{{font-size:17px;margin:26px 0 12px}} main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}
figure{{margin:0;background:#28181f;border-radius:14px;padding:12px;text-align:center}}
img{{width:100%;image-rendering:pixelated;background:repeating-conic-gradient(#2f2027 0 25%,#261a20 0 50%) 0/20px 20px;border-radius:10px}}
figcaption{{display:flex;flex-direction:column;gap:2px;margin-top:8px}} small{{color:#b89a9a}}
</style></head><body><h1>CC 小人动画库 v{VERSION}</h1>
<p>男女两个主角各一个文件夹。每个片段都有 .webm（透明背景，可直接拖进剪辑软件）、.gif 预览和 .png 截图；重新导出：python tracks/clawd_anim.py --export</p>
{cards}</body></html>"""
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="CC 小人动画库")
    ap.add_argument("--export", nargs="*", help="导出片段（不写名字 = 全部）")
    a = ap.parse_args()
    if a.export is not None:
        bad = [n for n in a.export if n not in CLIPS]
        if bad:
            ap.error(f"没有这些片段：{bad}；可选：{', '.join(CLIPS)}")
        export(a.export or None)
        print("已导出到", OUT_DIR)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
