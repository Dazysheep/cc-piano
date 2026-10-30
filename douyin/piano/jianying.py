"""生成剪映草稿：背景 / 音符(滤色) / 琴键 / 文字 / 钢琴音 / 背景音 分轨道，可在剪映中继续编辑。"""
import os
import shutil
import subprocess
from pathlib import Path

import pyJianYingDraft as jy
from PIL import Image, ImageOps
from pyJianYingDraft import ClipSettings, TextBorder, TextShadow, TextStyle, TrackSpec, TrackType, trange

from overlay import CJK, background

SEC = 1_000_000
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _draft_dir(cfg: dict) -> Path:
    d = cfg["jianying"].get("draft_dir")
    if d:
        return Path(d)
    return Path(os.environ["LOCALAPPDATA"]) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"


def _ty(y_px: float, h: int) -> float:
    """画面像素 y(中心) → 剪映 transform_y(单位为半个画布高，向上为正)。"""
    return (h / 2 - y_px) / (h / 2)


def _font(text: str, cfg: dict):
    name = cfg["jianying"]["cjk_font" if CJK.search(text) else "title_font"]
    return jy.FontType[name]


def _loop(script, track: str, material, total: int, make, start: int = 0):
    """把素材首尾相接，从 start 铺到 start + total 微秒，返回所有片段。"""
    segs, t = [], 0
    while t < total:
        d = min(material.duration, total - t)
        seg = make(material, trange(start + t, d), trange(0, d))
        script.add_segment(seg, track)
        segs.append(seg)
        t += d
    return segs


def build_draft(name: str, mat_dir: Path, renderer, meta: dict, cfg: dict, duration: float,
                intro: Path | None = None) -> Path:
    jc = cfg["jianying"]
    w, h, fps = renderer.w, renderer.h, cfg["video"]["fps"]
    total = int(duration * SEC)
    intro_mat = jy.VideoMaterial(str(intro)) if intro else None
    off = intro_mat.duration if intro_mat else 0   # 有开头时，正片所有轨道整体后移
    # 先在输出目录生成草稿，再复制到剪映目录（商店版 Python 无法直接写 AppData）
    staging = mat_dir.parent / "draft"
    staging.mkdir(exist_ok=True)
    folder = jy.DraftFolder(str(staging))
    script = folder.create_draft(name, w, h, fps=fps, allow_replace=True)
    for track, kind in (("背景", TrackType.video), ("音符", TrackType.video), ("琴键", TrackType.video),
                        ("蒙版", TrackType.video), ("片头", TrackType.video),
                        ("标题", TrackType.text), ("副标题", TrackType.text), ("水印", TrackType.text),
                        ("钢琴", TrackType.audio), ("背景音", TrackType.audio)):
        script.append_track(TrackSpec(kind, track))

    # 背景：图片裁成画布大小并按 bg_dim 压暗；视频按「填充」缩放、循环，用不透明度压暗(画布底色为黑)
    bg = meta.get("background") or jc.get("background")
    dim = float(meta.get("bg_dim", 1.0))
    if bg and Path(bg).suffix.lower() not in IMAGE_EXT:
        mat = jy.VideoMaterial(bg)
        scale = max(w / mat.width, h / mat.height) / min(w / mat.width, h / mat.height)
        _loop(script, "背景", mat, total, lambda m, tr, src: jy.VideoSegment(
            m, tr, source_timerange=src, volume=0,
            clip_settings=ClipSettings(scale_x=scale, scale_y=scale, alpha=dim)), start=off)
    else:
        bg_path = mat_dir / "background.jpg"
        if bg:
            img = ImageOps.fit(Image.open(bg).convert("RGB"), (w, h), Image.LANCZOS)
            img.point(lambda v: v * dim).save(bg_path, quality=95)
        else:
            Image.fromarray((background(w, h, cfg) * 255).astype("uint8")).save(bg_path, quality=95)
        script.add_segment(jy.VideoSegment(str(bg_path), trange(off, total)), "背景")

    # 音符层：黑底 + 滤色 → 黑色部分透明
    notes = jy.VideoMaterial(str(mat_dir / "notes.mp4"))
    seg = jy.VideoSegment(notes, trange(off, min(notes.duration, total)))
    seg.set_mix_mode(jy.MixModeType.滤色)
    script.add_segment(seg, "音符")

    # 琴键层：只有琴键条，移到原来的位置
    keys = jy.VideoMaterial(str(mat_dir / "keys.mp4"))
    y, sh = renderer.strip_box
    script.add_segment(jy.VideoSegment(keys, trange(off, min(keys.duration, total)),
                                       clip_settings=ClipSettings(transform_y=_ty(y + sh / 2, h))), "琴键")

    # 蒙版：文字后面的黑色渐隐层，保证标题不被音符遮挡（可在剪映里调不透明度或删除）
    if (mat_dir / "scrim.png").exists():
        script.add_segment(jy.VideoSegment(str(mat_dir / "scrim.png"), trange(off, total)), "蒙版")

    # 文字：标题、副标题(居中顶部)，水印(琴键下方)；描边 + 阴影保证在任何背景上都清楚
    shadow = TextShadow(alpha=0.7, diffuse=10, distance=3)
    border = TextBorder(alpha=0.55, color=(0, 0, 0), width=25)
    s = jc["text_size"]
    if meta.get("title"):
        script.add_segment(jy.TextSegment(
            meta["title"], trange(off, total), font=_font(meta["title"], cfg),
            style=TextStyle(size=s["title"], color=(0.93, 0.93, 0.93), align=1),
            clip_settings=ClipSettings(transform_y=_ty(h * 0.09, h)), shadow=shadow, border=border), "标题")
    if meta.get("subtitle"):
        script.add_segment(jy.TextSegment(
            meta["subtitle"], trange(off, total), font=_font(meta["subtitle"], cfg),
            style=TextStyle(size=s["subtitle"], color=(0.68, 0.68, 0.68), align=1),
            clip_settings=ClipSettings(transform_y=_ty(h * 0.16, h)), shadow=shadow, border=border), "副标题")
    mark = meta.get("watermark") or jc.get("watermark")
    if mark:
        script.add_segment(jy.TextSegment(
            mark, trange(off, total), font=_font(mark, cfg),
            style=TextStyle(size=s["watermark"], color=(1, 1, 1), alpha=0.75, align=1),
            clip_settings=ClipSettings(transform_y=_ty(min(y + sh + h * 0.04, h * 0.96), h)), shadow=shadow, border=border), "水印")

    # 钢琴音：从第一个音符落下时开始
    lead = int(cfg["timing"]["lead_in"] * SEC)
    piano = jy.AudioMaterial(str(mat_dir / "piano.wav"))
    script.add_segment(jy.AudioSegment(piano, trange(off + lead, min(piano.duration, total - lead))), "钢琴")

    # 背景音：循环铺满，首尾淡入淡出
    bgm = meta.get("bgm") or jc.get("bgm")
    if bgm:
        dst = mat_dir / ("bgm" + Path(bgm).suffix)
        shutil.copy(bgm, dst)
        vol = float(meta.get("bgm_volume", jc["bgm_volume"]))
        segs = _loop(script, "背景音", jy.AudioMaterial(str(dst)), total,
                     lambda m, tr, src: jy.AudioSegment(m, tr, source_timerange=src, volume=vol), start=off)
        if len(segs) == 1:
            segs[0].add_fade("2s", "3s")
        else:
            segs[0].add_fade("2s", "0s")
            segs[-1].add_fade("0s", "3s")

    # 片头：放在最上层视频轨，自带高潮片段音频；删掉它并把后面整体前移即可得到无开头版本
    if intro_mat:
        script.add_segment(jy.VideoSegment(intro_mat, trange(0, intro_mat.duration)), "片头")

    script.save()
    return _install(staging / name, _draft_dir(cfg) / name)


def _install(src: Path, dst: Path) -> Path:
    """用 robocopy 镜像到剪映草稿目录（退出码 < 8 表示成功）。"""
    r = subprocess.run(["robocopy", str(src), str(dst), "/MIR", "/NJH", "/NJS", "/NFL", "/NDL"],
                       capture_output=True)
    if r.returncode >= 8:
        raise RuntimeError(f"复制草稿到剪映目录失败 (robocopy {r.returncode}): {dst}")
    return dst
