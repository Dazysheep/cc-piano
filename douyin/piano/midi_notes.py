"""MIDI → 音符数组（秒为单位，含左右手标记）。"""
from bisect import bisect_right

import mido
import numpy as np

SPLIT_PITCH = 60  # 单轨 MIDI 按中央 C 分左右手


def _tempo_map(mid: mido.MidiFile):
    changes = {0: 500000}
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                changes[tick] = msg.tempo
    ticks = sorted(changes)
    secs, sec = [], 0.0
    for i, t in enumerate(ticks):
        if i:
            sec += (t - ticks[i - 1]) * changes[ticks[i - 1]] / 1e6 / mid.ticks_per_beat
        secs.append(sec)
    tempos = [changes[t] for t in ticks]

    def to_sec(tick: int) -> float:
        i = bisect_right(ticks, tick) - 1
        return secs[i] + (tick - ticks[i]) * tempos[i] / 1e6 / mid.ticks_per_beat

    return to_sec


def load(path) -> dict:
    mid = mido.MidiFile(path)
    to_sec = _tempo_map(mid)
    per_track = []
    for track in mid.tracks:
        tick, opened, notes = 0, {}, []
        for msg in track:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                opened.setdefault((msg.channel, msg.note), []).append((tick, msg.velocity))
            elif msg.type in ("note_off", "note_on") and (msg.channel, msg.note) in opened:
                stack = opened[(msg.channel, msg.note)]
                start, vel = stack.pop(0)
                if not stack:
                    del opened[(msg.channel, msg.note)]
                notes.append((msg.note, to_sec(start), to_sec(tick), vel))
        if notes:
            per_track.append(notes)
    if not per_track:
        raise ValueError(f"MIDI 中没有音符: {path}")

    rows = []
    if len(per_track) >= 2:
        # 多轨：平均音高最高的轨视为右手，其余为左手
        right = max(range(len(per_track)), key=lambda i: np.mean([n[0] for n in per_track[i]]))
        for i, notes in enumerate(per_track):
            rows += [(*n, 1 if i == right else 0) for n in notes]
    else:
        rows = [(*n, 1 if n[0] >= SPLIT_PITCH else 0) for n in per_track[0]]

    rows.sort(key=lambda r: (r[1], r[0]))
    arr = np.array(rows, dtype=np.float64)
    return {
        "pitch": arr[:, 0].astype(np.int16),
        "start": arr[:, 1],
        "end": np.maximum(arr[:, 2], arr[:, 1] + 0.05),
        "velocity": arr[:, 3].astype(np.int16),
        "hand": arr[:, 4].astype(np.int8),
    }
