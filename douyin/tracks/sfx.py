"""拨片开头音效：用 numpy 合成（无版权问题），输出单独的 wav，方便在剪映里单独剪辑。

- 每张卡片滑过中心时一声「拨片」轻响：速度越快越亮越响，快速段连成棘轮般的哒哒声
- 跟随滑动速度的风声（速度快时偏亮、慢时变暗变弱）
- 主图落定时一声轻柔的闷响
- 可选：开头 → 音轨转场的水墨「呼」声（渐强后散开）
"""
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
_rng = np.random.default_rng(7)


def _band(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def _low(x: np.ndarray, hi: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hi, btype="low", fs=SR, output="sos"), x)


def _add(buf: np.ndarray, t: float, snd: np.ndarray) -> None:
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(snd))
    buf[i:j] += snd[: j - i]


def flick(speed: float) -> np.ndarray:
    """一声拨片：短促的带通噪声 + 一点塑料感的音高。speed 0~1。"""
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    noise = _band(_rng.standard_normal(n), 1800 + 2400 * speed, 7000 + 4000 * speed)
    tick = noise * np.exp(-t / (0.004 + 0.003 * (1 - speed)))
    tone = np.sin(2 * np.pi * (1500 + 900 * speed) * t) * np.exp(-t / 0.012) * 0.35
    return (tick + tone) * (0.5 + 0.5 * speed ** 0.6)


def thump(amp: float = 0.5) -> np.ndarray:
    """落定的闷响：低频正弦快速衰减 + 柔和的触感噪声。"""
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (95 + 60 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09)
    touch = _low(_rng.standard_normal(n), 1200) * np.exp(-t / 0.015) * 0.6
    return (body + touch) * amp


def wind(speeds: np.ndarray) -> np.ndarray:
    """跟随速度的风声：speeds 是每个采样点的速度（0~1）。高频随速度变亮，整体音量随速度变化。"""
    n = len(speeds)
    noise = _rng.standard_normal(n)
    low = _band(noise, 250, 900)
    high = _band(noise, 1500, 6000)
    return (low * (0.6 + 0.4 * speeds) + high * speeds ** 1.5) * speeds ** 1.2 * 0.5


def ink_whoosh(dur: float = 1.1) -> np.ndarray:
    """水墨转场的「呼」声：低沉的气流渐强，到中段散开，尾巴带一点空气感。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    u = t / dur
    env = np.sin(np.pi * np.clip(u / 0.85, 0, 1)) ** 1.6
    noise = _rng.standard_normal(n)
    body = _band(noise, 120, 700) * 1.4
    air = _band(noise, 2000, 9000) * np.clip((u - 0.3) / 0.4, 0, 1) * 0.35
    return (body + air) * env * 1.8


def intro_sfx(crossings: list[tuple[float, float]], speed_at, seconds: float, settle_t: float,
              tail: float = 0.0, whoosh_at: float | None = None) -> np.ndarray:
    """crossings：[(时间, 速度 0~1)] 卡片经过中心的时刻；speed_at(t)：任意时刻的速度 0~1。"""
    n = int((seconds + tail) * SR)
    buf = np.zeros(n)
    ts = np.arange(n) / SR
    sp = np.clip(np.vectorize(speed_at)(ts[::64]), 0, 1)       # 每 64 个采样算一次速度，再插值
    buf += wind(np.interp(ts, ts[::64], sp))
    for t, s in crossings:
        _add(buf, t, flick(s))
    _add(buf, settle_t, thump(0.8))
    if whoosh_at is not None:
        _add(buf, whoosh_at, ink_whoosh())
    fade = np.minimum(1, np.minimum(ts / 0.01, (n / SR - ts) / 0.05))   # 首尾去爆音
    buf *= np.clip(fade, 0, 1)
    peak = np.abs(buf).max()
    return buf / peak * 0.89 if peak > 0 else buf                      # 峰值约 -1 dBFS


def write_wav(path: Path, x: np.ndarray) -> Path:
    data = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.repeat(data[:, None], 2, axis=1).tobytes())
    return path
