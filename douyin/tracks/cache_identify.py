"""认出剪映缓存里的歌：Whisper 听中间一段 → 拿听到的歌词去本机 LRC 歌词文件里比对 → 对上了就用 LRC 的文件名当歌名。

剪映缓存的 mp3 没有歌名标签，本地也不存歌名，只能这样认。网易云下载的 LRC 文件名就是「歌手 - 歌名」。
用法: python tracks/cache_identify.py <音频>   → 输出一行 JSON：{"lyric": 听到的歌词, "name": 歌名或空, "score": 匹配度}
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lyrics  # noqa: E402

LRC_DIRS = [Path("D:/CloudMusic"), Path.home() / "Music", HERE.parent / "uploads"]
CLIP = 40.0      # 听多少秒


def load_clip(path: Path) -> np.ndarray:
    """从 25% 处取 CLIP 秒，16kHz 单声道。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    info = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    start = max(0.0, min(dur * 0.25, dur - CLIP))
    raw = subprocess.run([ff, "-v", "error", "-ss", f"{start:.2f}", "-t", str(CLIP), "-i", str(path),
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).copy()
    return x / max(float(np.abs(x).max()), 1e-6) * 0.9


def tokens(text: str) -> set[str]:
    """英文按单词，中文按相邻两个字。"""
    out = {w for w in (lyrics._norm(t) for t in text.split()) if len(w) > 1}
    cjk = re.sub(r"[^\u4e00-\u9fff]", "", text)
    out |= {cjk[i:i + 2] for i in range(len(cjk) - 1)}
    return out


def best_lrc(heard: str) -> tuple[str, float]:
    want = tokens(heard)
    if not want:
        return "", 0.0
    best, score = "", 0.0
    for d in LRC_DIRS:
        if not d.is_dir():
            continue
        for f in d.rglob("*.lrc"):
            try:
                text = " ".join(x["text"] for x in lyrics.parse_lrc(f))
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            s = len(want & tokens(text)) / len(want)
            if s > score:
                best, score = f.stem, s
    return (best, score) if score >= 0.35 else ("", score)


def main() -> int:
    path = Path(sys.argv[1])
    os.environ.setdefault("HF_HOME", str(lyrics.MODELS / "hf"))
    from faster_whisper import WhisperModel
    local = lyrics.MODELS / "whisper-medium"
    m = WhisperModel(str(local) if (local / "model.bin").exists() else "medium", device="cpu", compute_type="int8",
                     cpu_threads=os.cpu_count() or 4)
    segs, _ = m.transcribe(load_clip(path), vad_filter=False, condition_on_previous_text=False, beam_size=3)
    heard = " ".join(s.text.strip() for s in segs).strip()
    name, score = best_lrc(heard)
    print(json.dumps({"lyric": heard[:160], "name": name, "score": round(score, 2)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
