"""《你有多久没有抬起头认真的数过星星》MV 合成：3D（out/3d.mp4）+ 两段手绘逐帧 + 原曲片段 → out/film.mp4。

时间轴（MV 剧本 v2）：
  0–16      3D 开头（15.5 秒星光全白）
  14.5–28   手绘童年（circleopen：从画面中间铺开）
  27–74     3D 中段（fadewhite：白光里醒来）
  72.5–84.5 手绘结尾（dissolve）
每段的起点都对准剧本秒数，所以 56.5 秒「抬头」正好压在副歌上。
最后用 lemo-opuscar 的 mux.sh 做两遍 loudnorm（-14 LUFS），不再加颗粒（3D 自带）。
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tracks"))
import build  # noqa: E402

FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
FRAMES = Path(r"D:\cc-engine\.tmp\handdrawn\film")
WORK = ROOT / "output" / "tracks_你有多久没有抬起头认真的数过星星" / "work"
START, DUR = 168.705, 84.52


def run(args: list[str]) -> None:
    r = subprocess.run([str(FF), "-y", "-loglevel", "error", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])


def main() -> Path:
    out = HERE / "out"
    v3d, picture, mix, film = out / "3d.mp4", out / "picture.mp4", out / "mix.wav", out / "film.mp4"
    for name in ("film_childhood", "film_home"):
        if not (FRAMES / name / "f0000.png").exists():
            raise FileNotFoundError(f"先渲染手绘：{FRAMES / name}")
    fc = ("[0:v]trim=0:16,setpts=PTS-STARTPTS,fps=30,format=yuv420p[a];"
          "[1:v]fps=30,format=yuv420p,trim=0:13.5,setpts=PTS-STARTPTS[b];"
          "[0:v]trim=27:74,setpts=PTS-STARTPTS,fps=30,format=yuv420p[c];"
          "[2:v]fps=30,format=yuv420p,trim=0:12,setpts=PTS-STARTPTS[d];"
          "[a][b]xfade=transition=circleopen:duration=1.5:offset=14.5[ab];"
          "[ab][c]xfade=transition=fadewhite:duration=1:offset=27[abc];"
          "[abc][d]xfade=transition=dissolve:duration=1.5:offset=72.5,trim=0:84.5[v]")
    lock = build.render_lock()
    try:
        run(["-i", str(v3d), "-framerate", "15", "-i", str(FRAMES / "film_childhood" / "f%04d.png"),
             "-framerate", "15", "-i", str(FRAMES / "film_home" / "f%04d.png"),
             "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", str(picture)])
        run(["-ss", str(START), "-t", str(DUR), "-i", str(WORK / "source.wav"),
             "-af", "afade=t=in:d=0.3,afade=t=out:st=82.3:d=2.2", "-ar", "48000", "-ac", "2", str(mix)])
        r = subprocess.run(["bash", "-lc", '. /d/cc-engine/filmlab/env.sh && cd "$LIB" && sh core/render/mux.sh '
                            f'"{picture.as_posix()}" "{mix.as_posix()}" "{film.as_posix()}" 30 0'],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout[-800:], r.stderr[-800:])
        if r.returncode:
            raise RuntimeError("mux 失败")
    finally:
        lock.close()
    return film


if __name__ == "__main__":
    print(main())
