"""手绘歌词动画「出整片」（任何一首都能用，分段修改页的「出整片」调它）：
重新逐帧渲染整片 → 配原声合成（-14 LUFS，标准 bt709）→ 拷回作品文件夹的 video.mp4 / cover.jpg → 分层素材 + OpenFilm 剪辑工程。

  python handdrawn/film_build.py <歌曲文件夹> <作品文件夹> [--no-layers] [--json-progress]

歌曲文件夹 = handdrawn/songs/<名>（scenes.js / film.js / film_data.js），作品文件夹 = 待上传/<…>（job.json 的 song 指向歌曲 json，
原声取 output/tracks_<标题>/work/source.wav，分层用同一目录的 stems）。逐帧在 .tmp/handdrawn/film/<歌>/，每次出整片前清空。
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tracks"))
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import layers  # noqa: E402

FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
FRAMES = Path(r"D:\cc-engine\.tmp\handdrawn\film")
ENV_SH = Path(r"D:\cc-engine\filmlab\env.sh").as_posix()
JSON_PROGRESS = False


def emit(stage: str, msg: str, pct: float | None = None, **extra) -> None:
    if JSON_PROGRESS:
        print("@@" + json.dumps({"stage": stage, "msg": msg, "pct": pct, **extra}, ensure_ascii=False), flush=True)
    else:
        print(msg, flush=True)


def work_dir_of(work_folder: Path) -> Path:
    """作品文件夹 job.json 里的歌曲 → output/tracks_<标题>/work（原声 source.wav、分轨 stems）。"""
    job = json.loads((work_folder / "job.json").read_text(encoding="utf-8"))
    sp = Path(job["song"])
    sp = sp if sp.is_absolute() else ROOT.parent / sp if str(sp).startswith("douyin") else ROOT / sp
    song = json.loads(sp.read_text(encoding="utf-8-sig"))
    return ROOT / "output" / f"tracks_{song['title'].replace(' ', '_')}" / "work"


STALL = 180          # 一段渲染这么多秒没出新帧（无头 Edge 崩了、node 还在等）：杀掉重来，已有的帧会跳过


def _kill(p: subprocess.Popen) -> None:
    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


def render_frames(song: str, dur: float, out: Path, parallel: int = 4, resume: bool = False) -> None:
    """整片逐帧（12fps JPEG），切成几段并行；某一段卡住就重启那一段（最多 3 次）。resume：不清空，接着渲染缺的帧。"""
    if out.exists() and not resume:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    n = round(dur * 12)
    cuts = [round(dur * k / parallel, 2) for k in range(parallel)] + [dur + .1]

    def start(a, b):
        cmd = (f'. "{ENV_SH}" && cd "{HERE.as_posix()}" && node render.mjs --song="{song}" --scene=film --frames --fps=12 --jpg '
               f'--from={a} --to={b} --out="{out.as_posix()}"')
        return subprocess.Popen(["bash", "-lc", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def have(a, b):
        return sum(1 for i in range(int(a * 12), min(n, int(b * 12 + .999))) if (out / f"f{i:04d}.jpg").exists())
    chunks = [{"a": a, "b": b, "p": start(a, b), "seen": -1, "t": time.time(), "tries": 0} for a, b in zip(cuts, cuts[1:])]
    while any(c["p"].poll() is None for c in chunks):
        time.sleep(5)
        for c in chunks:
            k = have(c["a"], c["b"])
            if k != c["seen"]:
                c["seen"], c["t"] = k, time.time()
            elif c["p"].poll() is None and time.time() - c["t"] > STALL and c["tries"] < 3:
                _kill(c["p"])
                c["p"], c["t"], c["tries"] = start(c["a"], c["b"]), time.time(), c["tries"] + 1
            elif c["p"].poll() is not None and k < int((c["b"] - c["a"]) * 12) - 2 and c["tries"] < 3:   # 退出了但没渲染完：重跑
                c["p"], c["t"], c["tries"] = start(c["a"], c["b"]), time.time(), c["tries"] + 1
        emit("frames", "逐帧渲染整片", round(.6 * len(list(out.glob("f*.jpg"))) / n, 3))
    if len(list(out.glob("f*.jpg"))) < n - 2:
        raise RuntimeError(f"逐帧没渲染完：{len(list(out.glob('f*.jpg')))}/{n}")


def compose(frames: Path, source: Path, dur: float, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    picture, mix, film = out_dir / "picture.mp4", out_dir / "mix.wav", out_dir / "film.mp4"

    def ff(args):
        r = subprocess.run([str(FF), "-y", "-loglevel", "error", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            raise RuntimeError(r.stderr[-800:])
    ff(["-framerate", "12", "-i", str(frames / "f%04d.jpg"), "-vf", f"fps=30,trim=0:{dur},format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", str(picture)])
    fade = min(2.0, max(.6, dur * .025))
    ff(["-t", str(dur), "-i", str(source), "-af", f"afade=t=out:st={dur - fade:.2f}:d={fade:.2f}", "-ar", "48000", "-ac", "2", str(mix)])
    r = subprocess.run(["bash", "-lc", f'. "{ENV_SH}" && cd "$LIB" && LEMO_COLOR=bt709 sh core/render/mux.sh '
                        f'"{picture.as_posix()}" "{mix.as_posix()}" "{film.as_posix()}" 30 0'],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode or not film.exists():
        raise RuntimeError("合成失败：" + (r.stderr or r.stdout)[-400:])
    return film


def main(song: str, work_folder: Path, with_layers: bool = True, resume: bool = False) -> dict:
    d = layers.film_data(song)
    dur = d["dur"]
    work = work_dir_of(work_folder)
    source = work / "source.wav"
    if not source.exists():
        raise FileNotFoundError(f"找不到原声：{source}")
    frames = FRAMES / song
    lock = build.render_lock()
    try:
        emit("frames", "逐帧渲染整片", 0.0)
        render_frames(song, dur, frames, resume=resume)
        emit("compose", "配原声合成", .62)
        film = compose(frames, source, dur, ROOT / "output" / "lyricfilm" / song)
    finally:
        lock.close()
    shutil.copy2(film, work_folder / "video.mp4")
    subprocess.run([str(FF), "-y", "-loglevel", "error", "-ss", f"{max(0.0, dur - 2):.2f}", "-i", str(film), "-frames:v", "1", "-q:v", "2",
                    str(work_folder / "cover.jpg")], check=False)
    (work_folder / "video_publish.mp4").unlink(missing_ok=True)       # 旧的发布用转码副本作废（发布时会按新片重转）
    res = {"folder": str(work_folder), "video": str(work_folder / "video.mp4")}
    if with_layers:
        emit("layers", "分层渲染（剪辑工程用）", .66)
        shutil.rmtree(layers.TMP / song, ignore_errors=True)            # 分层逐帧也清空（render 会跳过已有的帧）
        layers.render(song)
        emit("layers", "抠像、编码、写剪辑工程", .92)
        title = json.loads((work_folder / "job.json").read_text(encoding="utf-8")).get("title") or work_folder.name
        res["project"] = str(layers.build_project(song, work_folder, title, work))
    emit("done", "整片和剪辑工程都好了", 1.0, result=res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("song")
    ap.add_argument("work_folder")
    ap.add_argument("--no-layers", action="store_true")
    ap.add_argument("--resume", action="store_true", help="接着上次没渲染完的逐帧继续（不清空）")
    ap.add_argument("--json-progress", action="store_true")
    a = ap.parse_args()
    JSON_PROGRESS = a.json_progress
    try:
        main(a.song, Path(a.work_folder), not a.no_layers, a.resume)
    except Exception as e:
        emit("error", str(e))
        sys.exit(1)
