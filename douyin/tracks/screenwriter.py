"""cc-piano「编剧」的后台：根据一首歌的歌词、旋律和网易云评论，用用户自己选的大模型编出一条故事线（用户 2026-10-28 设计）。

- 只做编剧：系统提示固定，输出只有「重要动画节点（图 + 短文字）」和一份能直接出片的方案（plan），聊天也只能改剧本。
- 省 token：评论用编号（c1、c2…）给模型，模型只回编号，原文由这里填回去（也保证评论一字不差）；动画只给一份简短目录
  （动画库：想象画面 / 小动画 / 开头结尾小剧场 / 女生动作，最近用过的打星号），模型挑名字，不发代码；知识库只给要点
  （LLM Wiki 里 findings 的结论标题 + 最新日报的改进建议 + 热词）。
- 每天尽量不重复：每次编好的故事线记在 output/writer/history.jsonl，下次把最近 10 条的主题、开头结尾、用过的画面告诉模型。
- 接口：多套配置（OpenAI 兼容：DeepSeek / 通义 / Kimi / 智谱 / 豆包 / OpenAI…；Anthropic Claude 原生接口），
  配置存 web/writer_profiles.json，密钥只存用户环境变量 CC_PIANO_WRITER_KEY_<配置名>（不写文件、不回传网页）。
- 套用：先把歌曲 json 存一份历史（和分段修改同一套），再写开头评论、每条评论配的画面、小动画、只听某一轨、尾声、结尾问题、标题文案。
"""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np

import clawd_anim as ca
import moments
import template_lib
import visions

import sys as _sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SONGS = HERE / "songs"
OUT = ROOT / "output" / "writer"
_sys.path.insert(0, str(ROOT / "data"))
try:
    import db as _studioDb
except ImportError:
    _studioDb = None
PROFILES = ROOT / "web" / "writer_profiles.json"
KEY_ENV = "CC_PIANO_WRITER_KEY_"
WORKFLOW = ROOT.parent / "workflow"
WIKI = WORKFLOW / "llm-wiki" / "resource" / "auto-douyin-knowledges" / "wiki"
ZH_TRACK = {"vocals": "人声", "piano": "钢琴", "guitar": "吉他", "bass": "贝斯", "drums": "鼓", "other": "其他"}
DEFAULT_PROFILES = {"active": "deepseek", "profiles": [
    {"id": "deepseek", "name": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    {"id": "claude", "name": "Claude", "kind": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude-opus-5-5"},
]}


# ====================================================================== 接口配置（多套，可切换）
def _env_key(pid: str) -> str:
    name = KEY_ENV + re.sub(r"\W", "_", pid).upper()
    key = os.environ.get(name, "")
    if not key and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, name)[0]
        except OSError:
            key = ""
    return key


def profiles() -> dict:
    data = json.loads(PROFILES.read_text(encoding="utf-8")) if PROFILES.exists() else json.loads(json.dumps(DEFAULT_PROFILES))
    for p in data["profiles"]:
        p["has_key"] = bool(_env_key(p["id"]))
        p["key_env"] = KEY_ENV + re.sub(r"\W", "_", p["id"]).upper()
    return data


def save_profile(pid: str, name: str, kind: str, base_url: str, model: str, key: str | None, activate: bool) -> dict:
    if not re.match(r"^[A-Za-z0-9_-]{1,24}$", pid or ""):
        raise ValueError("配置名只能用字母、数字、- 和 _（24 个字以内）")
    if kind not in ("openai", "anthropic"):
        raise ValueError("接口类型只能是 openai（兼容接口）或 anthropic（Claude 原生）")
    if not re.match(r"^https?://", base_url or ""):
        raise ValueError("接口地址要以 http:// 或 https:// 开头")
    data = profiles()
    row = {"id": pid, "name": (name or pid)[:30], "kind": kind, "base_url": base_url.rstrip("/"), "model": model.strip()[:80]}
    data["profiles"] = [p for p in data["profiles"] if p["id"] != pid] + [row]
    if activate or not data.get("active"):
        data["active"] = pid
    _write_profiles(data)
    if key:                                              # 密钥只进用户环境变量
        env = KEY_ENV + re.sub(r"\W", "_", pid).upper()
        os.environ[env] = key
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, env, 0, winreg.REG_SZ, key)
    return profiles()


def delete_profile(pid: str) -> dict:
    data = profiles()
    data["profiles"] = [p for p in data["profiles"] if p["id"] != pid]
    if data.get("active") == pid:
        data["active"] = data["profiles"][0]["id"] if data["profiles"] else ""
    _write_profiles(data)
    return profiles()


def set_active(pid: str) -> dict:
    data = profiles()
    if not any(p["id"] == pid for p in data["profiles"]):
        raise ValueError("没有这个配置")
    data["active"] = pid
    _write_profiles(data)
    return profiles()


def _write_profiles(data: dict) -> None:
    rows = [{k: p[k] for k in ("id", "name", "kind", "base_url", "model")} for p in data["profiles"]]
    PROFILES.write_text(json.dumps({"active": data.get("active", ""), "profiles": rows}, ensure_ascii=False, indent=1),
                        encoding="utf-8")


def llm(system: str, msgs: list[dict], pid: str | None = None, max_tokens: int = 4000) -> tuple[str, dict]:
    """调用选中的配置，返回 (回复文字, {input_tokens, output_tokens, model, profile})。"""
    data = profiles()
    pid = pid or data.get("active")
    prof = next((p for p in data["profiles"] if p["id"] == pid), None)
    if not prof:
        raise PermissionError("还没有选接口：点右上角「接口设置」")
    key = _env_key(prof["id"])
    if not key:
        raise PermissionError(f"「{prof['name']}」还没有填密钥：点右上角「接口设置」")
    if prof["kind"] == "anthropic":
        url = prof["base_url"].rstrip("/") + "/v1/messages"
        body = {"model": prof["model"], "max_tokens": max_tokens, "system": system, "messages": msgs}
        headers = {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}
    else:
        url = prof["base_url"].rstrip("/") + "/chat/completions"
        body = {"model": prof["model"], "max_tokens": max_tokens, "temperature": 0.8,
                "messages": [{"role": "system", "content": system}] + msgs}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    req = urllib.request.Request(url, json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{prof['name']} 接口返回 {e.code}：{e.read().decode('utf-8', 'replace')[:300]}") from e
    except OSError as e:
        raise RuntimeError(f"连不上 {prof['name']} 接口：{e}") from e
    if prof["kind"] == "anthropic":
        text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
        u = res.get("usage", {})
        usage = {"input_tokens": u.get("input_tokens", 0), "output_tokens": u.get("output_tokens", 0)}
    else:
        text = res["choices"][0]["message"]["content"]
        u = res.get("usage", {})
        usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}
    return text, {**usage, "model": prof["model"], "profile": prof["name"]}


# ====================================================================== 素材：歌词、旋律、评论
def song_path(stem: str) -> Path:
    p = (SONGS / f"{stem}.json").resolve()
    if p.parent != SONGS.resolve() or not p.exists():
        raise FileNotFoundError(f"没有这首歌：{stem}")
    return p


def _work(song: dict) -> Path:
    return ROOT / "output" / f"tracks_{song['title'].replace(' ', '_')}" / "work"


def _fmt(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _song(stem: str) -> dict:
    song = template_lib.load_song(song_path(stem))
    work = _work(song)
    if (work / "song.json").exists():                   # prepare 选好的片段（start = auto 时）
        r = json.loads((work / "song.json").read_text(encoding="utf-8"))
        if song.get("start") == "auto":
            song["start"], song["duration"] = r["start"], r["duration"]
    return song


def lyrics_lines(song: dict) -> list[dict]:
    """视频时间里的歌词：[{t, text}]。有 lyrics.json 用它，没有就用 AI 听写的分句。"""
    work = _work(song)
    s0, dur = float(song.get("start") or 0), float(song.get("duration") or 96)
    out = []
    if (work / "lyrics.json").exists():
        for ln in json.loads((work / "lyrics.json").read_text(encoding="utf-8")).get("lines", []):
            if s0 <= ln["start"] < s0 + dur:
                out.append({"t": round(ln["start"] - s0, 1), "text": ln["text"]})
    elif (work / "whisper_words.json").exists():
        cur = []
        for w in json.loads((work / "whisper_words.json").read_text(encoding="utf-8")) + [None]:
            if w is None or (cur and w["s"] - cur[-1]["e"] > 0.8):
                if cur and s0 <= cur[0]["s"] < s0 + dur:
                    out.append({"t": round(cur[0]["s"] - s0, 1), "text": "".join(x["w"] for x in cur)[:40]})
                cur = []
            if w is not None:
                cur.append(w)
    return out


def melody(song: dict) -> dict:
    """旋律的简短描述：速度，每 6 秒一段的响度（安静 / 中 / 强）和哪几条音轨在响。"""
    work = _work(song)
    if not (work / "analysis.json").exists():
        return {"tempo": None, "segments": []}
    a = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
    rate = a.get("env_rate", 200)
    seg_start = float(a.get("song", {}).get("start", song.get("start") or 0))
    env = {}
    for k in ZH_TRACK:
        f = work / f"env_{k}.npy"
        if f.exists():
            e = np.load(f)
            env[k] = e.max(axis=1) if e.ndim > 1 else e
    mix = np.load(work / "env_mix.npy") if (work / "env_mix.npy").exists() else None
    mix = mix.max(axis=1) if mix is not None and mix.ndim > 1 else mix
    s0, dur = float(song.get("start") or 0), float(song.get("duration") or 96)
    segs = []
    if mix is not None and len(mix):
        lo, hi = np.percentile(mix, 35), np.percentile(mix, 75)
        for t in np.arange(0, dur, 6.0):
            i0, i1 = int((s0 + t - seg_start) * rate), int((s0 + t + 6 - seg_start) * rate)
            if i1 <= 0 or i0 >= len(mix):
                continue
            i0 = max(0, i0)
            lv = float(np.mean(mix[i0:i1]))
            on = [ZH_TRACK[k] for k, e in env.items() if i0 < len(e) and np.mean(e[i0:i1]) > 0.18]
            segs.append(f"{_fmt(t)} {'强' if lv > hi else '中' if lv > lo else '安静'} {'+'.join(on) or '—'}")
    return {"tempo": round(float(a.get("tempo", 0))), "segments": segs}


def comments_file(stem: str) -> Path:
    return OUT / stem / "comments.json"


def load_comments(stem: str) -> list[dict]:
    f = comments_file(stem)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save_comments(stem: str, rows: list[dict]) -> list[dict]:
    clean = []
    for r in rows:
        text = str(r.get("text") or "").strip()[:300]
        if len(text) >= 2:
            clean.append({"text": text, "user": str(r.get("user") or "")[:40], "likes": str(r.get("likes") or "")[:12],
                          "use": r.get("use", True) is not False, "ocr": bool(r.get("ocr"))})
    comments_file(stem).parent.mkdir(parents=True, exist_ok=True)
    comments_file(stem).write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    if _studioDb:
        try:
            _studioDb.save_comments(stem, clean)
        except Exception:
            pass
    return clean


def ocr_comments(stem: str, progress=None) -> list[dict]:
    """录屏里的评论 → 合并进已有的评论（已有的、用户改过的不动，新认出来的加在后面）。"""
    import comment_ocr
    song = _song(stem)
    video = Path(song.get("audio", ""))
    if video.suffix.lower() not in (".mp4", ".mov") or not video.exists():
        raise ValueError("这首歌的音频不是录屏，没有评论可认，请手动粘贴")
    found = comment_ocr.from_video(video, progress=progress)
    old = load_comments(stem)
    have = {re.sub(r"\W", "", c["text"])[:24] for c in old}
    rows = old + [c for c in found if re.sub(r"\W", "", c["text"])[:24] not in have]
    return save_comments(stem, rows)


def materials(stem: str) -> dict:
    song = _song(stem)
    return {"song": {"stem": stem, "title": song.get("title"), "artist": song.get("artist"),
                     "duration": song.get("duration"), "intro": song.get("intro"),
                     "ending_seconds": song.get("ending_seconds", 10) if song.get("ending") else 0,
                     "tracks": song.get("tracks_keep") or [], "audio": song.get("audio")},
            "lyrics": lyrics_lines(song), "melody": melody(song), "comments": load_comments(stem),
            "versions": versions(stem)}


# ====================================================================== 知识库：动画目录 + LLM Wiki 要点
def recent_used(n: int = 1) -> dict:
    """前一首歌（按改动时间）+ 最近两次编剧用过的画面 / 小动画 / 开头结尾，给模型打星号，尽量别和前一天撞
    （更早的不打星号：库不大，一首歌常用掉十几个画面；更早的重复靠「最近编过的故事」那段去避开）。"""
    used = {"vision": set(), "moment": set(), "opening": set(), "ending": set()}
    for p in sorted(SONGS.glob("*.json"), key=lambda q: q.stat().st_mtime, reverse=True)[:n]:
        try:
            s = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        for act in s.get("story", {}).get("acts", []):
            for c in act.get("cards", []):
                if c.get("vision"):
                    used["vision"].add(c["vision"])
        for m in s.get("moments", []):
            used["moment"].add(m.get("kind"))
        for k in ("opening", "ending"):
            if s.get(k):
                used[k].add(s[k]["name"] if isinstance(s[k], dict) else s[k])
    for h in history(n + 1):
        for k in used:
            used[k].update(h.get("used", {}).get(k, []))
    return used


def _scripts(kind: str) -> dict:
    d = HERE / "templates" / kind
    out = {}
    for sub in sorted(p for p in d.iterdir() if p.is_dir()) if d.is_dir() else []:
        vs = sorted(int(p.stem[1:]) for p in sub.glob("v*.json") if p.stem[1:].isdigit())
        if vs:
            note = json.loads((sub / f"v{vs[-1]}.json").read_text(encoding="utf-8")).get("note", "")
            out[sub.name] = re.sub(r"\s+", " ", note)[:70]
    return out


def catalog() -> dict:
    return {"vision": {k: zh for k, (_, zh) in visions.VISIONS.items()},
            "moment": {k: zh for k, (_, zh) in moments.KINDS.items()},
            "opening": _scripts("opening"), "ending": _scripts("ending"),
            "girl": {c.name: c.zh for c in ca.CLIPS.values() if "female" in c.cast or c.name in ca.MOODS},
            "mood": list(ca.MOODS)}


def catalog_text(used: dict) -> str:
    cat = catalog()
    star = lambda kind, k: "★" if k in used.get(kind, set()) else ""   # noqa: E731
    lines = ["【想象画面 vision】（男生读完评论头顶云朵里的画面）"]
    lines += [f"- {k}{star('vision', k)}：{zh}" for k, zh in cat["vision"].items()]
    lines += ["【小动画 moment】（跟着歌词浮现在音轨上，3~8 秒）"]
    lines += [f"- {k}{star('moment', k)}：{zh}" for k, zh in cat["moment"].items()]
    lines += ["【开头小剧场 opening】（约 20 秒，最后接拨片开头：歌名 + 歌手）"]
    lines += [f"- {k}{star('opening', k)}：{n}" for k, n in cat["opening"].items()]
    lines += ["【结尾小剧场 ending】（约 10 秒，画面中间的小窗）"]
    lines += [f"- {k}{star('ending', k)}：{n}" for k, n in cat["ending"].items()]
    lines += ["【女生反应 girl】" + "、".join(cat["girl"]), "【男生情绪 mood】" + "、".join(cat["mood"])]
    return "\n".join(lines)


def knowledge_text(limit: int = 1500) -> str:
    """LLM Wiki 的结论标题 + 最新日报改进建议 + 热词：只给要点，省 token。"""
    parts = []
    fd = WIKI / "findings"
    if fd.is_dir():
        titles = [p.stem for p in sorted(fd.glob("*.md"), key=lambda q: q.stat().st_mtime, reverse=True)
                  if not re.search(r"cc-piano|帧|回归|预览|飞书|上限", p.stem)]
        parts.append("已验证的发现：" + "；".join(titles[:12]))
    rd = WORKFLOW / "reports" / "daily"
    reports = sorted(rd.glob("*.md")) if rd.is_dir() else []
    if reports:
        txt = reports[-1].read_text(encoding="utf-8")
        m = re.search(r"\*\*改进建议\*\*.*?\n(.*?)(?:\n\n|\Z)", txt, re.S)
        if m:
            parts.append("最新日报的建议：" + " ".join(re.sub(r"^-\s*", "", ln).strip() for ln in m.group(1).splitlines()))
    hw = WORKFLOW / "learn" / "hotwords.json"
    if hw.exists():
        parts.append("热门话题：" + "、".join(json.loads(hw.read_text(encoding="utf-8")).get("tags", [])))
    tax = WORKFLOW / "kb" / "taxonomy.json"                # 知识库里已有的叙事母题（workflow/kb/kb.py 归的类）
    if tax.exists():
        story = [k.split("/")[-1] for k, v in json.loads(tax.read_text(encoding="utf-8")).get("pages", {}).items() if v == "story"]
        if story:
            parts.append("知识库里已有的叙事母题：" + "、".join(story[:16]))
    return "\n".join(parts)[:limit]


# ====================================================================== 历史（每天尽量不重复）
HISTORY = OUT / "history.jsonl"


def history(n: int = 10) -> list[dict]:
    if not HISTORY.exists():
        return []
    rows = [json.loads(ln) for ln in HISTORY.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return rows[-n:]


def history_text() -> str:
    rows = history(10)
    if not rows:
        return "（还没有编过）"
    return "\n".join(f"- {r['date']}《{r['title']}》：{r.get('theme', '')}｜{r.get('logline', '')}｜开头 {r['used'].get('opening', [''])[0] if r['used'].get('opening') else ''}"
                     f"，结尾 {r['used'].get('ending', [''])[0] if r['used'].get('ending') else ''}" for r in rows)


def versions(stem: str) -> list[dict]:
    d = OUT / stem
    out = []
    for p in sorted(d.glob("v*.json"), key=lambda q: int(q.stem[1:]) if q.stem[1:].isdigit() else 0) if d.is_dir() else []:
        if p.stem[1:].isdigit():
            v = json.loads(p.read_text(encoding="utf-8"))
            out.append({"version": int(p.stem[1:]), "time": v.get("time"), "theme": v.get("theme"), "logline": v.get("logline"),
                        "applied": v.get("applied", False), "usage": v.get("usage")})
    return out


def load_version(stem: str, ver: int) -> dict:
    return json.loads((OUT / stem / f"v{int(ver)}.json").read_text(encoding="utf-8"))


# ====================================================================== 编剧
SYSTEM = """你是 cc-piano 的编剧。你只做一件事：为一条抖音「音轨拆解 + 读网易云评论」的像素小人视频编故事线。
不聊别的话题；用户说与编剧无关的话时，只回一句「这里只能编剧」，仍然按格式输出当前剧本。

视频结构（时间都是视频秒数）：
- 开头小剧场（0 ~ 开头秒数）：从【开头小剧场】里选一个，第一帧就是一条最戳人的评论（两秒内抓住人）。
- 中段：男生小人从「网易云评论」文件夹抽出评论读，读完头顶云朵里浮现【想象画面】；女生小人在左下角唱歌，读到评论时做一个【女生反应】。
  节奏要慢：3~5 条评论，每条占 10~14 秒，彼此不重叠；可以在合适的歌词处放 0~4 个【小动画】（3~8 秒），0~2 段「只听某一轨」（3~6 秒）。
- 尾声那句话：正片快结束时浮现，最多 20 字（可以是一条短评论原句，sub 写「—— 用户名」）。
- 结尾小剧场（最后约 10 秒）：从【结尾小剧场】里选一个，并写一句问观众的话（引导评论）。

规则：
1. 评论只能用给你的编号（c1、c2…），绝不改写、不编造评论；男生读的评论尽量选真实、有画面感、能连成一条故事线的。
2. 避开：死亡细节、轻生、重病、枪、暴力、案件、政治；也不要用涉及具体真人隐私的评论。
3. 画面 / 小动画 / 开头 / 结尾只能填目录里的名字；带 ★ 的最近用过，尽量换别的。目录里没有、但故事很需要的画面，
   写进 new_animations（一句话描述），对应位置的名字填 null。
4. 和【最近编过的故事】要不一样：换主题角度、换开头结尾、换画面。
5. 小动画、只听某一轨要卡在歌词或旋律变化处；时间在 [开头秒数+2, 总长-结尾秒数-4] 之内。
6. nodes 只列「重要动画节点」8~14 个（开头 2~4 个、中段每条评论 1~2 个、结尾 1~2 个），每个一句画面描述（40 字以内），
   用户只看这些节点的图和字，所以要具体、有画面。
7. 只输出一个 JSON（不要别的文字、不要代码块标记），格式：
{"theme":"一句话主题","logline":"一句话故事线（30 字内）",
 "nodes":[{"t":"0:00","part":"开头|中段|结尾","title":"节点名（10 字内）","text":"画面（40 字内）",
           "anim":{"type":"opening|vision|moment|girl|ending|new","name":"目录里的名字，或新动画一句话"},"comment":"c3 或 null"}],
 "plan":{"opening":{"scene":"开头名","comment":"c1"},
         "acts":[{"name":"幕名（6 字内）","from":秒,"to":秒,"comment":"c5","vision":"画面名或null","mood":"情绪","girl":"反应或null","solo":false}],
         "moments":[{"kind":"小动画名","from":秒,"to":秒}],
         "solos":[{"track":"vocals|piano|guitar|bass|drums|other","from":秒,"to":秒,"label":"只听人声"}],
         "finale":{"text":"尾声大字","sub":"—— 用户名"},
         "ending":{"scene":"结尾名","question":"问观众的话（25 字内）"},
         "douyin_title":"抖音标题（30 字内，带「Claude」）","description":"抖音文案（200 字内，结尾一个问题）","tags":["5 个以内，不带 #"]},
 "new_animations":["目录里没有、建议新做的画面"]}"""


def build_prompt(stem: str) -> tuple[str, dict]:
    """把素材压成一段文字（评论编号化）。返回 (用户消息, 编号 → 评论)。"""
    m = materials(stem)
    s = m["song"]
    use = [c for c in m["comments"] if c.get("use", True)]
    if len(use) < 3:
        raise ValueError("可用的评论不到 3 条：先「识别录屏评论」或手动粘贴几条")
    ids = {f"c{i + 1}": c for i, c in enumerate(use[:60])}
    used = recent_used()
    lyr = "\n".join(f"{_fmt(x['t'])} {x['text']}" for x in m["lyrics"]) or "（没有歌词）"
    mel = m["melody"]
    msg = (f"【歌】《{s['title']}》{s['artist']}，视频总长 {s['duration']} 秒，开头小剧场约 {s['intro']} 秒，"
           f"结尾小剧场约 {s['ending_seconds']} 秒，画面上的音轨：{'、'.join(ZH_TRACK.get(t, t) for t in s['tracks'] if t != 'mix')}\n\n"
           f"【歌词（视频时间）】\n{lyr}\n\n【旋律】速度 {mel['tempo']} BPM；每 6 秒：\n" + "\n".join(mel["segments"]) +
           "\n\n【评论】（点赞数｜作者｜原文）\n" +
           "\n".join(f"{k}｜{c.get('likes') or '-'}｜{c.get('user') or '-'}｜{c['text'][:160]}" for k, c in ids.items()) +
           f"\n\n【动画目录】\n{catalog_text(used)}\n\n【知识库要点】\n{knowledge_text()}\n\n【最近编过的故事】\n{history_text()}")
    return msg, ids


def _parse(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("模型没有给出 JSON 剧本：" + text[:200])
    return json.loads(t[a:b + 1])


def check(raw: dict, ids: dict, stem: str) -> dict:
    """检查、裁剪模型给的剧本：评论编号换回原文；名字不在目录里的移到 new_animations；时间夹在范围里。"""
    s = materials(stem)["song"]
    cat = catalog()
    dur, intro, end_s = float(s["duration"]), float(s["intro"]), float(s["ending_seconds"])
    lo, hi = intro + 2, dur - end_s - 4
    new = [str(x)[:60] for x in (raw.get("new_animations") or []) if str(x).strip()][:8]
    num = lambda v, d: max(lo, min(hi, float(v))) if isinstance(v, (int, float)) or re.match(r"^-?\d+(\.\d+)?$", str(v)) else d   # noqa: E731

    def com(cid):
        return ids.get(str(cid).strip()) if cid else None

    def name_in(kind, v):
        if v in (None, "", "null"):
            return None
        if v in cat[kind]:
            return v
        new.append(f"{kind}：{v}")
        return None
    plan = raw.get("plan") or {}
    op = plan.get("opening") or {}
    oc = com(op.get("comment"))
    opening = {"scene": name_in("opening", op.get("scene")) or next(iter(cat["opening"]), None),
               "comment": oc["text"] if oc else None, "user": oc.get("user") if oc else None}
    acts, t_prev = [], lo
    for a in (plan.get("acts") or [])[:5]:
        c = com(a.get("comment"))
        if not c:
            continue
        f = max(num(a.get("from"), t_prev), t_prev)
        to = min(num(a.get("to"), f + 12), hi)
        if to - f < 4:
            continue
        acts.append({"name": str(a.get("name") or "")[:6], "from": round(f, 1), "to": round(to, 1), "comment": c["text"],
                     "user": c.get("user"), "vision": name_in("vision", a.get("vision")),
                     "mood": a.get("mood") if a.get("mood") in cat["mood"] else "nostalgic",
                     "girl": a.get("girl") if a.get("girl") in cat["girl"] else None, "solo": bool(a.get("solo"))})
        t_prev = to + 1
    moms = []
    for m in (plan.get("moments") or [])[:4]:
        k = name_in("moment", m.get("kind"))
        f = num(m.get("from"), None)
        if k and f is not None:
            moms.append({"kind": k, "from": round(f, 1), "to": round(min(hi, max(f + 3, num(m.get("to"), f + 6))), 1)})
    solos = []
    for so in (plan.get("solos") or [])[:2]:
        tr = so.get("track")
        f = num(so.get("from"), None)
        if tr in ZH_TRACK and tr in (s["tracks"] or list(ZH_TRACK)) and f is not None:
            solos.append({"track": tr, "from": round(f, 1), "to": round(min(hi, max(f + 3, num(so.get("to"), f + 5))), 1),
                          "label": str(so.get("label") or f"只听{ZH_TRACK[tr]}")[:10]})
    fin = plan.get("finale") or {}
    en = plan.get("ending") or {}
    tags = [str(t).lstrip("#").replace(" ", "")[:20] for t in (plan.get("tags") or []) if str(t).strip()]
    tags = (["音轨拆解"] + [t for t in tags if t != "音轨拆解"])[:5]
    nodes = []
    for n in (raw.get("nodes") or [])[:16]:
        an = n.get("anim") or {}
        typ = an.get("type") if an.get("type") in ("opening", "vision", "moment", "girl", "ending", "new") else "new"
        nm = an.get("name")
        if typ != "new" and nm not in cat.get(typ, {}):
            typ, nm = "new", f"{nm}"
        c = com(n.get("comment"))
        nodes.append({"t": str(n.get("t") or "")[:6], "part": str(n.get("part") or "")[:4], "title": str(n.get("title") or "")[:12],
                      "text": str(n.get("text") or "")[:60], "anim": {"type": typ, "name": str(nm or "")[:60]},
                      "comment": c["text"] if c else None})
    return {"theme": str(raw.get("theme") or "")[:40], "logline": str(raw.get("logline") or "")[:60], "nodes": nodes,
            "plan": {"opening": opening, "acts": acts, "moments": moms, "solos": solos,
                     "finale": {"text": str(fin.get("text") or "")[:20], "sub": str(fin.get("sub") or "")[:40]},
                     "ending": {"scene": name_in("ending", en.get("scene")) or next(iter(cat["ending"]), None),
                                "question": str(en.get("question") or "")[:30]},
                     "douyin_title": str(plan.get("douyin_title") or "")[:30],
                     "description": str(plan.get("description") or "")[:600], "tags": tags},
            "new_animations": list(dict.fromkeys(new))[:10]}


def _save_version(stem: str, script: dict, convo: list[dict], usage: dict, ids: dict) -> int:
    d = OUT / stem
    d.mkdir(parents=True, exist_ok=True)
    vs = [int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit()]
    ver = max(vs) + 1 if vs else 1
    full = {**script, "time": datetime.now().isoformat(timespec="seconds"),
            "usage": usage, "convo": convo, "ids": {k: v["text"] for k, v in ids.items()}}
    (d / f"v{ver}.json").write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")
    if _studioDb:
        try:
            _studioDb.save_screenplay(stem, "standard", ver, full)
        except Exception:
            pass
    return ver


def generate(stem: str, pid: str | None = None, hint: str = "") -> dict:
    """编一版新的故事线：返回 {version, script, usage}。"""
    msg, ids = build_prompt(stem)
    if hint.strip():
        msg += f"\n\n【用户的想法】{hint.strip()[:500]}"
    text, usage = llm(SYSTEM, [{"role": "user", "content": msg}], pid)
    script = check(_parse(text), ids, stem)
    convo = [{"role": "user", "content": msg}, {"role": "assistant", "content": text}]
    ver = _save_version(stem, script, convo, usage, ids)
    return {"version": ver, "script": script, "usage": usage}


def refine(stem: str, ver: int, message: str, pid: str | None = None) -> dict:
    """在某一版上按用户的话改剧本（仍然只能编剧），存成新版本。"""
    old = load_version(stem, ver)
    msg, ids = build_prompt(stem)
    convo = old.get("convo") or [{"role": "user", "content": msg}]
    convo = convo[:1] + convo[-2:] if len(convo) > 3 else convo         # 只带素材 + 上一版，省 token
    if len(convo) == 1:
        convo.append({"role": "assistant", "content": json.dumps({k: old[k] for k in ("theme", "logline", "nodes")},
                                                                 ensure_ascii=False)})
    convo = convo + [{"role": "user", "content": "按下面的意见修改剧本，仍然只输出完整 JSON：" + message.strip()[:1000]}]
    text, usage = llm(SYSTEM, convo, pid)
    script = check(_parse(text), ids, stem)
    ver2 = _save_version(stem, script, convo + [{"role": "assistant", "content": text}], usage, ids)
    return {"version": ver2, "script": script, "usage": usage}


# ====================================================================== 套用到视频
def apply(stem: str, ver: int) -> dict:
    """把某一版剧本写进歌曲 json（先存历史版本，和分段修改同一套），记进编剧历史。"""
    import section_lib
    sc = load_version(stem, ver)
    p = sc["plan"]
    path = song_path(stem)
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    song = template_lib.resolve(json.loads(json.dumps(raw)))
    hist = section_lib._snapshot(stem, f"编剧 v{ver} 套用前")
    tracks = [t for t in (song.get("tracks_keep") or ["vocals"]) if t != "mix"] or ["vocals"]
    if p["opening"].get("scene"):
        op = {"name": p["opening"]["scene"]}
        if p["opening"].get("comment"):
            op["comment"] = p["opening"]["comment"]
        raw["opening"] = op
    acts = []
    for i, a in enumerate(p["acts"]):
        card = {"text": a["comment"], "track": tracks[i % len(tracks)], "mood": a["mood"], "solo": a["solo"]}
        if a.get("vision"):
            card["vision"] = a["vision"]
        if a.get("girl"):
            card["girl"] = a["girl"]
        acts.append({"name": a["name"], "from": a["from"], "to": a["to"], "cards": [card]})
    dur = float(song.get("duration", 96))
    end_s = float(song.get("ending_seconds", 10)) if song.get("ending") or p["ending"].get("scene") else 0
    story = {"acts": acts}
    if p["finale"].get("text"):
        story["finale"] = {"from": round(dur - end_s - 3.5, 1), "text": p["finale"]["text"], "sub": p["finale"].get("sub", "")}
    raw["story"] = story
    raw["moments"] = p["moments"]
    raw["solos"] = p["solos"]
    if p["ending"].get("scene"):
        import ending as ending_mod
        en = {"name": p["ending"]["scene"]}
        base = ending_mod.load_script({"name": en["name"]})
        if p["ending"].get("question") and "question" in base:
            en["question"] = p["ending"]["question"]
        raw["ending"] = en
    for k in ("douyin_title", "description"):
        if p.get(k):
            raw[k] = p[k]
    if p.get("tags"):
        raw["tags"] = p["tags"]
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    sc["applied"] = True
    (OUT / stem / f"v{int(ver)}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    hist_entry = {"date": datetime.now().strftime("%Y-%m-%d"), "stem": stem, "title": song.get("title"),
                  "theme": sc.get("theme"), "logline": sc.get("logline"),
                  "used": {"opening": [p["opening"].get("scene")], "ending": [p["ending"].get("scene")],
                           "vision": [a["vision"] for a in p["acts"] if a.get("vision")],
                           "moment": [m["kind"] for m in p["moments"]]}}
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(hist_entry, ensure_ascii=False) + "\n")
    if _studioDb:
        try:
            _studioDb.mark_screenplay_applied(stem, "standard", ver)
            _studioDb.append_screenplay_history(hist_entry)
        except Exception:
            pass
    return {"history": hist, "version": ver}


# ====================================================================== 节点配图（动画库里现成的预览）
def node_image(anim: dict) -> Path | None:
    typ, name = anim.get("type"), anim.get("name")
    if typ == "vision":
        p = ROOT / "assets" / "clawd" / "visions" / f"{name}.webp"
        return p if p.exists() else None
    if typ == "girl":
        p = ROOT / "assets" / "clawd" / "animations" / "female" / f"{name}.webp"
        if not p.exists():
            try:
                import anim_lib
                p = anim_lib.ensure_trimmed("female", name)
            except Exception:
                return None
        return p
    if typ == "moment":
        p = ROOT / "assets" / "clawd" / "moments" / f"{name}.png"
        if not p.exists() and name in moments.KINDS:
            p.parent.mkdir(parents=True, exist_ok=True)
            moments.KINDS[name][0](0.6, 3.0).save(p)
        return p if p.exists() else None
    if typ in ("opening", "ending"):
        d = ROOT / "assets" / "scenes" / typ
        vers = lambda q: int(q.stem.rsplit("_v", 1)[1]) if q.stem.rsplit("_v", 1)[1].isdigit() else 0   # noqa: E731
        cands = sorted(d.glob(f"{name}_v*.jpg"), key=vers) if d.is_dir() else []
        return cands[-1] if cands else None
    return None


# ====================================================================== 剧本导出成文字稿（给用户看 / 存进歌曲文件夹）
TYPE_ZH = {"opening": "开头小剧场", "vision": "想象画面", "moment": "小动画", "girl": "女生动作", "ending": "结尾小剧场", "new": "需新做"}


def script_md(stem: str, ver: int) -> str:
    """某一版剧本 → markdown：节点（画面 + 一句话）、每幕的评论原文、开头结尾、文案、需新做的动画。"""
    sc = load_version(stem, ver)
    p, song = sc["plan"], _song(stem)
    users = {c["text"]: c.get("user") for c in load_comments(stem)}
    who = lambda t: f"——{users[t]}" if users.get(t) else ""   # noqa: E731
    quote = lambda t: "> 「" + t.replace("\n", "\n> ") + "」" + who(t)   # noqa: E731   多行评论每行都留在引用块里
    out = [f"# 《{song.get('title', stem)}》剧本 v{ver}", "",
           f"- 主题：{sc.get('theme', '')}", f"- 故事线：{sc.get('logline', '')}",
           f"- 编剧：{(sc.get('usage') or {}).get('model', '')}，{sc.get('time', '')}；评论都是录屏原文", "",
           "## 重要动画节点", ""]
    for n in sc.get("nodes", []):
        a = n.get("anim") or {}
        out.append(f"**{n.get('t', '')}｜{n.get('part', '')}｜{n.get('title', '')}**  ")
        out.append(f"{n.get('text', '')}  ")
        out.append(f"动画：{TYPE_ZH.get(a.get('type'), a.get('type'))} · {a.get('name', '')}")
        if n.get("comment"):
            out.append("\n" + quote(n["comment"]))
        out.append("")
    op = p.get("opening") or {}
    out += ["## 开头", "", f"- 小剧场：{op.get('scene')}"]
    if op.get("comment"):
        out.append(f"- 第一帧评论：「{op['comment']}」{who(op['comment'])}")
    out += ["", "## 中段（男生回忆，评论在对应歌词处浮现）", ""]
    for a in p.get("acts", []):
        out.append(f"**{a['from']:.0f}–{a['to']:.0f} 秒｜{a['name']}**（情绪 {a['mood']}；云朵画面 {a.get('vision') or '—'}；"
                   f"女生 {a.get('girl') or '—'}{'；只听这一轨' if a.get('solo') else ''}）")
        out.append(quote(a["comment"]))
        out.append("")
    if p.get("moments"):
        out += ["小动画：" + "；".join(f"{m['kind']} {m['from']:.0f}–{m['to']:.0f} 秒" for m in p["moments"]), ""]
    if p.get("solos"):
        out += ["只听某一轨：" + "；".join(f"{s['label']} {s['from']:.0f}–{s['to']:.0f} 秒" for s in p["solos"]), ""]
    fin, en = p.get("finale") or {}, p.get("ending") or {}
    out += ["## 尾声与结尾", "", f"- 尾声大字：{fin.get('text', '')} {fin.get('sub', '')}",
            f"- 结尾小剧场：{en.get('scene')}", f"- 问观众：{en.get('question', '')}", "",
            "## 抖音文案", "", f"- 标题：{p.get('douyin_title', '')}", f"- 文案：{p.get('description', '')}",
            f"- 标签：{' '.join('#' + t for t in p.get('tags', []))}", ""]
    if sc.get("new_animations"):
        out += ["## 动画库里没有、建议新做", ""] + [f"- {x}" for x in sc["new_animations"]] + [""]
    return "\n".join(out)
