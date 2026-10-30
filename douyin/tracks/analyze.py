"""音轨剪辑：分析一首歌（已分离的各轨），生成画面需要的数据。

输出 analysis.json：截取范围、节拍、每轨的片段(clip)、钢琴音符；以及每轨的波形包络 .npy。
用法: python tracks/analyze.py <工作目录>   （目录里要有 source.wav 和 stems/*.wav，以及 song.json）
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
ENV_RATE = 200   # 波形包络：每秒 200 个点

# 轨道顺序（从上到下）与显示名；mix 为原曲混音
TRACKS = [
    ("mix", "原曲", "One More Light.mp3"),
    ("vocals", "人声", "Vocals.wav"),
    ("piano", "钢琴", "Piano · MIDI"),
    ("guitar", "吉他", "Guitar.wav"),
    ("bass", "贝斯", "Bass.wav"),
    ("other", "其他", "Synth & FX.wav"),
]


def envelope(x: np.ndarray, sr: int) -> np.ndarray:
    """每个包络点取这一小段的最大绝对值（保留立体声两个声道）。"""
    hop = sr // ENV_RATE
    n = len(x) // hop
    return np.abs(x[: n * hop]).reshape(n, hop, -1).max(axis=1)   # (n, channels)


def clips(env: np.ndarray, thr: float, min_gap: float = 1.2, min_len: float = 0.8) -> list[list[float]]:
    """按能量把一条轨道切成若干个片段（静音处断开），返回 [开始秒, 结束秒]。"""
    win = int(ENV_RATE * 0.3)
    level = np.convolve(env.max(axis=1), np.ones(win) / win, mode="same")
    on = level > thr
    segs, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        elif not v and start is not None:
            segs.append([start, i])
            start = None
    if start is not None:
        segs.append([start, len(on)])
    merged = []
    for s, e in segs:
        if merged and (s - merged[-1][1]) / ENV_RATE < min_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [[round(s / ENV_RATE, 3), round(e / ENV_RATE, 3)] for s, e in merged if (e - s) / ENV_RATE >= min_len]


ONSET_HOP = 512


def beat_grid(work: Path) -> dict:
    """整首的节拍（缓存在 beats.json + onset.npy）：tempo、每拍时间（整首时间，未做半速处理）。
    算法与原来的 librosa.beat.beat_track(y=…) 完全相同，旧歌出片的节拍网格不变。"""
    cache = work / "beats.json"
    if cache.exists() and (work / "onset.npy").exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    import librosa
    mono, sr = sf.read(work / "source.wav", dtype="float32")
    y = librosa.to_mono(mono.T)
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=ONSET_HOP, aggregate=np.median)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=ONSET_HOP, units="time")
    np.save(work / "onset.npy", onset.astype(np.float32))
    grid = {"tempo": round(float(np.atleast_1d(tempo)[0]), 1), "beats": [round(float(b), 3) for b in beats],
            "sr": sr}
    cache.write_text(json.dumps(grid), encoding="utf-8")
    return grid


def effective_beats(grid: dict, beats: list[float]) -> list[float]:
    """画面实际使用的拍子：tempo 超过 140 时隔一拍取一拍（与 daw.DawView 相同）。"""
    return beats[::2] if grid["tempo"] > 140 else beats


def downbeat_phase(work: Path, grid: dict, beats: list[float]) -> int:
    """beats 里第几拍（0~3）是小节第一拍：取起音强度平均最强的相位。"""
    if len(beats) < 8:
        return 0
    onset = np.load(work / "onset.npy")
    fr = np.minimum((np.asarray(beats) * grid["sr"] / ONSET_HOP).astype(int), len(onset) - 1)
    s = onset[fr]
    return int(np.argmax([s[k::4].mean() for k in range(4)]))


def main(work: Path) -> None:
    song = json.loads((work / "song.json").read_text(encoding="utf-8-sig"))   # 兼容带 BOM 的手写文件
    t0, t1 = song["start"], song["start"] + song["duration"]
    out = {"song": song, "env_rate": ENV_RATE, "tracks": []}

    # 节拍（整首算，再截取）；downbeat 是画面实际使用的拍子里第几拍是重拍
    grid = beat_grid(work)
    win = [b for b in grid["beats"] if t0 <= b <= t1]
    out["tempo"] = grid["tempo"]
    out["beats"] = [round(b - t0, 3) for b in win]
    out["downbeat"] = downbeat_phase(work, grid, effective_beats(grid, win))
    sr = sf.info(str(work / "source.wav")).samplerate

    a, b = int(t0 * sr), int(t1 * sr)
    for key, zh, label in TRACKS:
        if key == "mix":
            label = f"{song.get('title', 'Mix')}.mp3"
        path = work / "source.wav" if key == "mix" else work / "stems" / f"{key}.wav"
        x, _ = sf.read(path, dtype="float32", always_2d=True)
        seg = x[a:b]
        env = envelope(seg, sr)
        peak = float(np.percentile(env, 99.5)) or 1.0
        np.save(work / f"env_{key}.npy", np.clip(env / peak, 0, 1.2).astype(np.float16))
        thr = 0.0 if key == "mix" else 0.06 * peak
        cl = [[0.0, round(len(seg) / sr, 3)]] if key == "mix" else clips(env, thr)
        out["tracks"].append({"key": key, "name": zh, "label": label, "clips": cl,
                              "rms": float(np.sqrt((seg ** 2).mean()))})

    # 钢琴：把这段钢琴轨转写成音符，画成 MIDI 片段
    piano_seg = work / "piano_seg.wav"
    piano, _ = sf.read(work / "stems" / "piano.wav", dtype="float32", always_2d=True)
    sf.write(piano_seg, piano[a:b], sr)
    midi = work / "piano_seg.mid"
    subprocess.run([sys.executable, str(ROOT / "piano" / "transcribe.py"), str(piano_seg), "--out", str(midi),
                    "--no-split"], check=True, capture_output=True)
    sys.path.insert(0, str(ROOT / "piano"))
    import midi_notes
    try:
        n = midi_notes.load(midi)
        out["piano_notes"] = [[int(p), round(float(s), 3), round(float(e), 3)]
                              for p, s, e in zip(n["pitch"], n["start"], n["end"])]
    except ValueError:
        out["piano_notes"] = []
    (work / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"tempo {out['tempo']}  beats {len(out['beats'])}  downbeat {out['downbeat']}  "
          f"piano notes {len(out['piano_notes'])}")
    for t in out["tracks"]:
        print(f"  {t['name']:3s} clips {len(t['clips']):3d}  rms {t['rms']:.4f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
