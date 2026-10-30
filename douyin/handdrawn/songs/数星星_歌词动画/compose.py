"""《你有多久没有抬起头认真的数过星星》歌词动画合成：手绘逐帧（12fps JPEG）+ 整首原曲 → douyin/output/lyricfilm/<歌>/film.mp4。

逐帧由 render.mjs 渲染：node render.mjs --song=数星星_歌词动画 --scene=film --frames --fps=12 --jpg --out=<FRAMES>（可分段 --from/--to 并行）。
画面 12fps（手绘的「一拍二」节奏）转成 30fps 输出；声音是整首录屏音频（work/source.wav），最后用 lemo-opuscar 的 mux.sh 做两遍 loudnorm（-14 LUFS），
片尾 2 秒淡出。渲染和合成都拿 douyin 的渲染锁。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]                     # douyin/
sys.path.insert(0, str(ROOT / "tracks"))
import build  # noqa: E402

FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
FRAMES = Path(r"D:\cc-engine\.tmp\handdrawn\lyricfilm")
SRC = ROOT / "output" / "tracks_你有多久没有抬起头认真的数过星星" / "work" / "source.wav"
OUT = ROOT / "output" / "lyricfilm" / "你有多久没有抬起头认真的数过星星"
DUR = 268.26


def run(args: list[str]) -> None:
    r = subprocess.run([str(FF), "-y", "-loglevel", "error", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])


def main() -> Path:
    n = len(list(FRAMES.glob("f*.jpg")))
    need = round(DUR * 12)
    if n < need - 2:
        raise FileNotFoundError(f"逐帧还没渲染完：{n}/{need}")
    OUT.mkdir(parents=True, exist_ok=True)
    picture, mix, film = OUT / "picture.mp4", OUT / "mix.wav", OUT / "film.mp4"
    lock = build.render_lock()
    try:
        run(["-framerate", "12", "-i", str(FRAMES / "f%04d.jpg"), "-vf", f"fps=30,trim=0:{DUR},format=yuv420p",
             "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", str(picture)])
        run(["-t", str(DUR), "-i", str(SRC), "-af", f"afade=t=out:st={DUR - 2.2}:d=2.2", "-ar", "48000", "-ac", "2", str(mix)])
        r = subprocess.run(["bash", "-lc", '. /d/cc-engine/filmlab/env.sh && cd "$LIB" && LEMO_COLOR=bt709 sh core/render/mux.sh '
                            f'"{picture.as_posix()}" "{mix.as_posix()}" "{film.as_posix()}" 30 0'],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout[-600:], r.stderr[-600:])
        if r.returncode:
            raise RuntimeError("mux 失败")
    finally:
        lock.close()
    return film


if __name__ == "__main__":
    print(main())
