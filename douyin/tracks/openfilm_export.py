"""成片 → OpenFilm 工程（film.html），在琴房的「剪辑」页（OpenFilm Studio）里继续剪。

工程放在成片文件夹里的 film/：film.html + assets/（素材是 output/tracks_<歌>/<时间>/ 里文件的硬链接，不占双份空间）。
轨道从上到下：评论层（comments.webm，透明背景，有评论故事时才有）、开头（intro.mp4）、
正片（main.mp4，紧接开头；有评论层时用不带评论的 main_clean.mp4）、音乐（截取范围 + 淡入淡出）、音效（拨片声、结尾呼声）。
格式见 douyin/editor/node_modules/openfilm/SPEC.md。
"""
import html
import json
import os
import shutil
from pathlib import Path


def _link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy(src, dst)


def _gain_to(path: Path, start: float, dur: float, target: float, ffmpeg: str) -> float:
    """这段音频调到 target LUFS 需要的线性音量（量不出来时返回 1）。"""
    import re
    import subprocess
    r = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                        "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", r.stderr)
    if not m:
        return 1.0
    return round(min(1.5, 10 ** ((target - float(m[-1])) / 20)), 3)


def _clip(tag: str, cid: str, src: str, at: float = 0.0, t: tuple[float, float] | None = None, volume: float = 1.0,
          fade: tuple[float, float] | None = None) -> str:
    frag = f"#t={t[0]:.3f},{t[1]:.3f}" if t else ""
    attrs = [f'id="{cid}"', f'src="{html.escape(src)}{frag}"']
    if at:
        attrs.append(f'at="{at:.3f}"')
    if volume != 1.0:
        attrs.append(f'volume="{volume:.3f}"')
    if fade:
        attrs.append("overrides='" + json.dumps([{"fade": [round(fade[0], 3), round(fade[1], 3)]}]) + "'")
    return f"  <{tag} {' '.join(attrs)}></{tag}>"


def export(dest: Path, mat: Path, song: dict, t_from: float, duration: float, size: tuple[int, int],
           fades: tuple[float, float], sfx_gain: float, outro_at: float | None = None) -> Path:
    """dest：成片文件夹；mat：这次渲染的素材文件夹（intro.mp4、main.mp4、音乐、音效）。返回 film.html 路径。"""
    film = dest / "film"
    assets = film / "assets"
    music = next((p for p in mat.glob("music.*")), None)
    layered = (mat / "comments.webm").exists() and (mat / "main_clean.mp4").exists()
    files = {"intro.mp4": mat / "intro.mp4", "main.mp4": mat / ("main_clean.mp4" if layered else "main.mp4")}
    if layered:
        files["comments.webm"] = mat / "comments.webm"
    if music:
        files[music.name] = music
    sfx = mat / "intro_sfx.wav"
    if sfx.exists():
        files["intro_sfx.wav"] = sfx
    outro = mat / "outro_sfx.wav"
    if outro.exists() and outro_at is not None:
        files["outro_sfx.wav"] = outro
    for name, src in files.items():
        _link(src, assets / name)
    w, h = size
    import imageio_ffmpeg                         # 片段的结束点不能超过文件实际长度（帧数取整后会短几毫秒）
    frames, secs = imageio_ffmpeg.count_frames_and_secs(str(assets / "main.mp4"))
    main_len = min(duration - t_from, secs) - 0.001
    start = float(song["start"])
    tracks = [[_clip("video", "comments", "assets/comments.webm", at=t_from, t=(0.0, main_len))]] if layered else []
    tracks += [
        [_clip("video", "intro", "assets/intro.mp4")],
        [_clip("video", "main", "assets/main.mp4", at=t_from, t=(0.0, main_len))],
    ]
    if music:   # 成片里音乐做过 -14 LUFS 响度统一；这里量一下这一段的响度，用音量把剪辑器里的声音调到一样
        vol = _gain_to(assets / music.name, start, duration, -14.0, imageio_ffmpeg.get_ffmpeg_exe())
        tracks.append([_clip("audio", "music", f"assets/{music.name}", t=(start, start + duration), volume=vol,
                             fade=fades)])
    sounds = []
    if "intro_sfx.wav" in files:
        sounds.append(_clip("audio", "sfx_intro", "assets/intro_sfx.wav", volume=sfx_gain))
    if "outro_sfx.wav" in files:
        sounds.append(_clip("audio", "sfx_outro", "assets/outro_sfx.wav", at=outro_at, volume=sfx_gain))
    if sounds:
        tracks.append(sounds)
    body = "\n".join("<section>\n" + "\n".join(t) + "\n</section>" for t in tracks)
    doc = (f'<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n'
           f'<meta name="viewport" content="width={w}, height={h}">\n'
           f'<title>{html.escape(song["title"])}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n')
    (film / "film.html").write_text(doc, encoding="utf-8")
    return film / "film.html"
