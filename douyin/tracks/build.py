"""音轨剪辑作品：拨片下滑开头 + 多轨时间线正片 + 音乐 → 成片 + 两份剪映草稿。

用法: python tracks/build.py tracks/songs/one_more_light.json [--fps 60] [--work 目录] [--preview 秒]
歌曲配置(json)：title / artist / audio(音频文件) / start(截取起点秒，"auto" 用 prepare.py 选好的片段) /
              duration(总时长，含开头) / intro(开头秒数) / final_image(开头最后停留的图) / images(开头滑过的其他图)
可选效果：theme("sunset"|"tech"|"classical") / backdrop(true：封面虚化做背景，面板变毛玻璃) /
         grain(颗粒强度，如 0.07) / fireworks(true：副歌放烟花) / lyrics(true：底部歌词 + 唱歌的像素小人，
         需要 prepare.py 生成的 lyrics.json；lyrics_zh 给每句的中文翻译) /
         loop(true：开头第一帧就是主图，结尾主图飞回中央，首尾相接)
模板：template("daw@v2")引用 tracks/templates 里的模板，竖屏、卡点、钩子文案等字段见 template_lib.py
产出：
  待上传/<日期>_<歌名>/video.mp4、cover.jpg、publish.md
  剪映草稿 1：<歌名>_开头_<时间>（开头 + 滑动音效）
  剪映草稿 2：<歌名>_作品_<时间>（开头 / 正片 / 音乐 / 音效分轨，可分别编辑）
  音效单独输出为 待上传/.../intro_sfx.wav（卡片拨动声 + 落定闷响 + 水墨转场「呼」声）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "piano"))
import daw  # noqa: E402
import flick_intro  # noqa: E402
import sfx  # noqa: E402

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SFX_GAIN = 0.7          # 音效相对音量（成片和草稿一致）
LYRIC_BAND = 190        # 底部歌词区高度
DUO_BAND = 170          # 两人模式（cast: duo）的舞台带：小人缩小后矮一些
DUO_LYRIC_X1 = 1080     # 两人模式：女生的歌词最右到这里，右半边是男生和评论文件夹
JSON_PROGRESS = False   # 琴房网页调用时用 @@{json} 行报告进度


def emit(stage: str, msg: str, pct: float | None = None, **extra) -> None:
    if JSON_PROGRESS:
        print("@@" + json.dumps({"stage": stage, "msg": msg, "pct": pct, **extra}, ensure_ascii=False), flush=True)
    else:
        print(msg, flush=True)


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def make_view(work: Path, song: dict, intro: dict, t_from: float, t_last: float, cover: Path) -> tuple:
    """按歌曲配置组装正片画面（主题、背景、歌词小人、烟花），返回 (DawView, Grain 或 None)。"""
    import stage
    import themes
    th = themes.get(song.get("theme"))
    backdrop = daw.make_backdrop(Image.open(cover)) if song.get("backdrop") else None
    ly = None
    if song.get("lyrics") and (work / "lyrics.json").exists():
        ly = json.loads((work / "lyrics.json").read_text(encoding="utf-8"))
    import comment_scene
    duo = song.get("cast") == "duo" and bool(song.get("story"))     # 两人模式：女生唱歌 + 男生读评论
    bottom = DUO_BAND if duo else comment_scene.STAGE_BAND if song.get("story") else (LYRIC_BAND if ly else 0)
    view = daw.DawView(work, song["title"], song["artist"], song["start"], intro=intro, t_entry=t_from,
                       theme=song.get("theme"), backdrop=backdrop, bottom=bottom,
                       outro=intro.get("first") if song.get("loop") else None, t_last=t_last,
                       pulse=float(song.get("pulse") or 0), keep=song.get("tracks_keep"))
    s0, dur = song["start"], song["duration"]
    chorus = [[a - s0, b - s0] for a, b in (ly or {}).get("chorus", []) if b > s0 and a < s0 + dur]
    if song.get("fireworks"):
        if not chorus:                          # 没有歌词时按原曲能量找高潮
            chorus = loud_spans(view)
        area = (daw.TL_X, daw.LANE_TOP, daw.W, daw.H - bottom)
        fw = stage.Fireworks([[max(a, t_from + daw.ENTRY), min(b, t_last - daw.OUTRO)] for a, b in chorus],
                             view.beats, th["fireworks"], area)
        view.overlays.append(fw)
    lines = []
    if ly:
        zh = {**ly.get("zh", {}), **song.get("lyrics_zh", {})}    # 贴的歌词自带翻译，歌曲里写的优先
        for ln in ly["lines"]:
            if ln["end"] < s0 or ln["start"] > s0 + dur:
                continue
            lines.append({"start": ln["start"] - s0, "end": ln["end"] - s0, "text": ln["text"],
                          "zh": zh.get(ln["text"], ""),
                          "words": [[w, s - s0, e - s0] for w, s, e in ln["words"]]})
    show_lyrics = True
    if not lines and song.get("cast") == "duo" and (work / "whisper_words.json").exists():
        words = json.loads((work / "whisper_words.json").read_text(encoding="utf-8"))
        cur = []
        for w in words + [None]:                 # 停顿超过 0.8 秒就算新的一句
            if w is None or (cur and w["s"] - cur[-1]["e"] > 0.8):
                if cur:
                    lines.append({"start": cur[0]["s"] - s0, "end": cur[-1]["e"] - s0,
                                  "text": " ".join(x["w"] for x in cur), "zh": "",
                                  "words": [[x["w"], x["s"] - s0, x["e"] - s0] for x in cur]})
                cur = []
            if w is not None:
                cur.append(w)
        lines = [ln for ln in lines if ln["end"] > 0 and ln["start"] < dur]
        show_lyrics = False
    if ly and not song.get("story"):     # 有评论故事时，底部舞台给读评论的小人（唱歌的小人不出场）
        view.overlays.append(stage.Singer(lines, th, view.env["vocals"].max(axis=1), view.rate, view.beats, chorus,
                                          daw.H - bottom))
    if song.get("story"):
        cards, finale = schedule_story(song["story"], view, t_from, t_last)
        if finale and song.get("ending"):
            finale["t1"] = min(finale["t1"], t_last - float(song.get("ending_seconds", 10)) + 0.4)
        avoid = None
        if duo:                          # 卡片让开男生头顶的想象云朵
            import duo_scene
            x0, y0, x1, y1 = comment_scene.cloud_box(comment_scene.duo_home(duo_scene.SCALE), duo_scene.SCALE)
            avoid = (x0 - 20, y0 - 20, daw.W, daw.H)
        story = stage.CommentStory(cards, finale, th, view, avoid=avoid)
        if duo:                          # 女生左下角唱歌，男生右边读评论想画面，结尾两人走到中间鞠躬
            import duo_scene
            walk = duo_scene.finale_times(finale, t_last)
            gx, bx = duo_scene.meet_points()
            exit_ = bool(song.get("ending"))
            if exit_:                    # 有结尾小剧场：两人在小窗浮现前走出画面（回家），鞠躬放到小剧场里
                walk = t_last - float(song.get("ending_seconds", 10)) - 1.6
                gx, bx = -260, daw.W + 260
            scene = comment_scene.CommentScene(story, th, view, band=DUO_BAND, scale=duo_scene.SCALE,
                                               visions_on=True, bow_finale={"walk": walk, "x": bx, "exit": exit_},
                                               center_min=DUO_LYRIC_X1 + 170, pace=float(song.get("pace", 1.0)))
            reactions = [(c["t0"], c["t0"] + 3.0, c["girl"]) for c in cards if c.get("girl")]
            girl = duo_scene.SingerGirl(lines, th, view.env["vocals"].max(axis=1), view.rate, view.beats, chorus,
                                        scene.floor, x1=DUO_LYRIC_X1,
                                        finale={"walk": walk, "x": gx, "exit": exit_},
                                        show_lyrics=show_lyrics, reactions=reactions,
                                        lyric_size=song.get("lyric_size"))
            if song.get("solos") or song.get("moments"):          # 只听某一轨 + 跟歌词走的主题动画（画在小人和卡片下面）
                import moments
                if song.get("solos"):
                    view.overlays.append(moments.SoloLanes(song["solos"], view))
                if song.get("moments"):
                    view.overlays.append(moments.Moments(song["moments"], bottom=DUO_BAND))
                    for cl in scene.clouds:                  # 主题动画出现时，男生的想象云朵先收起来
                        for m in song["moments"]:
                            if cl["a"] < float(m["from"]) < cl["b"]:
                                cl["b"] = max(cl["a"] + 1.2, float(m["from"]) - 0.1)
            view.overlays += [scene, girl, story]
        else:
            view.overlays.append(comment_scene.CommentScene(story, th, view))   # 先画舞台和小人，再画飞出来的卡片
            view.overlays.append(story)
    if song.get("ending"):               # 结尾小剧场：画面中间浮现小窗（最后画，盖在最上面）
        import ending
        dur_end = float(song.get("ending_seconds", 10))
        view.overlays.append(ending.HomeEnding(ending.load_script(song["ending"]), Image.open(cover), song["title"],
                                               song["artist"], t_last - dur_end, t_last))
    grain = stage.Grain(float(song["grain"])) if song.get("grain") else None
    return view, grain


def schedule_story(story: dict, view, t_from: float, t_last: float) -> tuple[list[dict], dict | None]:
    """评论故事排期：每一幕 {from, to, cards:[{text, track, solo}]} 里的卡片平均分布，出现时刻吸附到重拍；
    独白卡片（solo）一条接一条不重叠，其他卡片停留约两个间隔（同时有好几条在画面上）。
    尾声 finale {from, text, sub} 一直显示到结尾转场之前。时间都是视频时间（秒）。"""
    downs = view.downbeats

    def snap(x: float) -> float:
        return float(downs[np.argmin(np.abs(downs - x))]) if len(downs) else x

    start_ok = t_from + daw.ENTRY + 0.2
    cards = []
    for act in story.get("acts", []):
        a, b = max(float(act["from"]), start_ok), float(act["to"])
        n = len(act["cards"])
        if n == 0 or b <= a:
            continue
        step = (b - a) / n
        for i, c in enumerate(act["cards"]):
            t0 = max(start_ok, snap(a + i * step))
            hold = step * (0.88 if c.get("solo") else 2.1)
            cards.append({**c, "t0": round(t0, 3), "t1": round(min(t0 + max(hold, 1.6), b), 3)})
    finale = None
    if story.get("finale"):
        f = story["finale"]
        end = t_last - (daw.OUTRO if view.outro else 0.0)
        finale = {**f, "t0": round(snap(float(f["from"])), 3), "t1": round(end, 3)}
    return cards, finale


def loud_spans(view) -> list[list[float]]:
    """原曲电平最高的段落（平滑后前 20%，至少 8 秒）。"""
    lv = view.level["mix"]
    k = view.rate * 4
    sm = np.convolve(lv, np.ones(k) / k, mode="same")
    on = sm > np.percentile(sm, 80)
    spans, s = [], None
    for i, v in enumerate(np.append(on, False)):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if (i - s) / view.rate >= 8:
                spans.append([s / view.rate, i / view.rate])
            s = None
    return spans


def _h264(out: Path, fps: int):
    w = imageio_ffmpeg.write_frames(str(out), (daw.W, daw.H), fps=fps, codec="libx264", pix_fmt_out="yuv420p",
                                    quality=None, output_params=["-crf", "17", "-preset", "fast"],
                                    macro_block_size=1, ffmpeg_log_level="error")
    w.send(None)
    return w


def matte(layers: list, t: float) -> np.ndarray:
    """只把 layers 画成带透明通道的一帧（RGBA）：同一帧分别画在黑底和白底上，
    两张的差就是透明度（叠加层都是贴图和压暗，这样抠出来是精确的），颜色 = 黑底结果 ÷ 透明度。"""
    k = Image.new("RGB", (daw.W, daw.H), (0, 0, 0))
    w = Image.new("RGB", (daw.W, daw.H), (255, 255, 255))
    for ov in layers:
        ov(k, t)
        ov(w, t)
    kb = np.asarray(k)
    a = 255 - (np.asarray(w) - kb).max(axis=2)            # 白底 ≥ 黑底，uint8 相减不会溢出
    rgb = kb.astype(np.uint16) * 255                        # 最大 65025，uint16 放得下（省内存，int32 要两倍）
    rgb //= np.maximum(a, 1).astype(np.uint16)[..., None]
    out = np.empty((daw.H, daw.W, 4), np.uint8)
    out[..., :3] = np.minimum(rgb, 255)
    out[..., 3] = a
    out[a == 0, :3] = 0
    return out


def render_main(view, grain, out: Path, fps: int, t_from: float, n: int, span=(0.0, 1.0),
                layers: list | None = None) -> Path:
    """layers：要单独输出的叠加层（评论卡片和读评论的小人）。给了的话，除了 out（成片用，叠加层画在里面，
    和不分层时完全一样），还在旁边输出 main_clean.mp4（不带这些层）和 comments.webm（只有这些层，透明背景），
    剪辑页的 OpenFilm 工程用它们，评论层可以单独调整。"""
    # 正片开头 daw.ENTRY 秒是水墨转场：墨晕开露出编曲界面，主图飞进标题栏小图位置（第一帧与开头最后一帧一致）
    writer = _h264(out, fps)
    clean = alpha = None
    if layers:
        view.overlays = [o for o in view.overlays if o not in layers]
        clean = _h264(out.with_name("main_clean.mp4"), fps)
        alpha = imageio_ffmpeg.write_frames(str(out.with_name("comments.webm")), (daw.W, daw.H), fps=fps,
                                            pix_fmt_in="rgba", codec="libvpx-vp9", pix_fmt_out="yuva420p",
                                            quality=None, macro_block_size=1, ffmpeg_log_level="error",
                                            output_params=["-b:v", "0", "-crf", "30", "-deadline", "realtime",
                                                           "-cpu-used", "8", "-row-mt", "1", "-auto-alt-ref", "0"])
        alpha.send(None)
    t0 = time.time()
    for f in range(n):
        t = t_from + f / fps
        im = view.frame(t)
        amt = view.progress(t) if grain else 0.0
        if clean:
            clean.send((grain.apply(im, f, amt) if amt > 0.001 else np.asarray(im)).tobytes())
            alpha.send(matte(layers, t).tobytes())
            for ov in layers:
                ov(im, t)
        data = grain.apply(im, f, amt) if amt > 0.001 else np.asarray(im)
        writer.send(data.tobytes())
        if f % (fps * 2) == 0:
            left = (time.time() - t0) / max(f, 1) * (n - f)
            emit("frames", f"渲染正片 {f}/{n} 帧，约剩 {left / 60:.0f} 分钟" if f else "渲染正片",
                 span[0] + (span[1] - span[0]) * f / n)
    writer.close()
    if clean:
        clean.close()
        alpha.close()
        view.overlays += layers
    return out


def render_lock():
    """同一时间只渲染一个（命令行出片、每日制作、分段修改页的预览都走这里）：两个渲染同时跑时
    ffmpeg 管道会断（2026-10-27 整片两次中断）。拿不到锁就等，进程结束时锁自动释放。"""
    import msvcrt
    path = ROOT / "output" / ".render.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    waited = False
    while True:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            if not waited:
                emit("queue", "等前一个渲染结束……", 0.0)
                waited = True
            time.sleep(3)


def range_mux(mat: Path, video: Path, song: dict, work: Path, out_dir: Path, a: float, b: float,
              sfx_wav: Path | None) -> Path:
    """分段预览：画面 + 成片里 [a, b] 秒的音乐（「只听某一轨」也换好）+ 开头音效，720p 小文件。"""
    import soundfile as sf
    src, sr = sf.read(str(work / "source.wav"), dtype="float32", always_2d=True)
    if song.get("solos"):
        import moments
        stems = {}
        for s_ in song["solos"]:
            f = work / "stems" / f"{s_['track']}.wav"
            if f.exists() and s_["track"] not in stems:
                x, _ = sf.read(str(f), dtype="float32", always_2d=True)
                stems[s_["track"]] = x[: len(src)] if len(x) >= len(src) else np.pad(x, ((0, len(src) - len(x)), (0, 0)))
        moments.solo_music(src, stems, sr, float(song["start"]), song["solos"], out_dir / "range_music.wav")
        src, sr = sf.read(str(out_dir / "range_music.wav"), dtype="float32", always_2d=True)
    i0, i1 = int((float(song["start"]) + a) * sr), int((float(song["start"]) + b) * sr)
    sf.write(str(out_dir / "range_music.wav"), src[max(0, i0):max(0, i1)], sr)
    out = out_dir / "range.mp4"
    inputs = ["-i", video, "-i", out_dir / "range_music.wav"]
    mix = "[1:a]anull[a]"
    if sfx_wav:
        inputs += ["-i", sfx_wav]
        mix = f"[2:a]volume={SFX_GAIN}[fx];[1:a][fx]amix=inputs=2:duration=first:normalize=0[a]"
    run([FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", f"[0:v]scale=-2:720[v];{mix}",
         "-map", "[v]", "-map", "[a]", "-t", f"{b - a:.3f}", "-c:v", "libx264", "-crf", "24", "-preset", "fast",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    return out


def beat_timing(work: Path, song: dict) -> dict:
    """卡点：开头取整数小节（结束在重拍上），水墨转场取整数拍，淡入淡出按拍数。
    返回 {intro, entry, fade_in, fade_out}；没开 snap_beats 时是原来的固定值。"""
    out = {"intro": song["intro"], "entry": daw.ENTRY,
           "fade_in": 1.0, "fade_out": 1.5}
    a = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
    beats = a["beats"][::2] if a["tempo"] > 140 else a["beats"]
    if len(beats) < 8:
        return out
    beat = float(np.median(np.diff(beats)))
    if song.get("fade_in_beats") is not None:
        out["fade_in"] = max(0.05, float(song["fade_in_beats"]) * beat)
    if song.get("fade_out_beats") is not None:
        out["fade_out"] = max(0.3, float(song["fade_out_beats"]) * beat)
    if not song.get("snap_beats"):
        return out
    d = a.get("downbeat", 0)
    # 开头小节数：按 intro 秒数取整（偏向短一些，慢歌不会拖得太长）
    bars = int(song.get("intro_bars") or max(1, int(song["intro"] / (4 * beat) + 0.25)))
    if song.get("opening") and not song.get("intro_bars"):   # 开头小剧场：从第一个重拍算起，结束在最接近 intro 秒的重拍
        bars = max(1, round((song["intro"] - beats[d]) / (4 * beat)))
    i_end = d + 4 * bars
    if i_end >= len(beats):
        return out
    out["intro"] = round(beats[i_end], 3)
    k = max(2, round(daw.ENTRY / beat))                  # 转场约 1.8 秒，取整数拍
    if i_end + k < len(beats):
        out["entry"] = round(beats[i_end + k] - beats[i_end], 3)
    return out


def hook_png(text: str, path: Path) -> Path:
    """开头钩子文案：画面上方的大字（白字 + 深色描边和投影），透明底 PNG。"""
    from PIL import ImageDraw, ImageFilter, ImageFont
    im = Image.new("RGBA", (daw.W, daw.H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = 76 if daw.W < daw.H else 64
    max_w = daw.W * 0.86
    path_f = "C:/Windows/Fonts/msyhbd.ttc"
    f = ImageFont.truetype(path_f, size)
    while d.textlength(text, font=f) > max_w and size > 58:   # 先缩小字号争取一行放下
        size -= 2
        f = ImageFont.truetype(path_f, size)
    lines = [text]
    if d.textlength(text, font=f) > max_w:              # 还放不下：按总宽度均分成几行，避免最后一行只剩一个字
        n = int(d.textlength(text, font=f) // max_w) + 1
        per = d.textlength(text, font=f) / n
        lines, cur = [], ""
        for ch in text:
            if d.textlength(cur + ch, font=f) > per * 1.08 and cur and len(lines) < n - 1:
                lines.append(cur)
                cur = ""
            cur += ch
        lines.append(cur)
    y = int(daw.H * (0.13 if daw.W < daw.H else 0.12))
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    for i, ln in enumerate(lines):
        yy = y + i * int(size * 1.3)
        ds.text((daw.W / 2, yy + 4), ln, font=f, fill=(0, 0, 0, 200), anchor="mm")
        d.text((daw.W / 2, yy), ln, font=f, fill=(255, 255, 255, 255), anchor="mm",
               stroke_width=4, stroke_fill=(20, 16, 24, 230))
    im = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)), im)
    im.save(path)
    return path


def build_drafts(name: str, song: dict, intro: Path, main: Path, music: Path, t_from: float,
                 sfx_wav: Path, outro_wav: Path | None, fades: tuple[float, float] = (1.0, 1.5)) -> list[Path]:
    import pyJianYingDraft as jy
    from pyJianYingDraft import TrackSpec, TrackType, trange
    from jianying import _draft_dir, _install
    import render as piano_render

    cfg = piano_render.load_config({})
    staging = main.parent / "draft"
    staging.mkdir(exist_ok=True)
    folder = jy.DraftFolder(str(staging))
    sec = 1_000_000
    stamp = datetime.now().strftime("%m%d_%H%M")
    out = []

    # 草稿 1：开头 + 滑动音效（音效截到开头长度）
    d1 = f"{name}_开头_{stamp}"
    s1 = folder.create_draft(d1, daw.W, daw.H, fps=30, allow_replace=True)
    s1.append_track(TrackSpec(TrackType.video, "开头"))
    s1.append_track(TrackSpec(TrackType.audio, "音效"))
    im = jy.VideoMaterial(str(intro))
    s1.add_segment(jy.VideoSegment(im, trange(0, im.duration)), "开头")
    fx = jy.AudioMaterial(str(sfx_wav))
    s1.add_segment(jy.AudioSegment(fx, trange(0, min(fx.duration, im.duration)), volume=SFX_GAIN), "音效")
    s1.save()
    out.append(_install(staging / d1, _draft_dir(cfg) / d1))

    # 草稿 2：完整作品，开头 / 正片 / 音乐分轨
    d2 = f"{name}_作品_{stamp}"
    total = int(song["duration"] * sec)
    s2 = folder.create_draft(d2, daw.W, daw.H, fps=30, allow_replace=True)
    for tr, kind in (("正片", TrackType.video), ("开头", TrackType.video), ("音乐", TrackType.audio),
                     ("音效", TrackType.audio)):
        s2.append_track(TrackSpec(kind, tr))
    mm = jy.VideoMaterial(str(main))
    start_main = int(t_from * sec)
    s2.add_segment(jy.VideoSegment(mm, trange(start_main, min(mm.duration, total - start_main))), "正片")
    s2.add_segment(jy.VideoSegment(im, trange(0, im.duration)), "开头")   # 正片自带转场，接缝处无需动画
    am = jy.AudioMaterial(str(music))
    a = jy.AudioSegment(am, trange(0, total), source_timerange=trange(int(song["start"] * sec), total))
    a.add_fade(f"{fades[0]:g}s", f"{fades[1]:g}s")
    s2.add_segment(a, "音乐")
    s2.add_segment(jy.AudioSegment(fx, trange(0, fx.duration), volume=SFX_GAIN), "音效")   # 含转场「呼」声
    if outro_wav:                                                                          # 结尾飞回的「呼」声
        om = jy.AudioMaterial(str(outro_wav))
        o_start = max(fx.duration, total - om.duration)
        s2.add_segment(jy.AudioSegment(om, trange(o_start, min(om.duration, total - o_start)), volume=SFX_GAIN),
                       "音效")
    s2.save()
    out.append(_install(staging / d2, _draft_dir(cfg) / d2))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="音轨剪辑作品")
    ap.add_argument("song", type=Path)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--work", type=Path, help="已有的分析目录（含 analysis.json、env_*.npy）")
    ap.add_argument("--preview", type=float, help="只渲染正片前 N 秒（不出成片和草稿），检查效果用")
    ap.add_argument("--no-draft", action="store_true")
    ap.add_argument("--no-layers", action="store_true", help="有评论故事时不单独输出评论透明层（省时间）")
    ap.add_argument("--prepare", action="store_true",
                    help="先运行 prepare.py（分离、歌词、选片段、分析，已完成的会跳过）")
    ap.add_argument("--json-progress", action="store_true")
    ap.add_argument("--range", type=float, nargs=2, metavar=("FROM", "TO"),
                    help="只渲染成片里这一段（秒，带音乐），分段修改时预览用；不出成片和草稿")
    args = ap.parse_args()
    global JSON_PROGRESS, RENDER_LOCK
    JSON_PROGRESS = args.json_progress
    RENDER_LOCK = render_lock()
    import template_lib
    song = template_lib.load_song(args.song)
    if song.get("vertical"):
        daw.set_canvas(True)
    base = args.song.parent
    slug = song["title"].replace(" ", "_")
    work = args.work
    if args.prepare:
        import prepare
        work = prepare.run(args.song, work,
                           emit=lambda st, msg, pct=None: emit(st, msg, None if pct is None else pct * 0.4))
    if work is None:
        prepared = ROOT / "output" / f"tracks_{slug}" / "work"
        work = prepared if (prepared / "analysis.json").exists() else ROOT / "output" / f"tracks_{slug}"
    if not (work / "analysis.json").exists():
        print("缺少分析结果，请先运行 tracks/prepare.py（或 tracks/analyze.py）", file=sys.stderr)
        return 1
    if song.get("start") == "auto" or (work / "song.json").exists() and song.get("lyrics"):
        resolved = json.loads((work / "song.json").read_text(encoding="utf-8"))
        song["start"], song["duration"] = resolved["start"], resolved["duration"]
    mat = ROOT / "output" / f"tracks_{slug}" / datetime.now().strftime("%Y%m%d_%H%M%S")
    mat.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    timing = beat_timing(work, song)
    song["intro"] = timing["intro"]
    daw.ENTRY = timing["entry"]

    # 1. 开头
    intro = mat / "intro.mp4"
    if song.get("opener"):                         # 「开头设计」的模板（tracks/openers）：翻译成下面原来就认识的字段
        import openers
        openers.apply_to_song(song)
    if song.get("intro_from_library"):            # 用「拨片开头」图库里的图片和顺序（intro_final 指定主图）
        import flick_lib
        others, final = flick_lib.sequence(final=song.get("intro_final"))
        if song.get("intro_images"):              # 模板指定了用哪几张专辑、按什么顺序
            others = [flick_lib.LIB_DIR / f for f in song["intro_images"]
                      if (flick_lib.LIB_DIR / f).exists() and flick_lib.LIB_DIR / f != final] or others
    else:
        others = [(base / p).resolve() for p in song.get("images", [])]
        final = (base / song["final_image"]).resolve()
    emit("intro", "渲染拨片开头", 0.4)
    text = song.get("intro_text", True)           # false：拨片开头不写歌名歌手
    rng = args.range
    in_intro = bool(rng) and rng[0] < song["intro"] - 0.5       # 起点在开头里：只预览开头（正片的段都从开头之后开始）
    fps_intro = 4 if rng and not in_intro else args.fps     # 只预览正片的一段：开头只为拿转场用的画面，低帧率快速过
    if song.get("opening"):                        # 开头小剧场（最后接上拨片开头），歌名由小剧场自己画
        import opening
        emit("intro", "渲染开头小剧场", 0.4)
        intro_info = opening.render(opening.load_script(song["opening"]), final, others, intro, song["intro"],
                                    fps_intro, song["title"], song["artist"], sfx_tail=daw.ENTRY)
    else:
        intro_info = flick_intro.render(final, others, intro, daw.W, daw.H, fps_intro, song["intro"],
                                        song["title"] if text else "", song["artist"] if text else "",
                                        sfx_tail=daw.ENTRY, whoosh_at=song["intro"] - 0.15,
                                        loop_start=bool(song.get("loop")))
    emit("intro", f"开头完成 ({time.time() - t0:.0f}s)", 0.45)
    if in_intro:                                   # 分段预览：只要开头
        out = range_mux(mat, intro, song, work, mat, 0.0, song["intro"], intro_info["sfx"])
        emit("done", "预览完成", 1.0, result={"video": str(out), "preview": True, "range": [0.0, song["intro"]]})
        return 0

    # 2. 正片：紧接开头，从第 intro 秒开始（自带转场）
    t_from = song["intro"]
    n = int(round((song["duration"] - t_from) * args.fps))
    t_last = t_from + (n - 1) / args.fps
    view, grain = make_view(work, song, intro_info, t_from, t_last, final)
    if rng:                                        # 分段预览：只渲染正片里的这一段，配上那几秒的音乐
        a, b = max(rng[0], t_from), min(rng[1], song["duration"])
        part = render_main(view, grain, mat / "range_v.mp4", args.fps, a, int(round((b - a) * args.fps)),
                           span=(0.45, 0.95))
        out = range_mux(mat, part, song, work, mat, a, b, None)
        emit("done", "预览完成", 1.0, result={"video": str(out), "preview": True, "range": [a, b]})
        return 0
    if args.preview:
        n = int(args.preview * args.fps)
    layers = None
    if song.get("story") and not args.preview and not args.no_layers:   # 评论层单独输出，剪辑页里可以单独调整
        import comment_scene
        import stage
        import duo_scene
        import ending
        layers = [o for o in view.overlays
                  if isinstance(o, (comment_scene.CommentScene, stage.CommentStory, duo_scene.SingerGirl,
                                    ending.HomeEnding))]
    main_v = render_main(view, grain, mat / "main.mp4", args.fps, t_from, n, span=(0.45, 0.95), layers=layers)
    emit("frames", f"正片完成 ({time.time() - t0:.0f}s)", 0.95)
    if args.preview:
        emit("done", "预览完成", 1.0, result={"video": str(main_v), "cover": str(intro.with_suffix(".jpg")),
                                          "preview": True})
        return 0

    # 3. 音乐：截取 + 淡入淡出（草稿里用原始文件 + 截取范围）
    if Path(song["audio"]).suffix.lower() in (".mp4", ".mov"):   # 录屏：只取声音（剪映草稿的音频素材不能带画面）
        music_src = mat / "music.m4a"
        run([FFMPEG, "-y", "-loglevel", "error", "-i", song["audio"], "-vn", "-c:a", "copy", music_src])
    else:
        music_src = mat / ("music" + Path(song["audio"]).suffix)
        shutil.copy(song["audio"], music_src)
    if song.get("solos"):                         # 只听某一轨：那几秒换成分离音轨（前后交叉淡化）
        import soundfile as sf
        import moments
        src, sr = sf.read(str(work / "source.wav"), dtype="float32", always_2d=True)
        stems = {}
        for s_ in song["solos"]:
            f = work / "stems" / f"{s_['track']}.wav"
            if f.exists() and s_["track"] not in stems:
                x, _ = sf.read(str(f), dtype="float32", always_2d=True)
                stems[s_["track"]] = x[: len(src)] if len(x) >= len(src) else np.pad(x, ((0, len(src) - len(x)), (0, 0)))
        for old in mat.glob("music.*"):
            old.unlink()
        music_src = mat / "music.wav"
        moments.solo_music(src, stems, sr, float(song["start"]), song["solos"], music_src)
    dur = song["duration"]
    outro_wav = None
    if song.get("loop"):                          # 结尾主图飞回中央时的「呼」声
        outro_wav = sfx.write_wav(mat / "outro_sfx.wav", sfx.ink_whoosh(daw.OUTRO * 0.8) * 0.8)

    # 4. 成片：开头 + 正片首尾相接，配音乐 + 音效
    import storage                       # 成片保存位置：默认 D:\cc-engine\douyin\待上传，可在设置里改
    dest = storage.deliver_dir() / f"{datetime.now():%Y%m%d_%H%M}_{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    video = dest / "video.mp4"
    inputs = ["-i", intro, "-i", main_v, "-i", music_src, "-i", intro_info["sfx"]]
    fx_mix = f"[3:a]volume={SFX_GAIN},apad[fx];"
    mix_in = "[m][fx]"
    n_in = 2
    if outro_wav:
        inputs += ["-i", outro_wav]
        delay = int((dur - daw.OUTRO) * 1000)
        fx_mix += f"[4:a]adelay={delay}|{delay},volume={SFX_GAIN},apad[ox];"
        mix_in += "[ox]"
        n_in = 3
    fi, fo = timing["fade_in"], timing["fade_out"]
    hook = song.get("hook_text")
    v_out = "[v]"
    if hook:                                       # 开头 0~3 秒的大字钩子文案，淡入淡出
        inputs += ["-loop", "1", "-t", "3.2", "-i", hook_png(hook, mat / "hook.png")]
        v_out = "[v0]"
    vf = (f"[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p{v_out};"
          f"[2:a]atrim=start={song['start']}:duration={dur},asetpts=PTS-STARTPTS,"
          f"afade=t=in:d={fi:.3f},afade=t=out:st={dur - fo:.3f}:d={fo:.3f},"
          f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[m];"
          f"{fx_mix}"
          f"{mix_in}amix=inputs={n_in}:duration=first:normalize=0,alimiter=limit=0.95[a]")
    if hook:
        hk = n_in + 2                              # 钩子图片是最后一个输入
        vf += (f";[{hk}:v]format=rgba,fade=t=in:st=0:d=0.15:alpha=1,fade=t=out:st=2.7:d=0.45:alpha=1[hk];"
               f"[v0][hk]overlay=0:0:eof_action=pass,format=yuv420p[v]")
    run([FFMPEG, "-y", "-loglevel", "error", *inputs,
         "-filter_complex", vf, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
         # 颗粒噪点很难压缩，不限码率时 100 秒能到 2GB 以上；限 16Mbps（抖音 1080p 足够）
         "-c:v", "libx264", "-crf", "18", "-maxrate", "16M", "-bufsize", "32M", "-preset", "fast",
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", video])
    vertical = daw.W < daw.H
    if vertical:   # 竖屏作品：发布台给竖屏平台找 video_vertical.mp4（硬链接，不占双份空间）
        try:
            os.link(video, dest / "video_vertical.mp4")
        except OSError:
            shutil.copy(video, dest / "video_vertical.mp4")
        shutil.copy(intro.with_suffix(".jpg"), dest / "cover_vertical.jpg")
    shutil.copy(intro.with_suffix(".jpg"), dest / "cover.jpg")
    shutil.copy(intro_info["sfx"], dest / "intro_sfx.wav")
    if outro_wav:
        shutil.copy(outro_wav, dest / "outro_sfx.wav")
    tags = " ".join("#" + t for t in song.get("tags", []))
    (dest / "publish.md").write_text(f"# 发布信息\n\n**标题**：{song.get('douyin_title', song['title'])}\n\n"
                                     f"**文案**：{song.get('description', '')} {tags}\n\n**封面**：cover.jpg\n",
                                     encoding="utf-8")
    (dest / "job.json").write_text(json.dumps({"kind": "tracks", "song": str(args.song.resolve()),
                                               "title": song.get("douyin_title", song["title"]),
                                               "description": song.get("description", ""),
                                               "tags": song.get("tags", []),
                                               "template": song.get("template"),
                                               "orientation": "vertical" if vertical else "horizontal"},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    emit("compose", f"成片完成：{video} ({time.time() - t0:.0f}s)", 0.97)
    try:                                           # 同时生成 OpenFilm 工程，可以在琴房的「剪辑」页里继续剪
        import openfilm_export
        openfilm_export.export(dest, mat, song, t_from, dur, (daw.W, daw.H), (fi, fo), SFX_GAIN,
                               outro_at=dur - daw.OUTRO if outro_wav else None)
    except Exception as e:                         # 剪辑工程是附带的，失败不影响成片
        print(f"OpenFilm 工程没有生成：{e}", flush=True)

    # 5. 剪映草稿
    drafts = []
    if not args.no_draft:
        emit("draft", "生成剪映草稿", 0.98)
        drafts = [d.name for d in build_drafts(slug, song, intro, main_v, music_src, t_from, intro_info["sfx"],
                                                outro_wav, fades=(fi, fo))]
        for d in drafts:
            print("剪映草稿：", d, flush=True)
    emit("done", f"全部完成 ({time.time() - t0:.0f}s)", 1.0,
         result={"video": str(video), "cover": str(dest / "cover.jpg"), "folder": str(dest), "drafts": drafts})
    return 0


if __name__ == "__main__":
    sys.exit(main())
