"""从网易云评论区的录屏里读出评论（Windows 自带 OCR，不花 token）：编剧页用。

做法：每 1.5 秒抽一帧 → OCR 出每一行文字和位置 → 以「日期行」（2016·04·30 / 08·29 广东）为锚点：上一行是用户名，
右边带「凸」的数字是点赞数，下面同一列连续的行是评论正文，遇到「展开 N 条回复」、下一个用户名或别的版块就结束 →
多帧里同一条评论（同一个用户名 + 日期）只留最长的那版（滚动时评论常被屏幕上下边缘截断）。
OCR 会有错字（比如「跳鱼儿」认成「跳鱼丿」），所以结果标了 ocr=True，编剧页里提示用户核对、可以直接改。
用法：python tracks/comment_ocr.py <录屏.mov>
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import song_ocr

DATE = re.compile(r"^(\d{4}\s*[·.\-]\s*)?\d{1,2}\s*[·.\-]\s*\d{1,2}(\s+\S{1,4})?$")
LIKES = re.compile(r"(\d+(?:\.\d+)?\s*万?)\s*凸|凸\s*(\d+(?:\.\d+)?\s*万?)")
STOP = re.compile(r"展开\s*\d+\s*条回复|这首歌的相关笔记|听说爱评论的人|话题\s*[〉>]")
CJK = r"一-鿿　-〿＀-￯“”‘’…—"


def tidy(text: str) -> str:
    """OCR 在中文和标点之间插的空格去掉，英文单词之间的空格留着。"""
    t = re.sub(rf"\s+(?=[{CJK}])|(?<=[{CJK}])\s+", "", text.strip())
    return re.sub(r"\s{2,}", " ", t)


def frame_comments(res: dict) -> list[dict]:
    """一帧 OCR 结果 → [{user, date, likes, text, cut}]（cut：正文碰到屏幕底边，可能没显示完）。"""
    k = res.get("k", 1.0)
    W, H = res["w"], res["h"]
    lines = sorted(res["lines"], key=lambda ln: (ln["y"], ln["x"]))
    head = next((ln["y"] for ln in lines if ln["text"].replace(" ", "").startswith("评论（")
                 or ln["text"].replace(" ", "").startswith("评论(")), None)
    if head is None:                                   # 不是评论页（播放页、控制中心……）
        return []
    out = []
    for i, ln in enumerate(lines):
        if ln["y"] <= head or not DATE.match(ln["text"].strip()):
            continue
        user = next((u for u in reversed(lines[:i]) if abs(u["x"] - ln["x"]) < 14 * k
                     and 0 < ln["y"] - u["y"] < 80 * k), None)
        if user is None:
            continue
        likes = None
        for o in lines:                               # 点赞数：用户名那一行的右边
            if o["x"] > W * 0.7 and abs(o["y"] - user["y"]) < 40 * k:
                m = LIKES.search(o["text"])
                if m:
                    likes = (m.group(1) or m.group(2)).replace(" ", "")
        body, last_y, cut = [], ln["y"], False
        for o in lines[i + 1:]:
            if o["y"] <= ln["y"] + 5 or o["x"] > W * 0.7 and LIKES.search(o["text"]):
                continue
            if STOP.search(o["text"].replace(" ", "")) or DATE.match(o["text"].strip()):
                break
            if abs(o["x"] - ln["x"]) > 30 * k:           # 别的列（笔记卡片、头像下的东西）
                continue
            if body and o["y"] - last_y > 3.0 * o["h"]:   # 中间空了一大截：下一个版块
                break
            nxt = lines.index(o) + 1                      # 下一个用户名（它下面紧跟日期行）也算结束
            if nxt < len(lines) and DATE.match(lines[nxt]["text"].strip()) and lines[nxt]["y"] - o["y"] < 80 * k:
                break
            body.append(o["text"])
            last_y = o["y"]
        if body:
            cut = last_y > H - 260 * k                  # 快到底部输入框了：可能没显示完
            out.append({"user": tidy(user["text"]), "date": tidy(ln["text"]), "likes": likes,
                        "text": tidy("".join(body)), "cut": cut})
    return out


def from_video(video: Path, every: float = 1.5, progress=None) -> list[dict]:
    """整段录屏 → 去重后的评论列表（按第一次出现的顺序）。"""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    seen: dict[str, dict] = {}
    order: list[str] = []
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps=1/{every}",
                        str(Path(d) / "f%04d.png")], check=True, creationflags=0x08000000)
        frames = sorted(Path(d).glob("f*.png"))
        for n, f in enumerate(frames):
            try:
                res = song_ocr.ocr(f)
            except Exception:                            # 某一帧认不出不影响别的帧
                continue
            for c in frame_comments(res):
                key = re.sub(r"\W", "", c["user"]) + "|" + re.sub(r"\D", "", c["date"])
                old = seen.get(key)
                if old is None:
                    seen[key] = c
                    order.append(key)
                elif len(c["text"]) > len(old["text"]):
                    seen[key] = {**c, "likes": c["likes"] or old["likes"]}
            if progress:
                progress((n + 1) / len(frames), f"识别评论 {n + 1}/{len(frames)} 帧，已找到 {len(order)} 条")
    out, texts = [], set()
    for key in order:
        c = seen[key]
        norm = re.sub(r"\W", "", c["text"])[:24]          # 用户名认得不一样（徽章被认成字）的同一条评论只留一次
        if len(c["text"]) >= 4 and norm not in texts:
            texts.add(norm)
            out.append({"user": c["user"], "date": c["date"], "likes": c["likes"], "text": c["text"], "ocr": True})
    return out


if __name__ == "__main__":
    for c in from_video(Path(sys.argv[1]), progress=lambda u, m: print(m, flush=True) if int(u * 100) % 25 == 0 else None):
        print(json.dumps(c, ensure_ascii=False))
