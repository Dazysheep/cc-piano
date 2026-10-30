"""修正 Audiveris 对《三叶的主题》的识别结果，导出 MIDI。

修正依据：逐小节对照原谱图片（主要是谱号切换处读错、长音符/连音丢失、升号漏识别）。
"""
import sys
from pathlib import Path

from music21 import chord, converter, note, stream, tempo, tie

SRC = str(Path(__file__).with_name("Mitsuha_Theme.omr.mxl"))   # Audiveris 原始识别结果
OUT = sys.argv[1]
BPM = 92

s = converter.parse(SRC)
rh, lh = s.parts[0], s.parts[1]


def make(spec: str):
    """'A3.C4:2~' → 和弦/单音/休止；~ 表示连到下一个音。"""
    tied = spec.endswith("~")
    spec = spec.rstrip("~")
    pitches, dur = spec.split(":")
    d = float(eval(dur))
    if pitches == "r":
        return note.Rest(quarterLength=d)
    ps = pitches.split(".")
    n = chord.Chord(ps, quarterLength=d) if len(ps) > 1 else note.Note(ps[0], quarterLength=d)
    if tied:
        n.tie = tie.Tie("start")
    return n


def set_measure(part, num: int, *voices: str) -> None:
    """用若干个声部(每个是空格分隔的音符序列)替换某小节的全部内容。"""
    m = part.measure(num)
    for el in list(m.voices) + list(m.notesAndRests):   # 只删音符/休止/声部，保留谱号、调号等
        m.remove(el)
    if len(voices) == 1:
        off = 0.0
        for spec in voices[0].split():
            n = make(spec)
            m.insert(off, n)
            off += n.quarterLength
    else:
        for i, vs in enumerate(voices, 1):
            v = stream.Voice(id=str(i))
            off = 0.0
            for spec in vs.split():
                n = make(spec)
                v.insert(off, n)
                off += n.quarterLength
            m.insert(0, v)


# ---------------- 右手
set_measure(rh, 12, "C5:1 G4:1 A4:2~")
set_measure(rh, 13, "A4:4")
set_measure(rh, 58, "C5.A5:1 G5:1 D5.G5.C6:1 B-5:1", "E4.G4.C5:2 r:2")

# ---------------- 左手
set_measure(lh, 14, "F3:4~")
set_measure(lh, 15, "F3:4")
set_measure(lh, 18, "F3:4~")
set_measure(lh, 22, "F3:4~")
set_measure(lh, 23, "F3:4")
set_measure(lh, 24, "A3:4")
set_measure(lh, 25, "G3:4")
set_measure(lh, 26, "F3:4~")
set_measure(lh, 27, "F3:4")
set_measure(lh, 30, "F3.C4:4~")
set_measure(lh, 33, "A3.C4:2~ C4.E4:2")
set_measure(lh, 34, "A3.G4:4~")
set_measure(lh, 35, "A3:4", "C5:2 G4:2")
set_measure(lh, 36, "C4.E4:3 D4:0.5 C4:0.5")
set_measure(lh, 37, "B3.D4:4")
set_measure(lh, 38, "C4.E4:4~")
set_measure(lh, 39, "C4:4", "B3:2 D4:2/3 C4:2/3 D4:2/3")
set_measure(lh, 40, "C4.E4:4~")
set_measure(lh, 41, "C4:4", "E4:2 G4:2~")
set_measure(lh, 42, "A3.G4:4~")
set_measure(lh, 43, "A3.C5:4")
set_measure(lh, 58, "A3.D4.G4:2 r:2")
set_measure(lh, 59, "A3:4~", "D4.E4.G4:2 D4.E4.G4:2")
set_measure(lh, 60, "A3:4~", "D4.E4.G4:2 D4.E4.G4:2")
set_measure(lh, 61, "A3:4~", "C#4.E4.G4:2 C#4.E4.G4:2")
set_measure(lh, 79, "F3:4~")
set_measure(lh, 80, "F3:4~")
set_measure(lh, 81, "F3:4~")
set_measure(lh, 82, "F3:4")

# 第 117 小节是识别软件在变调号处多出来的空小节，两只手都删掉，后面的小节号前移
for part in (rh, lh):
    extra = part.measure(117)
    part.remove(extra)
    for m in part.getElementsByClass("Measure"):
        if m.number > 117:
            m.number -= 1
            m.offset -= 4.0

# 结尾段只有「反复开始」没有「反复结束」，去掉反复记号（按不反复处理）
from music21 import bar
for part in (rh, lh):
    for m in part.getElementsByClass("Measure"):
        for side in ("leftBarline", "rightBarline"):
            b = getattr(m, side)
            if isinstance(b, bar.Repeat):
                setattr(m, side, bar.Barline("regular"))

# ---------------- 速度：整体 80 BPM，有延长记号的小节放慢
FERMATA_BARS = {4, 7, 10, 13, 45, 49, 52, 55, 68, 82, 96, 116}
for part in (rh, lh):
    for el in part.recurse().getElementsByClass(tempo.MetronomeMark):
        el.activeSite.remove(el)
first = rh.measure(1)
first.insert(0, tempo.MetronomeMark(number=BPM))
for b in sorted(FERMATA_BARS):
    m = rh.measure(b)
    if m is None:
        continue
    m.insert(0, tempo.MetronomeMark(number=round(BPM * 0.55)))
    nxt = rh.measure(b + 1)
    if nxt is not None:
        nxt.insert(0, tempo.MetronomeMark(number=BPM))

# 校验每小节拍数
problems = []
for name, part in (("RH", rh), ("LH", lh)):
    for m in part.getElementsByClass("Measure"):
        voices = m.voices or [m]
        for v in voices:
            d = sum(n.quarterLength for n in v.notesAndRests)
            if m.number > 1 and abs(d - 4) > 0.02:
                problems.append((name, m.number, round(d, 3)))
print("measures:", len(rh.getElementsByClass("Measure")), "duration problems:", problems)

s.write("midi", fp=OUT)
print("written", OUT)

