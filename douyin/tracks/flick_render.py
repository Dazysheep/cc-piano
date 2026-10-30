"""用图库一键生成拨片开头：视频（带滑动音效）+ 封面 + 单独的音效 wav + 剪映草稿（开头 + 音效分轨）。

用法: python tracks/flick_render.py [--title 歌名 --artist 歌手] [--seconds 4] [--vertical] [--no-draft]
输出：<成片位置>/开头_<日期>_<标题>/intro.mp4、intro.jpg、intro_sfx.wav；剪映草稿「拨片开头_<标题>_<时间>」
     （成片位置见 piano/storage.py：默认 D 盘 cc-engine/douyin/待上传，可在设置里改）
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "piano"))
import flick_intro  # noqa: E402
import imageio_ffmpeg  # noqa: E402
import flick_lib  # noqa: E402

_json = False


def emit(stage: str, msg: str, pct: float | None = None, **extra) -> None:
    if _json:
        print("@@" + json.dumps({"stage": stage, "msg": msg, "pct": pct, **extra}, ensure_ascii=False), flush=True)
    else:
        print(f"  {msg}" + (f" {pct:.0%}" if pct is not None else ""), flush=True)


def make_draft(intro: Path, sfx_wav: Path, w: int, h: int, name: str) -> Path:
    import pyJianYingDraft as jy
    import render as piano_render
    from jianying import _draft_dir, _install
    from pyJianYingDraft import TrackSpec, TrackType, trange

    cfg = piano_render.load_config({})
    staging = ROOT / "output" / "flick_draft_staging"   # 草稿先写到这里再复制进剪映，不放在待上传里
    staging.mkdir(exist_ok=True)
    script = jy.DraftFolder(str(staging)).create_draft(name, w, h, fps=30, allow_replace=True)
    script.append_track(TrackSpec(TrackType.video, "开头"))
    script.append_track(TrackSpec(TrackType.audio, "音效"))
    m = jy.VideoMaterial(str(intro))
    script.add_segment(jy.VideoSegment(m, trange(0, m.duration), volume=0.0), "开头")   # 视频自带的音效静音
    fx = jy.AudioMaterial(str(sfx_wav))
    script.add_segment(jy.AudioSegment(fx, trange(0, min(fx.duration, m.duration))), "音效")   # 单独一轨，方便剪
    script.save()
    return _install(staging / name, _draft_dir(cfg) / name)


def main() -> int:
    global _json
    ap = argparse.ArgumentParser(description="拨片开头")
    ap.add_argument("--title", default="")
    ap.add_argument("--artist", default="")
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--vertical", action="store_true")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--no-draft", action="store_true")
    ap.add_argument("--json-progress", action="store_true")
    a = ap.parse_args()
    _json = a.json_progress
    w, h = (1080, 1920) if a.vertical else (1920, 1080)
    try:
        others, final = flick_lib.sequence()
    except RuntimeError as e:
        emit("error", str(e))
        return 1
    slug = re.sub(r'[\\/:*?"<>|\s]+', "_", a.title).strip("_") or "未命名"
    import storage                       # 成片保存位置：默认 D:\cc-engine\douyin\待上传，可在设置里改
    dest = storage.deliver_dir() / f"开头_{datetime.now():%Y%m%d_%H%M}_{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "intro.mp4"
    emit("frames", f"正在渲染开头（{len(others) + 1} 张卡片）", 0)
    silent = dest / "intro_silent.mp4"
    info = flick_intro.render(final, others, silent, w, h, a.fps, a.seconds, a.title, a.artist,
                              progress=lambda f, n: emit("frames", "正在渲染开头", f / n))
    emit("frames", "正在合成音效", 0.97)
    sfx_wav = info["sfx"].rename(dest / "intro_sfx.wav")
    silent.with_suffix(".jpg").replace(dest / "intro.jpg")
    (dest / "intro_silent_last.png").replace(dest / "intro_last.png")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", silent, "-i", sfx_wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", out], check=True)
    silent.unlink()
    result = {"video": str(out), "cover": str(out.with_suffix(".jpg")), "sfx": str(sfx_wav), "folder": str(dest),
              "draft": None}
    if not a.no_draft:
        emit("draft", "正在生成剪映草稿", 0.98)
        result["draft"] = str(make_draft(out, sfx_wav, w, h, f"拨片开头_{slug}_{datetime.now():%m%d_%H%M}"))
    emit("done", "开头已生成", 1, result=result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
