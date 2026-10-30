"""选片段并卡在节拍上：起点和终点都吸附到小节第一拍（重拍）。

有歌词时由 lyrics.choose_window 先按副歌选出大致范围；纯音乐（没有 LRC）用 energy_window 按响度选：
整段要饱满，开头 3 秒要够响（钩子），不能从静音开始。用法见 prepare.py。
"""
from pathlib import Path

import numpy as np
import soundfile as sf

import analyze


def downbeats(work: Path) -> np.ndarray:
    """整首的重拍时间（画面实际使用的拍子里每 4 拍一个）。"""
    grid = analyze.beat_grid(work)
    eff = analyze.effective_beats(grid, grid["beats"])
    return np.asarray(eff[analyze.downbeat_phase(work, grid, eff)::4], dtype=np.float64)


def snap(start: float, dur: float, downs: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    """起点吸附到最近的重拍；终点取时长在 [lo, hi] 内、最接近原时长的那个重拍。找不到时原样返回。"""
    if len(downs) < 2:
        return start, dur
    s = float(downs[np.argmin(np.abs(downs - start))])
    ends = downs[(downs - s >= lo) & (downs - s <= hi)]
    if not len(ends):
        return round(s, 3), dur
    e = float(ends[np.argmin(np.abs(ends - s - dur))])
    return round(s, 3), round(e - s, 3)


def loudness(work: Path, rate: int = 10) -> np.ndarray:
    """整首的响度曲线（每秒 rate 个点，RMS，平滑 1 秒，归一化到中位数）。"""
    x, sr = sf.read(work / "source.wav", dtype="float32", always_2d=True)
    hop = sr // rate
    n = len(x) // hop
    rms = np.sqrt((x[: n * hop].mean(axis=1) ** 2).reshape(n, hop).mean(axis=1))
    rms = np.convolve(rms, np.ones(rate) / rate, mode="same")
    return rms / (np.median(rms[rms > rms.max() * 0.02]) + 1e-9)


def energy_window(work: Path, target: float, lo: float, hi: float) -> tuple[float, float]:
    """纯音乐选片段：候选起点都是重拍，终点也是重拍，时长在 [lo, hi]。
    得分 = 整段平均响度 + 开头 3 秒响度（钩子）− 开头 1 秒太安静的惩罚 − 偏离目标时长的惩罚。"""
    downs = downbeats(work)
    lv = loudness(work)
    rate = 10
    total = len(lv) / rate

    def mean(a, b):
        i, j = int(a * rate), max(int(a * rate) + 1, int(b * rate))
        return float(lv[i:j].mean()) if i < len(lv) else 0.0

    best, best_score = (0.0, min(target, total)), -1e9
    for s in downs:
        for e in downs[(downs - s >= lo) & (downs - s <= hi)]:
            if e > total:
                break
            d = e - s
            first = mean(s, s + 1.0)
            score = (mean(s, e) + 0.6 * mean(s, s + 3.0) - (2.0 if first < 0.35 else 0.0)
                     - 0.05 * abs(d - target))
            if score > best_score:
                best, best_score = (round(float(s), 3), round(float(d), 3)), score
    if best_score == -1e9:              # 录音比目标还短：整段都用
        return 0.0, round(total, 3)
    return best
