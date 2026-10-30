"""从音乐播放器截图里认出歌名和歌手（Windows 自带 OCR，见 ocr_win.ps1）。

做法：OCR 出每一行文字和位置 → 去掉状态栏、按钮、播放控件、歌词等干扰 → 在「页面顶部」或「封面正下方」找字最大的
那一行当歌名，紧挨在它下面的一行当歌手。认不出时返回空，调用方保留原来的名字（文件名）。
用法: python tracks/song_ocr.py <截图>    → {"title": ..., "artist": ...}
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
NOISE = re.compile(r"中国移动|中国联通|中国电信|关注|VIP|vip|评论|推荐|最热|最新|笔记|"
                   r"歌曲百科|歌词|百科|专注模式|设置|听歌识曲|极高音质|无损|音质|播放|下载|分享|收藏|^\W*$")
ICON_PREFIX = re.compile(r"^(?:[回囗口OoQ○●◎□■<>《》@&]\s+)+")


def ocr(path: Path) -> dict:
    """返回 {"w","h","lines":[{"text","x","y","w","h"}]}。小图先放大，Windows OCR 对小字识别差。"""
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    k = 1.0
    if img.width < 1000:
        k = 1080 / img.width
        img = img.resize((1080, int(img.height * k)), Image.LANCZOS)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ocr.png"
        img.save(p)
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HERE / "ocr_win.ps1"), str(p)]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                             creationflags=0x08000000).stdout
    res = json.loads(out.strip() or "{}")
    res["lines"] = [ln for ln in (res.get("lines") or []) if ln.get("text")]
    res["k"] = k
    return res


def clean(text: str) -> str:
    t = ICON_PREFIX.sub("", text.strip())
    # OCR 常把小写 l 认成大写 I：PIay → Play、PIace → Place、AlI → All
    t = re.sub(r"(?<=\b[A-Z])I(?=[a-z])|(?<=[a-z])I(?=[a-z])|(?<=[A-Za-z][a-z])I\b|(?<=[a-z])II(?=[a-z\s]|$)",
               lambda m: "l" * len(m.group()), t)
    t = re.sub(r"\s*(关注|VIP|vip|\+关注)\s*$", "", t)
    t = re.sub(r"\s*[（(][^）)]*$", "", t)                  # 没写完的括号（被截断的译名）
    t = re.sub(r"\s+([,，.。!！?？])", r"\1", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ·-—|/")


def is_noise(ln: dict, h: int, phone: bool) -> bool:
    t = ln["text"]
    if phone and (ln["y"] < h * 0.045 or ln["y"] > h * 0.86):   # 手机截图的状态栏 / 播放控件
        return True
    if re.fullmatch(r"[\d\s:：.,，%+wW万·]*", t):            # 时间、播放量、电量
        return True
    letters = len(re.findall(r"[A-Za-z一-鿿]", t))
    return letters < 2 or bool(NOISE.search(t)) and letters < 8


def netease_player(res: dict) -> dict | None:
    """网易云黑胶播放页：歌名在左下，正下方一行是「歌手 关注」。"""
    for ln in res["lines"]:
        t = ln["text"].strip()
        if not t.endswith("关注"):
            continue
        artist = clean(t[:-2])
        above = [a for a in res["lines"] if abs(a["x"] - ln["x"]) < 30 and 0 < ln["y"] - a["y"] < ln["h"] * 3.5]
        if above and artist:
            title = clean(max(above, key=lambda a: a["y"])["text"])
            if title:
                return {"title": title, "artist": artist}
    return None


def guess(res: dict, cover_box: tuple | None = None) -> dict:
    """在 OCR 结果里猜歌名和歌手。cover_box：(x0, y0, x1, y1) 封面在截图里的位置（按 OCR 图的尺寸）。"""
    ne = netease_player(res)
    if ne:
        return ne
    h = res.get("h") or 1
    phone = h / max(res.get("w") or 1, 1) > 1.6                # 竖长的手机截图
    lines = [ln for ln in res["lines"] if not is_noise(ln, h, phone)]
    for ln in lines:
        ln["clean"] = clean(ln["text"])
    lines = [ln for ln in lines if len(ln["clean"]) >= 2]
    if not lines:
        return {"title": "", "artist": ""}
    zones = [lambda ln: ln["y"] < h * 0.16]                   # 歌词页、播放页顶部的歌名
    if cover_box:
        cb = cover_box[3]
        zones.append(lambda ln: cb < ln["y"] < cb + h * 0.14)  # 封面正下方
    for z in zones:
        cand = sorted((ln for ln in lines if z(ln)), key=lambda ln: ln["y"])
        if not cand:
            continue
        title = max(cand, key=lambda ln: (ln["h"], -ln["y"]))
        below = [ln for ln in cand if 0 < ln["y"] - title["y"] < title["h"] * 3 and ln["h"] <= title["h"] * 1.05]
        artist = below[0]["clean"] if below else ""
        return {"title": title["clean"], "artist": artist}
    return {"title": "", "artist": ""}


def recognize(path: Path, cover_box: tuple | None = None) -> dict:
    """cover_box 按原图坐标给出。"""
    try:
        res = ocr(path)
        box = tuple(v * res["k"] for v in cover_box) if cover_box else None
        return guess(res, box)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"title": "", "artist": ""}


if __name__ == "__main__":
    print(json.dumps(recognize(Path(sys.argv[1])), ensure_ascii=False))
