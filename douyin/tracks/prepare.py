"""音轨剪辑的准备工作：整首音频 → 6 轨分离 → 歌词识别校对 → 选片段 → 分析数据。

用法: python tracks/prepare.py tracks/songs/<歌>.json [--work 目录]
歌曲 json 需要 audio（整首音频）；可选 lrc（有就做 AI 歌词 + 校对 + 副歌定位）或 lyrics_text（贴的纯文本歌词）。
start 写 "auto" 时自动选片段（副歌最多、开头 5 秒内进副歌、不在句子中间截断），duration 是目标长度。
每一步的结果都缓存在工作目录里，重跑会跳过已完成的步骤；换了音频会整个重做。之后运行 build.py 出成片
（build.py --prepare 会先自动跑这一步）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
STEMS = ("vocals", "piano", "guitar", "bass", "other", "drums")


def work_dir(song: dict) -> Path:
    return ROOT / "output" / f"tracks_{song['title'].replace(' ', '_')}" / "work"


def py_cmd(*args) -> list[str]:
    """运行项目里的 Python 模块/脚本；打包成 exe 后由 exe 自己代为执行（见 app/launcher.py）。"""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--py", *map(str, args)]
    return [sys.executable, *map(str, args)]


def separate(work: Path) -> None:
    """Demucs htdemucs_6s 分离（CPU 上一首 5 分钟的歌大约 10 分钟）。"""
    if all((work / "stems" / f"{k}.wav").exists() for k in STEMS):
        return
    env = dict(os.environ, TORCH_HOME=str(ROOT / "tools" / "models"), HF_HOME=str(ROOT / "tools" / "models" / "hf"))
    tmp = work / "_demucs"
    subprocess.run(py_cmd("-m", "demucs.separate", "-n", "htdemucs_6s", "-o", tmp, work / "source.wav"),
                   check=True, env=env)
    (work / "stems").mkdir(exist_ok=True)
    for k in STEMS:
        shutil.move(str(tmp / "htdemucs_6s" / "source" / f"{k}.wav"), work / "stems" / f"{k}.wav")
    shutil.rmtree(tmp, ignore_errors=True)


def run(song_path: Path, work: Path | None = None, model: str = "medium", emit=None) -> Path:
    """准备好工作目录并返回。emit(stage, msg, pct)：可选的进度回调（pct 0~1，只覆盖准备阶段）。"""
    emit = emit or (lambda stage, msg, pct=None: print(msg, flush=True))
    import template_lib
    song = template_lib.load_song(song_path)
    work = work or work_dir(song)
    work.mkdir(parents=True, exist_ok=True)
    src, mark = work / "source.wav", work / "audio_src.txt"
    if src.exists() and mark.exists() and mark.read_text(encoding="utf-8") != str(song["audio"]):
        shutil.rmtree(work)                   # 换了音频：之前的分离、识别、分析都作废
        work.mkdir(parents=True)
    if not src.exists():
        emit("prepare", "读取音频", 0.0)
        # -vn：iPhone 录屏（mp4/mov）只取声音
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", song["audio"], "-vn", "-ac", "2", "-ar", "44100",
                        src], check=True)
        mark.write_text(str(song["audio"]), encoding="utf-8")
    emit("separate", "分离音轨（第一次约 10 分钟）", 0.02)
    separate(work)

    resolved = {"title": song["title"], "artist": song.get("artist", ""), "start": song.get("start", 0.0),
                "duration": song.get("duration", 100.0)}
    target = float(song.get("duration", 100))
    lo, hi = target - 5, target + 6           # 目标 100 秒时就是原来的 95~106 秒
    if song.get("lrc") or song.get("lyrics_text"):
        import lyrics
        if song.get("lrc"):
            emit("lyrics", "AI 识别歌词并用 LRC 校对", 0.7)
            ly = lyrics.run(work, Path(song["lrc"]), model)
        else:                                 # 贴的纯文本歌词（原文 / 翻译交替），文件名相对 tracks/songs/
            txt = Path(song["lyrics_text"])
            txt = txt if txt.is_absolute() else Path(__file__).resolve().parent / "songs" / txt
            emit("lyrics", "AI 识别歌词并和贴的歌词对齐", 0.7)
            ly = lyrics.run_text(work, txt, model)
        if resolved["start"] == "auto":
            s, d = lyrics.choose_window(ly["lines"], ly["chorus"],
                                        intro=0.0 if song.get("cold_open") else song.get("intro", 4.0),
                                        min_len=lo, max_len=hi, target=target,
                                        cold_open=bool(song.get("cold_open")))
            if song.get("snap_beats"):
                import clip
                s, d = clip.snap(s, d, clip.downbeats(work), lo, hi)
            resolved["start"], resolved["duration"] = s, d
    if resolved["start"] == "auto":
        if song.get("snap_beats"):           # 纯音乐：按响度选最饱满、开头够响的一段，起止都在重拍上
            import clip
            emit("prepare", "按节拍和响度选片段", 0.8)
            resolved["start"], resolved["duration"] = clip.energy_window(work, target, lo, hi)
        else:                                # 没有歌词：用默认片段
            resolved["start"] = 30.0
    prev = json.loads((work / "song.json").read_text(encoding="utf-8")) if (work / "song.json").exists() else None
    (work / "song.json").write_text(json.dumps(resolved, ensure_ascii=False), encoding="utf-8")
    emit("prepare", f"片段：{resolved['start']:.2f}s 起，{resolved['duration']:.2f}s", 0.84)
    if prev != resolved or not (work / "analysis.json").exists():
        import analyze
        emit("analyze", "分析节拍、波形和钢琴音符", 0.85)
        analyze.main(work)
    emit("prepare", "准备完成", 1.0)
    return work


def main() -> int:
    ap = argparse.ArgumentParser(description="音轨剪辑准备")
    ap.add_argument("song", type=Path)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--model", default="medium", help="Whisper 模型（tools/models/hf）")
    a = ap.parse_args()
    print("准备完成：", run(a.song, a.work, a.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
