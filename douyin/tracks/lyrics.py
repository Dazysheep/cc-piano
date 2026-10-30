"""歌词：AI 识别（faster-whisper，逐词时间）+ LRC 校对，副歌定位与片段选择。

- 文字以 LRC 为准（修正识别听错的词），时间以识别结果为准（逐词高亮）；识别不到的句子按整体偏移套用 LRC 时间
- 副歌：LRC 里重复次数最多的那几句连成的段落；没有 LRC 时用原曲能量最高的段落
- 片段：在 [min_len, max_len] 秒里挑副歌覆盖最多、开头一进来就是副歌、不在句子中间截断的一段
- 没有 LRC 时也可以贴纯文本歌词（原文一行、中文翻译一行交替，翻译可以没有）：整份歌词按顺序和识别到的词对齐，
  文字以贴的为准，时间以识别为准；录屏里没唱到的句子（在第一句之前、最后一句之后）丢掉
用法: python tracks/lyrics.py <工作目录> --lrc 歌词.lrc [--model medium]
      python tracks/lyrics.py <工作目录> --text 歌词.txt
      工作目录里要有 stems/vocals.wav；输出 lyrics.json（整首时间，秒）
"""
import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "tools" / "models"


def parse_lrc(path: Path) -> list[dict]:
    """[{t, text}]，跳过网易云的 json 元数据行；空歌词行保留（表示间奏开始）。"""
    out = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        for m in re.finditer(r"\[(\d+):(\d+(?:\.\d+)?)\]", line):
            text = re.sub(r"\[[^\]]*\]", "", line).strip()
            out.append({"t": int(m.group(1)) * 60 + float(m.group(2)), "text": text})
    out.sort(key=lambda x: x["t"])
    return out


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def transcribe(vocals: Path, model: str = "medium", language: str = "en") -> list[dict]:
    """逐词识别：[{w, s, e, p}]。
    模型放在 tools/models/whisper-<名字>（没有时从 HuggingFace 下载到 tools/models/hf）。"""
    os.environ.setdefault("HF_HOME", str(MODELS / "hf"))
    from faster_whisper import WhisperModel
    local = MODELS / f"whisper-{model}"
    m = WhisperModel(str(local) if (local / "model.bin").exists() else model, device="cpu", compute_type="int8",
                     cpu_threads=os.cpu_count() or 4)
    # 自己解码成 16kHz 单声道再交给模型（faster-whisper 自带的 PyAV 解码和项目里的 av 版本不兼容）
    import librosa
    import soundfile as sf
    x, sr = sf.read(str(vocals), dtype="float32", always_2d=True)
    audio = librosa.resample(x.mean(axis=1), orig_sr=sr, target_sr=16000)
    audio = audio / max(float(np.abs(audio).max()), 1e-6) * 0.9     # 分离出的人声常常很小声，先拉到满幅
    # 输入已经是分离出的人声，不用 VAD（它会把唱歌当成非语音滤掉）
    segs, _ = m.transcribe(audio, language=language, word_timestamps=True, vad_filter=False,
                           condition_on_previous_text=False, beam_size=5)
    words = []
    for s in segs:
        for w in s.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                          "p": round(w.probability, 3)})
    return words


def global_offset(lrc: list[dict], words: list[dict], span: float = 40.0) -> float:
    """音频和 LRC 的整体时间差（音频里的时间 - LRC 时间）：剪映缓存的音频可能带前导静音，录屏更是从中间开始。
    在 ±span 秒内每 0.25 秒试一次，看识别出的词落在「当时那句 LRC」里的个数最多的偏移。"""
    if not words:
        return 0.0
    ts = np.array([x["t"] for x in lrc])
    toks = [{_norm(w) for w in x["text"].split()} for x in lrc]
    best, best_n = 0.0, -1
    for off in np.arange(-span, span + 0.01, 0.25):
        n = 0
        for w in words:
            i = int(np.searchsorted(ts, w["s"] - off, side="right")) - 1
            if i >= 0 and _norm(w["w"]) in toks[i]:
                n += 1
        if n > best_n:
            best, best_n = float(off), n
    return best


def align(lrc: list[dict], words: list[dict], offset: float | None = None) -> list[dict]:
    """每句 LRC 在附近的识别结果里做模糊匹配，得到逐词时间。返回 [{start, end, text, words:[[w,s,e]], heard}]。
    时间都是音频里的时间（LRC 时间 + 整体偏移）。"""
    g = global_offset(lrc, words) if offset is None else offset
    lrc = [{"t": x["t"] + g, "text": x["text"]} for x in lrc]
    lines = [x for x in lrc if x["text"]]
    nxt = {id(x): (lrc[i + 1]["t"] if i + 1 < len(lrc) else x["t"] + 8) for i, x in enumerate(lrc)}
    rec = [_norm(w["w"]) for w in words]
    out, offsets = [], []
    for ln in lines:
        toks = ln["text"].split()
        keys = [_norm(t) for t in toks]
        lo, hi = ln["t"] - 2.5, nxt[id(ln)] + 1.5
        cand = [i for i, w in enumerate(words) if lo <= w["s"] <= hi]
        times = [None] * len(toks)
        heard = ""
        if cand:
            sub = [rec[i] for i in cand]
            sm = difflib.SequenceMatcher(None, keys, sub, autojunk=False)
            for a, b, size in sm.get_matching_blocks():
                for k in range(size):
                    w = words[cand[b + k]]
                    times[a + k] = (w["s"], w["e"])
            heard = " ".join(words[i]["w"] for i in cand)
        hit = sum(t is not None for t in times)
        out.append({"lrc_t": ln["t"], "text": ln["text"], "toks": toks, "times": times,
                    "match": round(hit / max(1, len(toks)), 2), "heard": heard, "next": nxt[id(ln)]})
        if hit >= max(2, len(toks) // 2) and times[0] is not None:
            offsets.append(times[0][0] - ln["t"])
    off = float(np.median(offsets)) if offsets else 0.0
    res = []
    for o in out:
        toks, times = o["toks"], o["times"]
        if o["match"] < 0.34:               # 基本没识别到：整句按 LRC 时间 + 整体偏移，平均分配给每个词
            s0 = o["lrc_t"] + off
            e0 = min(o["next"] + off - 0.3, s0 + max(2.5, 0.9 * len(toks)))   # 慢歌一句常唱 6~8 秒
            times = [None] * len(toks)
            times[0], times[-1] = (s0, s0), (e0, e0)
        times = _fill(times)
        res.append({"start": round(times[0][0], 3), "end": round(times[-1][1], 3), "text": o["text"],
                    "words": [[w, round(s, 3), round(e, 3)] for w, (s, e) in zip(toks, times)],
                    "match": o["match"], "heard": o["heard"]})
    for a, b in zip(res, res[1:]):            # 不重叠
        a["end"] = min(a["end"], b["start"] - 0.02)
    return res, g


def _fill(times: list) -> list:
    """没匹配上的词按字母数在前后已知时间之间插值。"""
    n = len(times)
    known = [i for i, t in enumerate(times) if t is not None]
    if not known:
        return [(0.0, 0.0)] * n
    out = list(times)
    for i in range(n):
        if out[i] is not None:
            continue
        left = max((k for k in known if k < i), default=None)
        right = min((k for k in known if k > i), default=None)
        if left is None:
            s = times[right][0] - 0.35 * (right - i)
            out[i] = (s, s + 0.3)
        elif right is None:
            s = times[left][1] + 0.3 * (i - left - 1)
            out[i] = (s, s + 0.3)
        else:
            a, b = times[left][1], times[right][0]
            f0, f1 = (i - left) / (right - left), (i - left + 1) / (right - left)
            out[i] = (a + (b - a) * f0, a + (b - a) * f1)
    return out


def chorus_spans(lines: list[dict], lrc: list[dict]) -> list[list[float]]:
    """重复次数最多的句子 = 副歌；相邻的副歌句连成一段，结束于下一句非副歌（或间奏空行）的开始。"""
    count = {}
    for ln in lines:
        count[ln["text"].lower()] = count.get(ln["text"].lower(), 0) + 1
    top = max(count.values(), default=0)
    if top < 2:
        return []
    is_ch = [count[ln["text"].lower()] == top for ln in lines]
    spans = []
    for i, ln in enumerate(lines):
        if not is_ch[i]:
            continue
        end = lines[i + 1]["start"] if i + 1 < len(lines) else ln["end"] + 1
        gap = [x["t"] for x in lrc if not x["text"] and ln["start"] < x["t"] < end + 0.5]
        end = min([end] + [g for g in gap])
        if spans and i > 0 and is_ch[i - 1] and ln["start"] - 0.3 <= spans[-1][1] + 0.5:   # 紧挨着上一句副歌
            spans[-1][1] = round(end, 3)
        else:
            spans.append([round(ln["start"] - 0.3, 3), round(end, 3)])
    return spans


def choose_window(lines: list[dict], spans: list[list[float]], intro: float = 4.0,
                  min_len: float = 95, max_len: float = 106, target: float = 100,
                  cold_open: bool = False) -> tuple[float, float]:
    """返回 (start, duration)，整首时间。开头 intro 秒是拨片开头，第一句歌词在开头之后出现。
    cold_open：额外奖励「片段一开始就是副歌」（开头第一秒就是最抓耳的部分）。"""
    starts = [ln["start"] - intro - 1.0 for ln in lines if ln["start"] - intro - 1.0 >= 0]
    ends = [ln["start"] - 0.2 for ln in lines] + [ln["end"] + 1.2 for ln in lines]
    best, best_score = (max(0.0, (spans[0][0] if spans else 30) - intro - 1), target), -1e9
    for s in starts:
        first = next((ln for ln in lines if ln["start"] >= s + intro), None)
        for e in ends + [s + target]:
            d = e - s
            if not (min_len <= d <= max_len):
                continue
            cover, full, cut = 0.0, 0, 0
            for a, b in spans:
                ov = max(0.0, min(b, e) - max(a, s + intro))
                cover += ov
                if ov >= 0.95 * (b - a):
                    full += 1
                elif ov > 0:
                    cut += 1
            hook = any(a - 0.5 <= first["start"] <= b for a, b in spans) if first else False
            score = cover + 8 * full - 6 * cut + 4 * hook - 0.2 * abs(d - target)
            if cold_open and any(abs(s + 1.0 - a) <= 1.5 for a, _ in spans):
                score += 12
            if score > best_score:
                best, best_score = (round(s, 2), round(d, 2)), score
    return best


# ---------------------------------------------------------------- 纯文本歌词
CJK = re.compile(r"[\u4e00-\u9fff]")


def parse_plain(text: str) -> tuple[list[str], dict]:
    """原文和翻译交替的纯文本 → (原文每句, {原文: 翻译})。含中文字符的行算翻译，跟在上一句原文后面。
    句末的逗号句号去掉（字幕里不需要）。"""
    lines, zh = [], {}
    for raw in text.splitlines():
        t = raw.strip().rstrip(",，.。")
        if not t:
            continue
        if CJK.search(t) and lines:
            zh.setdefault(lines[-1], t)
        elif not CJK.search(t):
            lines.append(t)
    return lines, zh


# 识别结果（粤语歌常出繁体）→ 简体，只为了和贴的简体歌词逐字对齐；常用字够用，没收录的字靠前后插值
T2S = dict(zip("試將營無與聯難過從傾夠們來時這個說對會還著後裡為說愛讓聽見誰麼開關問題經應該當覺樣頭話親們歲歡淚邊車進給長電視還學氣場實",
               "试将营无与联难过从倾够们来时这个说对会还着后里为说爱让听见谁么开关问题经应该当觉样头话亲们岁欢泪边车进给长电视还学气场实"))


def parse_cjk(text: str) -> list[str]:
    """中文歌词（每句后面可能跟一行拼音 / 粤语拼音）→ 只留中文句子，句末标点去掉。"""
    return [t for t in (raw.strip().rstrip(",，.。") for raw in text.splitlines()) if t and CJK.search(t)]


def align_cjk(lines: list[str], words: list[dict]) -> list[dict]:
    """中文歌词逐字和识别结果整体对齐：识别出的每个词按字数均分时间，繁体先转简体；
    返回和 align_text 一样的格式，words 是逐字的 [字, 开始, 结束]（空格不算字）。"""
    rec, rt = [], []
    for w in words:
        cs = [T2S.get(c, c) for c in w["w"] if CJK.match(c)]
        for k, c in enumerate(cs):
            d = (w["e"] - w["s"]) / max(len(cs), 1)
            rec.append(c)
            rt.append((w["s"] + k * d, w["s"] + (k + 1) * d))
    toks = [(i, c) for i, ln in enumerate(lines) for c in ln if CJK.match(c)]
    times = [None] * len(toks)
    sm = difflib.SequenceMatcher(None, [c for _, c in toks], rec, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            times[a + k] = rt[b + k]
    res = []
    for i, ln in enumerate(lines):
        idx = [k for k, (li, _) in enumerate(toks) if li == i]
        tt = [times[k] for k in idx]
        res.append({"text": ln, "toks": [toks[k][1] for k in idx], "times": tt,
                    "match": round(sum(t is not None for t in tt) / max(1, len(idx)), 2)})
    matched = [i for i, r in enumerate(res) if r["match"] >= 0.34]
    if not matched:
        return []
    out = []
    for i in range(matched[0], matched[-1] + 1):
        r = res[i]
        tt = r["times"]
        if r["match"] < 0.34:                            # 漏听的句子：夹在前后两句之间
            prev_end = out[-1]["end"] if out else None
            nxt = next(res[j] for j in matched if j > i)
            s0 = (prev_end or 0) + 0.15
            e0 = min(s0 + max(1.5, 0.3 * len(r["toks"])), next(t for t in nxt["times"] if t)[0] - 0.15)
            tt = [None] * len(r["toks"])
            tt[0], tt[-1] = (s0, s0), (e0, e0)
        tt = _fill(tt)
        out.append({"start": round(tt[0][0], 3), "end": round(tt[-1][1], 3), "text": r["text"],
                    "words": [[c, round(s, 3), round(e, 3)] for c, (s, e) in zip(r["toks"], tt)],
                    "match": r["match"], "heard": ""})
    for a, b in zip(out, out[1:]):
        a["end"] = min(a["end"], b["start"] - 0.02)
    return out


def align_text(lines: list[str], words: list[dict]) -> list[dict]:
    """整份歌词（按顺序）和识别结果整体对齐（重复的副歌靠顺序区分），返回和 align 一样格式的句子列表。"""
    toks = [(i, t) for i, ln in enumerate(lines) for t in ln.split()]
    keys = [_norm(t) for _, t in toks]
    rec = [_norm(w["w"]) for w in words]
    times = [None] * len(toks)
    sm = difflib.SequenceMatcher(None, keys, rec, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            times[a + k] = (words[b + k]["s"], words[b + k]["e"])
    res = []
    for i, ln in enumerate(lines):
        idx = [k for k, (li, _) in enumerate(toks) if li == i]
        tt = [times[k] for k in idx]
        hit = sum(t is not None for t in tt)
        res.append({"text": ln, "toks": [toks[k][1] for k in idx], "times": tt,
                    "match": round(hit / max(1, len(idx)), 2)})
    matched = [i for i, r in enumerate(res) if r["match"] >= 0.34]
    if not matched:
        return []
    out = []
    for i in range(matched[0], matched[-1] + 1):         # 第一句之前、最后一句之后：录屏里没唱到
        r = res[i]
        tt = r["times"]
        if r["match"] < 0.34:                            # 中间漏听的句子：夹在前后两句之间，平均分配
            prev_end = out[-1]["end"] if out else None
            nxt = next(res[j] for j in matched if j > i)
            s0 = (prev_end or 0) + 0.15
            e0 = min(s0 + max(2.0, 0.6 * len(r["toks"])), next(t for t in nxt["times"] if t)[0] - 0.15)
            tt = [None] * len(r["toks"])
            tt[0], tt[-1] = (s0, s0), (e0, e0)
        tt = _fill(tt)
        out.append({"start": round(tt[0][0], 3), "end": round(tt[-1][1], 3), "text": r["text"],
                    "words": [[w, round(s, 3), round(e, 3)] for w, (s, e) in zip(r["toks"], tt)],
                    "match": r["match"], "heard": ""})
    for a, b in zip(out, out[1:]):
        a["end"] = min(a["end"], b["start"] - 0.02)
    return out


def run_text(work: Path, text_path: Path, model: str = "medium", vocals: Path | None = None) -> dict:
    """纯文本歌词版的 run：识别（共用缓存）→ 整体对齐 → 副歌，写 lyrics.json（多一个 zh：翻译）。"""
    vocals = vocals or work / "stems" / "vocals.wav"
    cache = work / "whisper_words.json"
    if cache.exists():
        words = json.loads(cache.read_text(encoding="utf-8"))
    else:
        words = transcribe(vocals, model)
        cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    text = Path(text_path).read_text(encoding="utf-8-sig")
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if CJK.search(first):                    # 第一行是中文：中文歌（下面跟的是拼音，不显示），逐字对齐
        lines_en, zh = parse_cjk(text), {}
        lines = align_cjk(lines_en, words)
    else:                                    # 第一行是外文：原文 / 中文翻译交替
        lines_en, zh = parse_plain(text)
        lines = align_text(lines_en, words)
    spans = chorus_spans(lines, [{"t": ln["start"], "text": ln["text"]} for ln in lines])
    out = {"lines": lines, "chorus": spans, "offset": 0.0, "words": len(words), "zh": zh, "source": "text"}
    (work / "lyrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"识别 {len(words)} 个词，对上 {len(lines)}/{len(lines_en)} 句（其余不在录屏里）")
    for ln in lines:
        flag = "" if ln["match"] >= 0.6 else "  ← 听得不清，时间是推算的"
        print(f"{ln['start']:7.2f}-{ln['end']:7.2f}  {ln['match']:.2f}  {ln['text']}{flag}")
    print("副歌：", spans)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="歌词识别 + LRC 校对")
    ap.add_argument("work", type=Path)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--lrc", type=Path)
    src.add_argument("--text", type=Path, help="纯文本歌词（原文 / 翻译交替）")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--vocals", type=Path, help="默认 <工作目录>/stems/vocals.wav")
    a = ap.parse_args()
    if a.text:
        run_text(a.work, a.text, a.model, a.vocals)
    else:
        run(a.work, a.lrc, a.model, a.vocals)
    return 0


def run(work: Path, lrc_path: Path, model: str = "medium", vocals: Path | None = None) -> dict:
    """识别（结果缓存在 whisper_words.json）→ 校对 → 副歌，写 lyrics.json 并返回。"""
    vocals = vocals or work / "stems" / "vocals.wav"
    cache = work / "whisper_words.json"
    if cache.exists():
        words = json.loads(cache.read_text(encoding="utf-8"))
    else:
        words = transcribe(vocals, model)
        cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    lrc = parse_lrc(lrc_path)
    lines, off = align(lrc, words)
    spans = chorus_spans(lines, [{"t": x["t"] + off, "text": x["text"]} for x in lrc])
    out = {"lines": lines, "chorus": spans, "offset": off, "words": len(words)}
    (work / "lyrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"识别 {len(words)} 个词，整体偏移 {off:+.2f}s")
    for ln in lines:
        flag = "" if ln["match"] >= 0.6 else "  ← 识别：" + ln["heard"][:60]
        print(f"{ln['start']:7.2f}  {ln['match']:.2f}  {ln['text']}{flag}")
    print("副歌：", spans)
    return out


if __name__ == "__main__":
    sys.exit(main())
