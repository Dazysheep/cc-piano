"""MIDI → wav（FluidSynth + 两遍响度归一化），以及视频片段拼接 + 混入音频。"""
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def render_wav(midi: Path, wav: Path, cfg: dict) -> Path:
    a = cfg["audio"]
    raw = wav.with_name("raw.wav")
    subprocess.run(
        [str(a["fluidsynth"]), "-ni", "-q", "-g", str(a["gain"]), "-r", str(a["sample_rate"]),
         "-F", str(raw), str(a["soundfont"]), str(midi)],
        check=True, capture_output=True,
    )

    # 第一遍测量响度，第二遍按测量值线性归一化（短曲目单遍 loudnorm 不准）
    target = f"I={a['loudness']}:TP=-1.5:LRA=11"
    probe = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(raw), "-af", f"loudnorm={target}:print_format=json", "-f", "null", "-"],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", probe.stderr).group(0))
    measured = (f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
                f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", str(raw), "-af", f"loudnorm={target}:{measured}",
         "-ar", "48000", str(wav)],
        check=True,
    )
    raw.unlink()
    return wav


def concat(segments: list[Path], out: Path) -> Path:
    """无损拼接视频片段（不含音频）。"""
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments), encoding="utf-8")
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", "-movflags", "+faststart", str(out)],
        check=True,
    )
    listing.unlink()
    return out


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def compose(*, background: Path, notes: Path, keys: Path, keys_y: int, text_png: Path, piano: Path,
            bgm: Path | None, bgm_volume: float, bg_dim: float, size: tuple[int, int], fps: int,
            duration: float, cfg: dict, out: Path, intro: Path | None = None, intro_dur: float = 0) -> Path:
    """背景 + 音符(滤色) + 琴键条 + 文字 → 成片；钢琴声与背景音混音；有开头时拼在最前面。"""
    w, h = size
    inputs = (["-loop", "1", "-framerate", str(fps), "-i", str(background)]
              if background.suffix.lower() in IMAGE_EXT
              else ["-stream_loop", "-1", "-i", str(background)])
    inputs += ["-i", str(notes), "-i", str(keys), "-loop", "1", "-framerate", str(fps), "-i", str(text_png),
               "-i", str(piano)]
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]
    if intro:
        inputs += ["-i", str(intro)]
        intro_idx = 6 if bgm else 5

    d = f"{duration:.3f}"
    lead = int(cfg["timing"]["lead_in"] * 1000)
    v = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,"
         f"format=gbrp,lutrgb=r=val*{bg_dim}:g=val*{bg_dim}:b=val*{bg_dim}[bg];"
         f"[1:v]format=gbrp[nt];[bg][nt]blend=all_mode=screen:shortest=1[mix];"
         f"[mix][2:v]overlay=0:{keys_y}:shortest=1[k];[k][3:v]overlay=0:0:shortest=1,"
         f"fade=t=in:st=0:d={0.25 if intro else 0.8},fade=t=out:st={duration - 1.5:.3f}:d=1.5,"
         f"scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]")
    a = f"[4:a]adelay={lead}:all=1,apad[p]"
    if bgm:
        a += (f";[5:a]volume={bgm_volume},afade=t=in:d=2,afade=t=out:st={duration - 3:.3f}:d=3[b];"
              f"[p][b]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]")
    else:
        a += ";[p]anull[a]"
    graph = f"{v};{a}"
    if intro:   # 开头 + 正片拼接（同一次编码完成）
        graph = graph.replace("[v]", "[mv]").replace("[a]", "[ma]")
        graph += (f";[{intro_idx}:v]fps={fps},scale={w}:{h},setsar=1,format=yuv420p[iv]"
                  f";[{intro_idx}:a]aresample=48000,aformat=channel_layouts=stereo[ia]"
                  f";[ma]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{duration:.3f}[ma2]"
                  f";[mv]trim=0:{duration:.3f}[mv2]"
                  f";[iv][ia][mv2][ma2]concat=n=2:v=1:a=1[v][a]")
        d = f"{duration + intro_dur:.3f}"
    v_cfg = cfg["video"]
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", *inputs, "-filter_complex", graph,
         "-map", "[v]", "-map", "[a]", "-t", d, "-r", str(fps),
         "-c:v", "libx264", "-crf", str(v_cfg["crf"]), "-preset", v_cfg["preset"], "-pix_fmt", "yuv420p",
         "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)],
        check=True,
    )
    return out
