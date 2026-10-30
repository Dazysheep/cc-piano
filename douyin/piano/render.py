"""钢琴下落音符视频生成：成片 mp4（存入「待上传」）+ 剪映草稿。

用法（在 douyin/ 目录下）:
  .venv\\Scripts\\python piano\\render.py songs\\曲名.mid
  .venv\\Scripts\\python piano\\render.py songs\\曲名.mid --bgm rain.mp3 --background snow.jpg --watermark "@账号"
  .venv\\Scripts\\python piano\\render.py songs\\曲名.mid --preview 15     # 只渲染前 15 秒，不进待上传
  .venv\\Scripts\\python piano\\render.py songs\\曲名.mid --vertical       # 竖屏
  .venv\\Scripts\\python piano\\render.py songs\\*.mid                    # 批量

每首曲子可放一个同名 .yaml 写元数据，见 songs/example.yaml；命令行参数优先。
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import imageio_ffmpeg
import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import audio  # noqa: E402
import midi_notes  # noqa: E402
from frames import Renderer  # noqa: E402
from overlay import background as gradient_background, scrim_image, text_image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHUNK_SECONDS = 10
META_KEYS = ("title", "subtitle", "corner_text", "watermark", "background", "bgm", "bgm_volume", "bg_dim",
             "draft_name", "douyin_title", "description", "tags",
             "intro", "intro_cover", "intro_artist", "intro_title", "intro_avatar", "key_range")

_renderer: Renderer | None = None
_json_progress = False


def emit(stage: str, msg: str, pct: float | None = None, **extra) -> None:
    """进度输出：--json-progress 时每行一个 @@JSON，供网页解析。"""
    if _json_progress:
        print("@@" + json.dumps({"stage": stage, "msg": msg, "pct": pct, **extra}, ensure_ascii=False), flush=True)
    elif pct is not None and stage == "frames":
        print(f"\r  {msg}", end="", flush=True)
    else:
        print(f"  {msg}", flush=True)


def load_config(overrides: dict) -> dict:
    cfg = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text(encoding="utf-8"))
    for sec, key in (("audio", "fluidsynth"), ("audio", "soundfont"), ("paths", "output"), ("paths", "tmp"),
                     ("paths", "deliver")):
        cfg[sec][key] = (ROOT / cfg[sec][key]).resolve()
    import storage                       # 成片保存位置跟随软件设置（默认 D:\cc-engine\douyin\待上传）
    cfg["paths"]["deliver"] = storage.deliver_dir()
    for k, v in overrides.items():
        if v is not None:
            cfg["video"][k] = v
    return cfg


def load_meta(midi: Path, args) -> dict:
    side = midi.with_suffix(".yaml")
    meta = (yaml.safe_load(side.read_text(encoding="utf-8")) if side.exists() else None) or {}
    paths = ("background", "bgm", "intro_cover", "intro_avatar")
    for k in paths:  # yaml 里的相对路径按 yaml 所在目录解析
        if meta.get(k):
            meta[k] = str((midi.parent / meta[k]).resolve())
    for k in META_KEYS:
        v = getattr(args, k, None)
        if v not in (None, "", False):
            meta[k] = str(Path(v).resolve()) if k in paths else v
    if isinstance(meta.get("tags"), str):
        meta["tags"] = [t.strip().lstrip("#") for t in re.split(r"[,，\s]+", meta["tags"]) if t.strip()]
    meta.setdefault("title", midi.stem)
    return meta


def _init(cfg, notes, meta, duration):
    global _renderer
    os.environ["IMAGEIO_FFMPEG_EXE"] = audio.FFMPEG
    _renderer = Renderer(cfg, notes, meta, duration)


def _try_chunk(job):
    try:
        return _render_chunk(job), None
    except Exception as e:  # 多为内存紧张时 ffmpeg 启动失败，交给主进程重试
        return 0, (job, e)


def _render_chunk(job):
    """job = (起始帧, 结束帧, [(图层, 输出路径)], cfg)；图层: notes / keys"""
    first, last, outputs, cfg = job
    v = cfg["video"]
    writers = []
    for layer, path in outputs:
        size = (v["width"], _renderer.strip_box[1] if layer == "keys" else v["height"])
        w = imageio_ffmpeg.write_frames(
            str(path), size, fps=v["fps"], codec="libx264", pix_fmt_out="yuv420p", quality=None,
            output_params=["-crf", str(v["crf"]), "-preset", v["preset"], "-threads", "2"],
            macro_block_size=1, ffmpeg_log_level="error",
        )
        w.send(None)
        writers.append((w, _renderer.keys_layer if layer == "keys" else _renderer.notes_layer))
    for f in range(first, last):
        for w, draw in writers:
            w.send(draw(f / v["fps"]).tobytes())
    for w, _ in writers:
        w.close()
    return last - first


def _render_layers(n_frames, tmp, cfg, notes, meta, duration, workers, t0) -> dict[str, list[Path]]:
    fps = cfg["video"]["fps"]
    step = CHUNK_SECONDS * fps
    layers = ("notes", "keys")
    jobs = [(s, min(s + step, n_frames), [(layer, tmp / f"{layer}_{i:04d}.mp4") for layer in layers], cfg)
            for i, s in enumerate(range(0, n_frames, step))]
    done, failed = 0, []
    with Pool(workers, initializer=_init, initargs=(cfg, notes, meta, duration)) as pool:
        for n, err in pool.imap_unordered(_try_chunk, jobs):
            if err:
                failed.append(err[0])
                continue
            done += n
            emit("frames", f"画面 {done}/{n_frames} 帧 (已用 {time.time() - t0:.0f}s)", done / n_frames)
    if not _json_progress:
        print()
    if failed:
        emit("frames", f"{len(failed)} 个片段失败，正在重试")
        _init(cfg, notes, meta, duration)
        for job in failed:
            _render_chunk(job)
    return {layer: [j[2][k][1] for j in jobs] for k, layer in enumerate(layers)}


def _slug(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_")[:40] or "untitled"


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on") if v is not None else False


def render(midi: Path, cfg: dict, meta: dict, preview: float | None, workers: int, draft: bool,
           deliver_dir: Path | None = None, intro_only: bool = False) -> dict:
    t0 = time.time()
    if meta.get("key_range") in ("auto", "full"):   # 歌曲可单独指定：音域窄的曲子用 auto 放大琴键
        cfg = {**cfg, "layout": {**cfg["layout"], "key_range": meta["key_range"]}}
    notes = midi_notes.load(midi)
    lead, tail, fps = cfg["timing"]["lead_in"], cfg["timing"]["tail"], cfg["video"]["fps"]
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    song_len = float(notes["end"].max())
    duration = lead + (min(song_len, preview) if preview else song_len) + tail
    n_frames = math.ceil(duration * fps)
    duration = n_frames / fps
    emit("start", f"{midi.name}: {len(notes['pitch'])} 个音符, 时长 {duration:.1f}s, {n_frames} 帧", 0)

    work = cfg["paths"]["output"] / midi.stem
    tmp = cfg["paths"]["tmp"] / midi.stem
    # 每次渲染单独一个素材目录：剪映草稿引用这里的文件，重新渲染同一首曲子不会改掉旧草稿
    stamp = datetime.now()
    mat = work / ("preview" if preview else f"{stamp:%Y%m%d_%H%M%S}" + ("_vertical" if deliver_dir else ""))
    for d in (work, mat):
        d.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    audio.render_wav(midi, mat / "piano.wav", cfg)
    emit("audio", f"钢琴音频完成 ({time.time() - t0:.0f}s)")

    # 爆款开头：头像唱片 × 曲子封面唱片，配高潮片段
    intro_info = None
    intro_enabled = cfg["intro"].get("enabled", True)
    if intro_enabled and _truthy(meta.get("intro")) and meta.get("intro_cover"):
        import intro as intro_mod
        emit("intro", "正在生成开头")
        ic = cfg["intro"]
        intro_info = intro_mod.render_intro(
            w=w, h=h, fps=fps, cfg=cfg, notes=notes, piano_wav=mat / "piano.wav",
            avatar=Path(meta.get("intro_avatar") or (ROOT / ic["avatar"])), cover=Path(meta["intro_cover"]),
            left=ic["left_name"], right=meta.get("intro_artist", ""), title=meta.get("intro_title", ""),
            out=mat / "intro.mp4",
        )
        emit("intro", f"开头完成，高潮片段取自 {intro_info['highlight']:.0f} 秒处 ({time.time() - t0:.0f}s)")
        if intro_only:
            out = work / "intro_preview.mp4"
            shutil.copy(intro_info["path"], out)
            cover = work / "intro_preview.jpg"
            intro_info["cover_frame"].save(cover, quality=92)
            shutil.rmtree(tmp, ignore_errors=True)
            result = {"video": str(out), "cover": str(cover), "folder": str(work), "draft": None,
                      "seconds": round(time.time() - t0)}
            emit("done", f"开头预览完成 ({result['seconds']}s)", 1, result=result)
            return result
    elif intro_only:
        raise RuntimeError("开头功能已关闭（piano/config.yaml 里 intro.enabled）" if not intro_enabled
                           else "要预览开头，请先打开「加开头」并上传曲子封面")

    segs = _render_layers(n_frames, tmp, cfg, notes, meta, duration, workers, t0)
    audio.concat(segs["notes"], mat / "notes.mp4")
    audio.concat(segs["keys"], mat / "keys.mp4")

    # 背景：用户图片/视频；未指定时生成默认深色渐变
    bg = Path(meta["background"]) if meta.get("background") else None
    if bg is None:
        bg = mat / "background_default.jpg"
        Image.fromarray((gradient_background(w, h, cfg) * 255).astype("uint8")).save(bg, quality=95)
        bg_dim = 1.0
    else:
        bg_dim = float(meta.get("bg_dim", cfg["background"]["dim"]))
    meta["bg_dim"] = bg_dim
    text_png = mat / "text.png"   # 成片用：蒙版 + 文字
    text_image(w, h, meta, cfg).save(text_png)
    scrim = scrim_image(w, h, meta, cfg)   # 剪映草稿单独一条蒙版轨道（文字用剪映自带文字）
    scrim_png = mat / "scrim.png"
    if scrim is not None:
        scrim.save(scrim_png)
    elif scrim_png.exists():
        scrim_png.unlink()

    suffix = ""
    if deliver_dir:   # 给已有成片补一个竖屏版，放进同一个文件夹
        dest, suffix = deliver_dir, "_vertical"
        video = dest / "video_vertical.mp4"
    elif preview:
        dest = work
        video = work / "preview.mp4"
    else:
        dest = cfg["paths"]["deliver"] / f"{stamp:%Y%m%d_%H%M}_{_slug(meta['title'])}"
        dest.mkdir(parents=True, exist_ok=True)
        video = dest / "video.mp4"

    emit("compose", "正在合成成片")
    bgm = Path(meta["bgm"]) if meta.get("bgm") else None
    renderer = Renderer(cfg, notes, meta, duration)
    audio.compose(
        background=bg, notes=mat / "notes.mp4", keys=mat / "keys.mp4", keys_y=renderer.strip_box[0],
        text_png=text_png, piano=mat / "piano.wav", bgm=bgm,
        bgm_volume=float(meta.get("bgm_volume", cfg["jianying"]["bgm_volume"])), bg_dim=bg_dim,
        size=(w, h), fps=fps, duration=duration, cfg=cfg, out=video,
        intro=intro_info["path"] if intro_info else None, intro_dur=intro_info["duration"] if intro_info else 0,
    )
    cover = dest / f"cover{suffix}.jpg"
    if intro_info:   # 有开头时用开头画面做封面（两张唱片 + 联动字样，更吸引点击）
        intro_info["cover_frame"].save(cover, quality=92)
    else:
        subprocess_frame(video, lead + min(song_len / 3, duration - lead - tail), cover)
    emit("compose", f"成片完成 ({time.time() - t0:.0f}s)")

    draft_path = None
    if draft and not deliver_dir:
        import jianying as jy  # 仅生成草稿时需要 pyJianYingDraft
        meta.setdefault("background", str(bg))
        # 默认草稿名带时间，同一首曲子多次生成不会互相覆盖
        name = meta.get("draft_name") or f"{meta['title']}_{datetime.now():%m%d_%H%M}"
        draft_path = jy.build_draft(name=_slug(name), mat_dir=mat, renderer=renderer, meta=meta, cfg=cfg,
                                    duration=duration, intro=intro_info["path"] if intro_info else None)
        emit("draft", f"剪映草稿已生成: {draft_path.name}")

    if not deliver_dir:
        write_publish(dest, meta)
        if not preview:   # 记下生成参数，发布时据此补渲染竖屏版
            job = {k: meta[k] for k in META_KEYS if meta.get(k) not in (None, "")}
            job.update(midi=str(midi), vertical=cfg["video"]["height"] > cfg["video"]["width"],
                       fps=cfg["video"]["fps"])
            (dest / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    result = {"video": str(video), "cover": str(cover), "folder": str(dest),
              "draft": str(draft_path) if draft_path else None, "seconds": round(time.time() - t0)}
    emit("done", f"完成 (总耗时 {result['seconds']}s)", 1, result=result)
    return result


def subprocess_frame(video: Path, t: float, out: Path) -> None:
    subprocess.run([audio.FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video),
                    "-frames:v", "1", "-q:v", "2", str(out)], check=True)


def write_publish(out_dir: Path, meta: dict) -> None:
    tags = meta.get("tags") or ["钢琴", "纯音乐", "钢琴曲", "治愈"]
    title = meta.get("douyin_title") or meta["title"]
    desc = meta.get("description", "")
    (out_dir / "publish.md").write_text(
        f"# 发布信息\n\n**标题**：{title}\n\n**文案**：{desc} {' '.join('#' + t for t in tags)}\n\n"
        f"**封面**：cover.jpg\n",
        encoding="utf-8",
    )


def main() -> int:
    global _json_progress
    ap = argparse.ArgumentParser(description="钢琴下落音符视频生成")
    ap.add_argument("midi", nargs="*", help="MIDI 文件，支持通配符")
    ap.add_argument("--job", help=argparse.SUPPRESS)  # 网页任务：参数放在 JSON 文件里，避免命令行转义问题
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--corner-text", dest="corner_text")
    ap.add_argument("--watermark", help="右下角水印，例如 @账号")
    ap.add_argument("--background", help="背景图片或视频")
    ap.add_argument("--bg-dim", dest="bg_dim", type=float, help="背景亮度 0-1，默认 0.45")
    ap.add_argument("--bgm", help="背景音(雨声、白噪音等)，循环铺满")
    ap.add_argument("--bgm-volume", dest="bgm_volume", type=float, help="背景音音量 0-1")
    ap.add_argument("--draft-name", dest="draft_name", help="剪映草稿名")
    ap.add_argument("--douyin-title", dest="douyin_title", help="发布标题(写入 publish.md)")
    ap.add_argument("--description", help="发布文案")
    ap.add_argument("--tags", help="话题，逗号或空格分隔")
    ap.add_argument("--no-draft", action="store_true", help="不生成剪映草稿")
    ap.add_argument("--intro", action="store_true", help="加爆款开头（需要 --intro-cover）")
    ap.add_argument("--intro-cover", dest="intro_cover", help="开头右侧(竖屏为下方)唱片：曲子封面")
    ap.add_argument("--intro-artist", dest="intro_artist", help="联动对象名，如 TRA$H")
    ap.add_argument("--intro-title", dest="intro_title", help="开头显示的曲名")
    ap.add_argument("--intro-only", dest="intro_only", action="store_true", help="只渲染开头预览")
    ap.add_argument("--preview", type=float, help="只渲染前 N 秒（不进待上传）")
    ap.add_argument("--vertical", action="store_true", help="竖屏 1080x1920，自动裁剪音域")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--json-progress", action="store_true", help=argparse.SUPPRESS)
    # 每个进程(含两路 x264 编码)约占 500-600MB 内存，空闲内存不足时调小
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="并行进程数")
    args = ap.parse_args()
    if args.job:
        job = json.loads(Path(args.job).read_text(encoding="utf-8"))
        args.midi = [job.pop("midi")]
        args.vertical = bool(job.pop("vertical", False))
        preview = job.pop("preview", None)
        args.preview = float(preview) if preview else None
        args.no_draft = bool(args.preview) or bool(job.pop("no_draft", False))
        args.fps = int(job.pop("fps")) if job.get("fps") else None
        deliver_dir = job.pop("deliver_dir", None)
        args.deliver_dir = Path(deliver_dir) if deliver_dir else None
        args.intro_only = bool(job.pop("intro_only", False))
        if args.intro_only:
            args.no_draft = True
        for k, v in job.items():
            if k in META_KEYS and v not in (None, ""):
                if isinstance(v, list):
                    v = " ".join(map(str, v))
                setattr(args, k, float(v) if k in ("bg_dim", "bgm_volume") else str(v))
    if not args.midi:
        ap.error("需要指定 MIDI 文件")
    _json_progress = args.json_progress

    cfg = load_config({"fps": args.fps, "width": args.width, "height": args.height})
    if args.vertical:
        cfg["video"].update(width=args.width or 1080, height=args.height or 1920)
        cfg["layout"].update(key_range="auto", keyboard_bottom=0.82)
    files = [Path(p) for pat in args.midi for p in (glob.glob(pat) or [pat])]
    failed = 0
    for f in files:
        try:
            render(f.resolve(), cfg, load_meta(f.resolve(), args), args.preview, args.workers, not args.no_draft,
                   deliver_dir=getattr(args, "deliver_dir", None), intro_only=args.intro_only)
        except Exception as e:
            failed += 1
            emit("error", f"失败 {f.name}: {e}")
            if len(files) == 1:
                raise
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
