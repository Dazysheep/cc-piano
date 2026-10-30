"""钢琴录音 → MIDI（字节跳动开源的钢琴转写模型 piano_transcription_inference）。

用法: python piano/transcribe.py <音频文件> [--out 输出.mid] [--json-progress]
第一次运行会把模型(约 170MB)下载到 tools/models/。
带鼓、贝斯的完整编曲会先用 Demucs 分离出旋律乐器再转写（--no-split 可跳过）。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "tools" / "models"
os.environ.setdefault("TORCH_HOME", str(MODEL_DIR / "torch"))   # Demucs 模型也缓存在项目里，不放 C 盘
os.environ.setdefault("HF_HOME", str(MODEL_DIR / "hf"))
MODEL = MODEL_DIR / "note_F1=0.9677_pedal_F1=0.9186.pth"
MODEL_URL = "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1"
MODEL_MIN_BYTES = 150_000_000
GHOST_RATIO = 0.6   # 力度低于整首中位数 60% 的音符视为余音/泛音，去掉

_json = False


def emit(stage: str, msg: str, pct: float | None = None, **extra) -> None:
    if _json:
        print("@@" + json.dumps({"stage": stage, "msg": msg, "pct": pct, **extra}, ensure_ascii=False), flush=True)
    else:
        print(f"  {msg}" + (f" {pct:.0%}" if pct is not None else ""), flush=True)


def ensure_model() -> Path:
    if MODEL.exists() and MODEL.stat().st_size > MODEL_MIN_BYTES:
        return MODEL
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    part = MODEL.with_suffix(".part")
    emit("model", "首次使用，正在下载转写模型（约 170MB）", 0)
    with urllib.request.urlopen(MODEL_URL, timeout=60) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, 0.0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total and time.time() - last > 1:
                emit("model", "正在下载转写模型", done / total)
                last = time.time()
    if part.stat().st_size < MODEL_MIN_BYTES:
        part.unlink()
        raise RuntimeError("模型下载不完整，请检查网络后重试")
    part.replace(MODEL)
    return MODEL


def separate(audio: Path, out_wav: Path) -> bool:
    """用 Demucs 去掉鼓、贝斯和人声，只留旋律乐器，转写会干净得多。返回是否成功。"""
    try:
        import numpy as np
        import soundfile as sf
        import torch
        import torchaudio.functional as AF
        from demucs.api import Separator
    except ImportError:
        emit("separate", "未安装音源分离(demucs)，直接转写原曲")
        return False
    import imageio_ffmpeg
    emit("separate", "正在分离乐器：去掉鼓、贝斯和人声（约 1 分钟）")
    tmp = out_wav.with_suffix(".src.wav")   # 先统一解码成 wav，mp3/m4a 等格式都能读
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(audio), str(tmp)], check=True)
    wav, sr = sf.read(str(tmp), dtype="float32", always_2d=True)
    tmp.unlink()
    sep = Separator(model="htdemucs", device="cpu")
    x = torch.from_numpy(wav.T.copy())
    if x.shape[0] == 1:
        x = x.repeat(2, 1)
    if sr != sep.samplerate:
        x = AF.resample(x, sr, sep.samplerate)
    _, stems = sep.separate_tensor(x, sep.samplerate)
    melody = stems["other"].numpy().T
    if float(np.sqrt((melody ** 2).mean())) < 1e-3:   # 几乎没有旋律乐器（可能本来就是纯人声/纯鼓），退回原曲
        emit("separate", "没有分离出旋律乐器，直接转写原曲")
        return False
    sf.write(str(out_wav), melody, sep.samplerate)
    return True


def transcribe(audio: Path, out: Path, split: bool = True) -> Path:
    import imageio_ffmpeg
    wav = out.with_suffix(".16k.wav")
    melody = out.with_suffix(".melody.wav")
    if split and separate(audio, melody):
        audio = melody
    emit("decode", "正在读取音频")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(audio),
                    "-ac", "1", "-ar", "16000", str(wav)], check=True)
    melody.unlink(missing_ok=True)
    model = ensure_model()

    import librosa
    from piano_transcription_inference import PianoTranscription, sample_rate

    y, _ = librosa.load(str(wav), sr=sample_rate, mono=True)
    wav.unlink()
    minutes = len(y) / sample_rate / 60
    emit("transcribe", f"正在转写（{minutes:.1f} 分钟的音频，CPU 上大约需要 {max(1, round(minutes * 1.5))} 分钟）")
    transcriptor = PianoTranscription(device="cpu", checkpoint_path=str(model))
    transcriptor.transcribe(y, str(out))
    kept, dropped = drop_ghost_notes(out)
    emit("done", f"转写完成：{kept} 个音符（过滤掉 {dropped} 个余音/泛音）", 1, midi=str(out))
    return out


def drop_ghost_notes(path: Path, ratio: float = GHOST_RATIO) -> tuple[int, int]:
    """去掉力度远低于整体的音符：多为混响余音、泛音被误判成的新音符。"""
    import mido
    import numpy as np
    mid = mido.MidiFile(path)
    vels = [m.velocity for tr in mid.tracks for m in tr if m.type == "note_on" and m.velocity > 0]
    if not vels:
        return 0, 0
    thr = ratio * float(np.median(vels))
    kept = dropped = 0
    for tr in mid.tracks:
        out, carry, ghost = [], 0, {}
        for m in tr:
            t = m.time + carry
            if m.type == "note_on" and m.velocity > 0:
                if m.velocity < thr:
                    ghost[(m.channel, m.note)] = ghost.get((m.channel, m.note), 0) + 1
                    dropped += 1
                    carry = t
                    continue
                kept += 1
            elif m.type in ("note_off", "note_on") and ghost.get((m.channel, m.note)):
                ghost[(m.channel, m.note)] -= 1   # 被丢掉的音符对应的松开事件
                carry = t
                continue
            out.append(m.copy(time=t))
            carry = 0
        tr[:] = out
    mid.save(path)
    return kept, dropped


def main() -> int:
    global _json
    ap = argparse.ArgumentParser(description="钢琴录音转 MIDI")
    ap.add_argument("audio", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--no-split", action="store_true", help="不做乐器分离（纯钢琴录音可以加上，快一些）")
    ap.add_argument("--json-progress", action="store_true")
    args = ap.parse_args()
    _json = args.json_progress
    out = args.out or args.audio.with_suffix(".mid")
    try:
        transcribe(args.audio.resolve(), out.resolve(), split=not args.no_split)
    except Exception as e:
        emit("error", f"转写失败：{e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
