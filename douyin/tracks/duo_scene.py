"""两人模式（模板 cast: "duo"）里的女生小人：左下角唱歌，歌词跟在她右边。

她不转身、不换位置（和原来的唱歌小人 stage.Singer 不同）：站在原地，随人声音量张嘴，按拍左右摇头、身体轻晃，
常常闭眼享受（一句唱到后半、副歌里唱得响时），重拍小踮脚，唱得响时举手；音符一直从她身边飘出来，人声越强飘得越多。
间奏里闭眼跟着节奏点头；第一句之前先挥手打招呼。尾声和男生一起蹦跳着走到画面中间，鞠躬致谢（finale）。
歌词：当前一句英文（逐词点亮）+ 下面一行中文翻译，左边紧挨着她，最右到 x1 为止，放不下就缩小字号。
"""
import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import clawd_anim as ca
import daw

SCALE = 4


class SingerGirl:
    VERSE = ["sway", "mic", "hum", "step"]               # 每句换一个动作（整句不变，不抽搐），都不转身
    CHORUS = ["wave_both", "heart", "clap", "step"]

    def __init__(self, lines: list[dict], theme: dict, vocal_env: np.ndarray, env_rate: int, beats: list[float],
                 chorus: list[list[float]], floor: float, x: float = 110, x1: float = 1080,
                 finale: dict | None = None, show_lyrics: bool = True, reactions: list | None = None,
                 lyric_size: int | None = None):
        """show_lyrics=False：只用 lines 的时间（比如 AI 听写的分句）驱动唱歌动作，不显示歌词；
        reactions：[(开始, 结束, 片段名)]，这段时间她对评论做反应（比如被夸「有品」时害羞）。"""
        self.show_lyrics, self.reactions = show_lyrics, reactions or []
        """lines：[{start, end, text, zh, words:[[词, 开始, 结束]]}]（正片时间）；finale：{"walk": 出发时间, "x": 鞠躬位置}。"""
        self.th, self.lines = theme, lines
        self.env, self.rate = vocal_env, env_rate
        self.peak = float(np.percentile(vocal_env, 98)) if len(vocal_env) else 1.0
        self.beats = np.array(beats or [0.0])
        self.chorus, self.floor, self.x, self.fin = chorus, floor, x, finale
        self.left = x + (ca.BW / 2 + 14) * SCALE                # 歌词从她右手边开始（让开飘出来的音符）
        room = x1 - self.left
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        size = int(lyric_size or 40)
        longest = max((ln["text"] for ln in lines), key=len, default="")
        cjk = any(re.search(r"[一-鿿]", ln["text"]) for ln in lines)   # 中文歌：歌词本身用中文字体，逐字高亮
        face = theme["lyric_zh"] if cjk else theme["lyric_en"]
        while size > 24 and d.textlength(longest, font=ImageFont.truetype(face, size)) > room:
            size -= 2
        self.f_en = ImageFont.truetype(face, size)
        self.f_zh = ImageFont.truetype(theme["lyric_zh"], max(20, int(size * 0.6)))
        for ln in lines:
            ln["w"] = d.textlength(ln["text"], font=self.f_en)
            ln["word_x"], xx = [], 0.0
            pos = 0
            for w, s, e in ln["words"]:
                if cjk:                                       # 按字在整句里的位置量（字之间没有空格）
                    k = ln["text"].find(w, pos)
                    k = pos if k < 0 else k
                    x0 = d.textlength(ln["text"][:k], font=self.f_en)
                    pos = k + len(w)
                    ln["word_x"].append((x0, d.textlength(ln["text"][:pos], font=self.f_en), s, e))
                    continue
                ww = d.textlength(w, font=self.f_en)
                ln["word_x"].append((xx, xx + ww, s, e))
                xx += ww + d.textlength(" ", font=self.f_en)

    # ---------------------------------------------------------------- 时间
    def _vocal(self, t: float, win: float = 0.08) -> float:
        """人声音量（0~1），取前后 win 秒的平均，避免一帧一变。"""
        i0, i1 = int((t - win) * self.rate), int((t + win) * self.rate) + 1
        i0, i1 = max(0, i0), min(len(self.env), i1)
        if i1 <= i0:
            return 0.0
        return float(min(1.0, self.env[i0:i1].mean() / max(self.peak, 1e-6)))

    def _chorus_w(self, t: float) -> float:
        """副歌权重 0~1，进出副歌时 0.6 秒内平滑过渡（摇摆幅度不会突然变大）。"""
        w = 0.0
        for a, b in self.chorus:
            w = max(w, min(1.0, (t - a + 0.3) / 0.6, (b + 0.3 - t) / 0.6))
        return max(0.0, w)

    def _beat(self, t: float) -> tuple[float, int]:
        """(拍内进度 0~1, 第几拍)。"""
        k = int(np.searchsorted(self.beats, t) - 1)
        if k < 0 or k + 1 >= len(self.beats):
            period = float(np.median(np.diff(self.beats))) if len(self.beats) > 1 else 0.6
            return (t / period) % 1.0, int(t / period)
        a, b = self.beats[k], self.beats[k + 1]
        return (t - a) / max(b - a, 1e-3), k

    def _line(self, t: float):
        cur = None
        for i, ln in enumerate(self.lines):
            if ln["start"] - 0.35 <= t:
                cur = i
        return cur

    # ---------------------------------------------------------------- 姿态
    def pose(self, t: float) -> tuple[ca.Pose, float]:
        """返回 (姿态, 脚底 x)。"""
        if self.fin and t >= self.fin["walk"]:
            a = self.fin["walk"]
            w = max(0.6, abs(self.fin["x"] - self.x) / 450)
            if t < a + w:
                u = (t - a) / w
                p = ca.walk_happy(t - a)
                if self.fin["x"] < self.x:
                    p = ca.replace(p, turn=-abs(p.turn), lean=-p.lean)
                return p, self.x + (self.fin["x"] - self.x) * u
            if self.fin.get("exit"):                  # 走出画面（回家去了）：之后不再画
                return None, self.fin["x"]
            return ca.bow(t - a - w), self.fin["x"]
        for a, b, clip in self.reactions:                         # 对评论的反应（优先于唱歌动作）
            if a <= t < b and clip in ca.CLIPS:
                return ca.CLIPS[clip].pose(t - a), self.x
        ph, k = self._beat(t)
        tq = math.floor(t / 0.11) * 0.11                          # 嘴型每 0.11 秒才换一次（不抽搐）
        v = self._vocal(tq)
        vs = self._vocal(math.floor(t / 0.4) * 0.4, 0.3)          # 举手、闪光用更慢的音量（0.4 秒一换）
        cw = self._chorus_w(t)
        in_ch = cw > 0.5
        cur = self._line(t)
        ln = self.lines[cur] if cur is not None else None
        singing = ln is not None and ln["start"] - 0.1 <= t <= ln["end"] + 0.15
        sway = math.sin((k + ph) * math.pi)                       # 每拍摆向一边
        amp = 5 + 3 * cw
        if ln is None and self.lines and t < self.lines[0]["start"] - 0.4:      # 第一句之前：挥手打招呼
            return ca.wave(t), self.x
        if not singing:                                          # 间奏：闭眼点头
            nodk = abs(math.sin((k + ph) * math.pi))
            return ca.Pose(squash=1 - 0.05 * nodk, lean=2.5 * sway, eyes="closed", mouth="smile",
                           fx=[("note", t / 2.2)]), self.x
        prog = (t - ln["start"]) / max(ln["end"] - ln["start"], 0.5)
        enjoy = prog > 0.55                                      # 唱到后半句：闭眼享受（整段稳定，不来回眨）
        mouth = "open" if v > 0.55 else "o" if v > 0.25 else "smile" if v > 0.08 else "closed"
        loud = in_ch and vs > 0.6
        lift = cw * (math.sin(math.pi * min(ph / 0.6, 1.0)) ** 2 if k % 2 == 0 else 0.0)   # 副歌重拍：慢慢踮起再落下
        fx = [("note", t / 1.6), ("note", t / 1.6 + 0.5)]          # 一直两个音符（数量不变，位置不跳）
        if loud:
            fx.append(("spark", t / 1.2))
        eyes = "closed" if enjoy else ("blink" if (t % 2.6) < 0.12 else "open")
        p = ca.Pose(lean=amp * sway, dx=0.4 * sway, hop=0.8 * lift, squash=1 + 0.03 * lift - 0.015 * abs(sway),
                    eyes=eyes, mouth=mouth, arm_l="up" if loud else "down", arm_r="down", fx=fx)
        return self._move(p, self._move_name(cur, ln, in_ch), t, k, ph, v), self.x

    def _move_name(self, i: int, ln: dict, in_ch: bool) -> str:
        text = (ln.get("text") or "").lower()
        if "sad" in text:
            return "pray"
        if "let go" in text or "let me go" in text:
            return "reach"
        if "love" in text:
            return "heart"
        seq = self.CHORUS if in_ch else self.VERSE
        return seq[i % len(seq)]

    @staticmethod
    def _move(p: ca.Pose, name: str, t: float, k: int, ph: float, v: float) -> ca.Pose:
        """在基础唱歌姿态上换成这一句的动作（跟着节拍走）。"""
        beat = math.sin((k + ph) * math.pi)
        if name == "mic":                     # 握麦：左手举到嘴边，身体往前探一点
            return ca.replace(p, arm_l="fist", lean=4 + 2 * beat, dx=0.2 * beat)
        if name == "hum":                     # 闭眼哼唱：慢慢歪头
            return ca.replace(p, eyes="closed", mouth="o" if v > 0.2 else "smile", lean=6 * math.sin(t * 1.3), dx=0)
        if name == "step":                    # 左右踏步：两拍走一边，脚一拍换一次
            side = math.sin(math.pi * ((k + ph) / 2))
            return ca.replace(p, dx=3.5 * side, legs="step0" if k % 2 else "step1", lean=3 * side)
        if name == "wave_both":               # 副歌：两手举高左右摇
            return ca.replace(p, arm_l="up", arm_r="up", lean=8 * beat, fx=list(p.fx) + [("spark", t / 1.1)])
        if name == "heart":                   # 比心：双手收在胸前，冒爱心
            return ca.replace(p, arm_l="hug", arm_r="hug", eyes="happy", blush=True,
                              fx=[("heart", t / 1.3), ("heart", t / 1.3 + 0.5), ("note", t / 1.6)])
        if name == "clap":                    # 拍手：半拍一合一开
            closed = (k + ph) % 1 < 0.5
            return ca.replace(p, arm_l="hold" if closed else "out", arm_r="hold" if closed else "out",
                              fx=list(p.fx) + ([("spark", t / 0.9)] if closed else []))
        if name == "pray":                    # 双手合十（唱到 sad）：闭眼、轻轻点头
            return ca.replace(p, arm_l="hold", arm_r="hold", eyes="closed", mouth="o" if v > 0.2 else "closed",
                              squash=0.97 - 0.02 * abs(beat), lean=2 * beat, dx=0)
        if name == "reach":                   # 唱到 let go：朝男生那边伸手
            return ca.replace(p, arm_r="out", eyes="look_r", lean=6, dx=0.6)
        return p

    # ---------------------------------------------------------------- 每帧
    def __call__(self, im: Image.Image, t: float) -> None:
        p, x = self.pose(t)
        if p is None:
            return
        rgba = im.convert("RGBA")
        sh = ca.shadow(p, SCALE)
        shade = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        shade.putalpha(sh)
        ca._put(rgba, shade, (x - sh.width / 2, self.floor - sh.height / 2))
        spr, (fx, fy) = ca.render(p, SCALE, ca.FEMALE)
        ca._put(rgba, spr, (x - fx, self.floor - fy))
        ca.draw_fx(rgba, p, (x, self.floor), SCALE)
        if self.show_lyrics and not (self.fin and t >= self.fin["walk"] - 0.3):
            self._lyrics(rgba, t)
        im.paste(rgba.convert("RGB"))

    def _lyrics(self, im: Image.Image, t: float) -> None:
        cur = self._line(t)
        if cur is None:
            return
        ln = self.lines[cur]
        end = ln["end"] + 0.6
        nxt = self.lines[cur + 1]["start"] - 0.35 if cur + 1 < len(self.lines) else end + 9
        hold = nxt if nxt - end < 6 else end + 2.4
        if self.fin:
            hold = min(hold, self.fin["walk"] - 0.3)
        a = min(1.0, max(0.0, (hold - t) / 0.3)) * min(1.0, max(0.0, (t - ln["start"] + 0.35) / 0.3))
        if a <= 0.01:
            return
        th = self.th
        in_ch = any(c0 <= t <= c1 for c0, c1 in self.chorus)
        y = self.floor - 100 + (1 - a) * 8
        prog = 0.0
        for wx0, wx1, s, e in ln["word_x"]:
            if t >= e:
                prog = wx1
            elif t >= s:
                prog = wx0 + (wx1 - wx0) * (t - s) / max(e - s, 0.05)
                break
            else:
                break
        layer = Image.new("RGBA", (int(ln["w"]) + 20, 80), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((4, 40), ln["text"], font=self.f_en, fill=(*th["muted"], int(190 * a)), anchor="lm")
        if prog > 0:
            lit = Image.new("RGBA", layer.size, (0, 0, 0, 0))
            hl = th["colors"]["vocals"] if in_ch else th["ivory"]
            ImageDraw.Draw(lit).text((4, 40), ln["text"], font=self.f_en, fill=(*hl, int(255 * a)), anchor="lm")
            cut = int(prog + 4)
            layer.alpha_composite(lit.crop((0, 0, cut, 80)), (0, 0))
        ca._put(im, layer, (self.left - 4, y - 40))
        if ln.get("zh"):
            d = ImageDraw.Draw(im, "RGBA")
            d.text((self.left, y + 40), ln["zh"], font=self.f_zh, fill=(*th["ivory"], int(200 * a)), anchor="lm")


def finale_times(story_finale: dict | None, t_last: float) -> float:
    """两人开始走向中间的时间：尾声那句话出现后，且留够走过去 + 鞠躬两次（约 3.6 秒）。"""
    start = t_last - 3.6
    if story_finale:
        start = max(start, story_finale["t0"] + 0.4)
    return min(start, t_last - 2.6)


def meet_points() -> tuple[float, float]:
    """鞠躬时女生、男生站的位置（画面中间，各往两边让一点）。"""
    return daw.W / 2 - 70, daw.W / 2 + 70

