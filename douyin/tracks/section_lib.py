"""cc-piano「分段修改」的后台：把一首歌的视频按「开头 / 每条评论 / 每个小动画 / 只听某一轨 / 尾声 / 结尾 / 整体」分块，
每块可以单独聊天修改、单独预览，满意了再出整片（用户 2026-10-27 设计）。

- 聊天（A）：用户自己配置的大模型（和动画库同一套设置），只能改这一块的字段，方案经 clean() 检查裁剪后由用户「采用」。
- 交给 Claude（B）：后台 claude -p 在 tracks 目录里工作，可以新增想象画面 / 小动画 / 开头结尾脚本版本（不改已有的），
  最后写 result.json 给出这一块的新 JSON；改动前备份 tracks/*.py，改完 import 不通过就全部还原。
- 采用 = 歌曲 json 先存一份历史（tracks/songs/history/<歌>/v<N>.json），再改；开头 / 结尾存成新的脚本版本。旧版本都保留。
- 预览：build.py --range 只渲染这一块的几秒（带音乐，720p）；出整片：build.py --prepare。
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import anim_lib
import clawd_anim as ca
import ending
import moments
import opening
import template_lib
import visions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SONGS = HERE / "songs"
HIST = SONGS / "history"
sys.path.insert(0, str(ROOT / "data"))
try:
    import db as _studioDb
except ImportError:
    _studioDb = None
JOBS = ROOT / "output" / "sections"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
STEMS = ["vocals", "piano", "guitar", "bass", "drums", "other"]
ZH_TRACK = {"vocals": "人声", "piano": "钢琴", "guitar": "吉他", "bass": "贝斯", "drums": "鼓", "other": "其他"}


# ====================================================================== 歌曲和分块
def song_path(stem: str) -> Path:
    p = (SONGS / f"{stem}.json").resolve()
    if p.parent != SONGS.resolve() or not p.exists():
        raise FileNotFoundError(f"没有这首歌：{stem}")
    return p


def _raw(stem: str) -> dict:
    return json.loads(song_path(stem).read_text(encoding="utf-8-sig"))


def latest_video(stem: str) -> Path | None:
    """这首歌最近一次出的整片（待上传里 job.json 指向这个歌曲文件的、最新的那个文件夹）。"""
    import storage
    target = str(song_path(stem))
    best = None
    for job in storage.deliver_dir().glob("*/job.json"):
        try:
            if json.loads(job.read_text(encoding="utf-8")).get("song") == target and (job.parent / "video.mp4").exists():
                if best is None or job.parent.name > best.name:
                    best = job.parent
        except (OSError, ValueError):
            continue
    return best / "video.mp4" if best else None


def list_songs(media_url) -> list[dict]:
    out = []
    for p in sorted(SONGS.glob("*.json"), key=lambda q: q.stat().st_mtime, reverse=True):
        try:
            raw = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        if not raw.get("story"):
            continue
        cover = Path(raw.get("final_image") or "")
        local = JOBS / p.stem / "cover.jpg"                  # 封面可能在 douyin 目录外（网页读不到）：复制一份小图
        if cover.is_file() and (not local.exists() or local.stat().st_mtime < cover.stat().st_mtime):
            from PIL import Image
            local.parent.mkdir(parents=True, exist_ok=True)
            Image.open(cover).convert("RGB").resize((96, 96)).save(local, quality=88)
        out.append({"stem": p.stem, "title": raw.get("title", p.stem), "artist": raw.get("artist", ""),
                    "cover": media_url(local) if local.exists() else None,
                    "versions": _hist_versions(p.stem)})
    return out


def sections(stem: str) -> dict:
    """{song: {...}, sections: [{id, kind, title, sub, range, data}]}，按时间排好。"""
    raw = _raw(stem)
    song = template_lib.resolve(json.loads(json.dumps(raw)))
    dur = float(song.get("duration", 96))
    intro = float(song.get("intro", 20))
    end_s = float(song.get("ending_seconds", 10)) if song.get("ending") else 0.0
    out = []
    if song.get("opening"):
        sc = opening.load_script(song["opening"])
        spec = song["opening"] if isinstance(song["opening"], dict) else {"name": song["opening"]}
        out.append({"id": "opening", "kind": "opening", "title": f"开头小剧场 · {spec.get('name')}",
                    "sub": sc.get("comment", ""), "range": [0.0, intro], "data": sc})
    for i, act in enumerate(song.get("story", {}).get("acts", [])):
        for j, c in enumerate(act.get("cards", [])):
            data = {"name": act.get("name", ""), "from": act.get("from"), "to": act.get("to"), **c}
            out.append({"id": f"card:{i}:{j}", "kind": "card", "title": f"评论 · {act.get('name', '')}",
                        "sub": c.get("text", ""), "range": [float(act["from"]) - 1, float(act["to"]) + 2.5], "data": data})
    for i, m in enumerate(song.get("moments", [])):
        zh = moments.KINDS.get(m.get("kind"), (None, m.get("kind")))[1]
        out.append({"id": f"moment:{i}", "kind": "moment", "title": "小动画", "sub": zh,
                    "range": [float(m["from"]) - 0.5, float(m["to"]) + 0.5], "data": m})
    for i, s in enumerate(song.get("solos", [])):
        out.append({"id": f"solo:{i}", "kind": "solo", "title": "只听某一轨", "sub": s.get("label", ""),
                    "range": [float(s["from"]) - 1, float(s["to"]) + 1], "data": s})
    fin = song.get("story", {}).get("finale")
    if fin:
        out.append({"id": "finale", "kind": "finale", "title": "尾声那句话", "sub": fin.get("text", ""),
                    "range": [float(fin["from"]) - 0.5, dur - end_s], "data": fin})
    if song.get("ending"):
        sc = ending.load_script(song["ending"])
        spec = song["ending"] if isinstance(song["ending"], dict) else {"name": song["ending"]}
        out.append({"id": "ending", "kind": "ending", "title": f"结尾小剧场 · {spec.get('name')}",
                    "sub": sc.get("question", "") or sc.get("note", "")[:40], "range": [dur - end_s - 0.5, dur],
                    "data": sc})
    out.sort(key=lambda s: s["range"][0])
    out.append({"id": "song", "kind": "song", "title": "整体", "sub": "标题、文案、话题、歌词字号、节奏、显示哪几条音轨",
                "range": None, "data": {k: song.get(k) for k in ("douyin_title", "description", "tags", "lyric_size",
                                                                 "pace", "tracks_keep")}})
    lv = latest_video(stem)
    return {"song": {"stem": stem, "title": song.get("title"), "artist": song.get("artist"), "duration": dur,
                     "intro": intro, "video": str(lv) if lv else None, "versions": _hist_versions(stem)},
            "sections": out}


def find(stem: str, sid: str) -> dict:
    for s in sections(stem)["sections"]:
        if s["id"] == sid:
            return s
    raise KeyError(f"没有这一块：{sid}")


def thumb(video: Path, t: float, out: Path) -> Path | None:
    """整片里第 t 秒的一帧（缓存）。"""
    if out.exists() and out.stat().st_mtime >= video.stat().st_mtime:
        return out
    import imageio_ffmpeg
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}",
                        "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(out)],
                       capture_output=True)
    return out if r.returncode == 0 and out.exists() else None


# ====================================================================== 字段说明 + 检查（模型和 Claude 给的 JSON 都不可信）
def _num(v, lo, hi, default):
    try:
        return round(min(hi, max(lo, float(v))), 2)
    except (TypeError, ValueError):
        return default


def guide(kind: str, song: dict) -> str:
    tracks = song.get("tracks_keep") or STEMS
    vis = {k: zh for k, (_, zh) in visions.VISIONS.items()}
    mk = {k: zh for k, (_, zh) in moments.KINDS.items()}
    if kind == "card":
        return ("这是视频中段的一条网易云评论：男生小人从文件夹抽出这条评论读，读完头顶冒出想象云朵（vision），女生小人在左下角唱歌，"
                "这时对评论做一个反应（girl）。字段：\n"
                "- text：评论原文（必须是真实评论原句，不能编、不能改写）\n"
                f"- track：评论卡片读完后飞到哪条音轨旁，可选 {tracks}\n"
                f"- mood：男生读完的情绪，可选 {list(ca.MOODS)}\n"
                f"- vision：想象云朵里的画面，可选 {json.dumps(vis, ensure_ascii=False)}（null 表示不冒云朵）\n"
                f"- girl：女生的反应动画，可选 {list(ca.CLIPS)}（null 表示不反应）\n"
                "- solo：true 时这条评论在画面中间单独读（独白），false 是普通读法\n"
                "- from / to：这一幕在视频里的开始和结束秒数（至少 4 秒）\n- name：这一幕的名字（几个字）")
    if kind == "moment":
        return ("这是跟着歌词出现的小动画，浮现在音轨区域，慢慢出现、停留、消失。字段：\n"
                f"- kind：哪个动画，可选 {json.dumps(mk, ensure_ascii=False)}\n- from / to：出现和消失的视频秒数（3~12 秒）")
    if kind == "solo":
        return ("这是「只听某一轨」：这几秒音乐换成这一条分离音轨，画面上这条轨亮起。字段：\n"
                f"- track：可选 {tracks}\n- from / to：视频秒数（3~10 秒）\n- label：顶部小牌子的字，比如「只听人声」")
    if kind == "finale":
        return ("这是尾声那句话：正片快结束时在画面中间浮现，一直到结尾小剧场之前。字段：\n"
                "- text：大字（20 字以内）\n- sub：下面一行小字（比如评论作者「—— 某某」）\n- from：出现的视频秒数")
    if kind == "song":
        return ("这是整首视频的整体设置。字段：\n- douyin_title：抖音标题（30 字以内）\n- description：抖音文案（600 字以内）\n"
                "- tags：话题，最多 5 个，不带 #\n- lyric_size：歌词字号 32~72\n- pace：读评论的节奏，越大越慢（0.8~2.5）\n"
                f"- tracks_keep：画面上显示哪几条音轨（2~4 条），可选 {STEMS}")
    return anim_lib.GUIDE.get(kind, "") + ("\n（这首歌用的是 " + str(song.get(kind)) + " 这个脚本，字段以当前 JSON 为准，"
                                           "beats 里每一段是占整段的比例 [开始, 结束]）")


def clean(kind: str, data: dict, base: dict, song: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("方案不是 JSON 对象")
    dur = float(song.get("duration", 96))
    intro = float(song.get("intro", 20))
    end_s = float(song.get("ending_seconds", 10)) if song.get("ending") else 0.0
    lo, hi = intro + 1, dur - end_s
    tracks = song.get("tracks_keep") or STEMS
    get = lambda k: data.get(k, base.get(k))             # noqa: E731

    def span(min_len, max_len):
        a = _num(get("from"), lo, hi - min_len, base.get("from"))
        b = _num(get("to"), a + min_len, min(hi, a + max_len), base.get("to"))
        return a, b
    if kind == "card":
        a, b = span(4, 20)
        text = str(get("text") or "").strip()[:150]
        if len(text) < 2:
            raise ValueError("评论原文不能为空")
        return {"name": str(get("name") or "")[:8], "from": a, "to": b, "text": text,
                "track": get("track") if get("track") in tracks else base.get("track", tracks[0]),
                "mood": get("mood") if get("mood") in ca.MOODS else base.get("mood", "nostalgic"),
                "vision": get("vision") if get("vision") in visions.VISIONS else None,
                "girl": get("girl") if get("girl") in ca.CLIPS else None, "solo": bool(get("solo"))}
    if kind == "moment":
        a, b = span(3, 12)
        return {"kind": get("kind") if get("kind") in moments.KINDS else base["kind"], "from": a, "to": b}
    if kind == "solo":
        a, b = span(3, 10)
        tr = get("track") if get("track") in tracks else base["track"]
        return {"track": tr, "from": a, "to": b, "label": str(get("label") or f"只听{ZH_TRACK.get(tr, tr)}")[:10]}
    if kind == "finale":
        return {"from": _num(get("from"), lo, hi - 1.5, base.get("from")), "text": str(get("text") or "")[:24],
                "sub": str(get("sub") or "")[:40]}
    if kind == "song":
        tags = [str(t).lstrip("#").replace(" ", "")[:20] for t in (get("tags") or []) if str(t).strip()][:5]
        keep = [t for t in (get("tracks_keep") or []) if t in STEMS][:4]
        return {"douyin_title": str(get("douyin_title") or "")[:30], "description": str(get("description") or "")[:600],
                "tags": tags, "lyric_size": int(_num(get("lyric_size") or 40, 32, 72, 40)),
                "pace": _num(get("pace") or 1.0, 0.8, 2.5, 1.0),
                "tracks_keep": keep if len(keep) >= 2 else base.get("tracks_keep")}
    if kind in ("opening", "ending"):
        out = anim_lib.clean(kind, data, base)
        out["note"] = str(data.get("note") or base.get("note", ""))[:300]
        return out
    raise ValueError(f"不认识的分块：{kind}")


# ====================================================================== 采用（存版本）
def _hist_versions(stem: str) -> list[int]:
    d = HIST / stem
    return sorted(int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit()) if d.is_dir() else []


def _snapshot(stem: str, note: str) -> int:
    vs = _hist_versions(stem)
    ver = (vs[-1] + 1) if vs else 1
    (HIST / stem).mkdir(parents=True, exist_ok=True)
    sp = song_path(stem)
    shutil.copy(sp, HIST / stem / f"v{ver}.json")
    if _studioDb:
        try:
            _studioDb.save_song_snapshot(stem, ver, json.loads(sp.read_text(encoding="utf-8-sig")), note)
        except Exception:
            pass
    with open(HIST / stem / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "saved_before": ver, "note": note},
                           ensure_ascii=False) + "\n")
    return ver


def apply(stem: str, sid: str, data: dict, via: str = "api") -> dict:
    """采用一个方案：先把当前歌曲 json 存成历史版本，再改这一块。返回 {history, data}。"""
    raw = _raw(stem)
    song = template_lib.resolve(json.loads(json.dumps(raw)))
    sec = find(stem, sid)
    new = clean(sec["kind"], data, sec["data"], song)
    hist = _snapshot(stem, f"{via}：改 {sid}")
    kind = sec["kind"]
    if kind in ("opening", "ending"):
        spec = song[kind] if isinstance(song[kind], dict) else {"name": song[kind]}
        new["note"] = (new.get("note") or "") + f"（{song.get('title')} 分段修改，{datetime.now():%m-%d %H:%M}）"
        ver = anim_lib.save(kind, spec["name"], new)
        raw[kind] = {"name": spec["name"], "version": ver}
    elif kind == "card":
        _, i, j = sid.split(":")
        act = raw["story"]["acts"][int(i)]
        act["name"], act["from"], act["to"] = new.pop("name") or act.get("name", ""), new.pop("from"), new.pop("to")
        card = {k: v for k, v in new.items() if v not in (None, False) or k == "solo"}
        act["cards"][int(j)] = card
    elif kind in ("moment", "solo"):
        key = "moments" if kind == "moment" else "solos"
        raw[key][int(sid.split(":")[1])] = new
    elif kind == "finale":
        raw["story"]["finale"] = new
    elif kind == "song":
        raw.update({k: v for k, v in new.items() if v is not None})
    song_path(stem).write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"history": hist, "data": new}


def restore(stem: str, ver: int) -> int:
    """回到某个历史版本（当前的也先存一份，所以随时能再回来）。"""
    src = HIST / stem / f"v{int(ver)}.json"
    if not src.exists():
        raise FileNotFoundError(f"没有 v{ver}")
    saved = _snapshot(stem, f"回到 v{ver} 之前")
    shutil.copy(src, song_path(stem))
    return saved


# ====================================================================== A：用户自己的大模型
def chat(stem: str, sid: str, message: str, history: list[dict]) -> dict:
    import re
    raw = _raw(stem)
    song = template_lib.resolve(json.loads(json.dumps(raw)))
    sec = find(stem, sid)
    system = (f"你是 cc-piano 的视频分段设计助手。视频是《{song.get('title')}》（{song.get('artist')}）的音轨拆解 + 读网易云评论，"
              f"总长 {song.get('duration')} 秒，开头小剧场约 {song.get('intro')} 秒。用户现在只想改其中一块：{sec['title']}"
              f"（{sec['sub'][:40]}）。只能改下面说明里的字段，其他块不要动。\n"
              "回答格式：先用一两句中文说明你打算怎么改，然后给一个 ```json 代码块，里面是这一块完整的新 JSON（在当前 JSON 基础上修改）。"
              "如果用户只是在提问、不需要改，就只回答文字。如果要做的东西靠改字段做不到（比如要一个新画面、新动作），"
              "就直接告诉用户「这个需要点『交给 Claude』」，不要硬凑。\n\n" + guide(sec["kind"], song) +
              "\n\n当前 JSON：\n```json\n" + json.dumps(sec["data"], ensure_ascii=False, indent=1) + "\n```")
    msgs = [{"role": "system", "content": system}]
    for h in history[-8:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": h["content"][:4000]})
    msgs.append({"role": "user", "content": message[:2000]})
    text = anim_lib.llm_complete(msgs)
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    proposal, err = None, None
    if m:
        try:
            proposal = clean(sec["kind"], json.loads(m.group(1)), sec["data"], song)
        except (ValueError, json.JSONDecodeError) as e:
            err = str(e)
    reply = re.sub(r"```(?:json)?\s*\{.*\}\s*```", "", text, flags=re.S).strip() or "方案在下面，看看要不要采用。"
    if err:
        reply += f"\n（方案没通过检查：{err}）"
    return {"reply": reply, "proposal": proposal}


# ====================================================================== B：交给 Claude（后台 claude -p）
CLAUDE_PROMPT = """你在 cc-piano 项目的 tracks 目录里（像素小人 CC 的音轨拆解视频生成器）。用户要改视频里的一块，详细要求在
{job}\\request.md，先读它，再读里面提到的代码文件。

规则：
1. 只为这一块工作。能靠改这一块的 JSON 字段做到的，就只改 JSON。
2. 需要新画面 / 新动作时可以写代码，但只能「新增」：
   - 想象云朵画面：在 visions.py 里新增函数，并登记到 VISIONS 字典；
   - 跟歌词走的小动画：在 moments.py 里新增函数，并登记到 KINDS 字典；
   - 开头 / 结尾小剧场：在 opening.py / ending.py 里新增场景类并登记到 SCENES，不要改已有场景的画法；
   - 小人的新手势 / 新表情：在 clawd_anim.py 里新增选项（elif 分支），不要改已有选项的画法。
   不要修改、删除已有的函数和已有的画法，其他歌曲的视频必须和原来一模一样。
3. 评论原文必须是真实评论，不能编造。
4. 写完后用 Read 检查一遍语法（缩进、括号）。
5. 最后写 {job}\\result.json：{{"data": 这一块完整的新 JSON, "summary": "用一两句中文告诉用户改了什么"}}。
   data 的字段说明见 request.md。如果做不到，data 写当前 JSON 原样，summary 说明原因。
"""


def claude_job(stem: str, sid: str, message: str, progress=None) -> dict:
    """在后台跑 claude -p 改这一块；import 检查不过就还原代码。返回 {summary, data, cost_usd, history}。"""
    raw = _raw(stem)
    song = template_lib.resolve(json.loads(json.dumps(raw)))
    sec = find(stem, sid)
    job = JOBS / stem / f"claude_{datetime.now():%Y%m%d_%H%M%S}"
    (job / "backup").mkdir(parents=True, exist_ok=True)
    for p in HERE.glob("*.py"):                                  # 改代码前备份，失败时还原
        shutil.copy(p, job / "backup" / p.name)
    (job / "request.md").write_text(
        f"# 要改的一块\n\n视频：《{song.get('title')}》{song.get('artist')}，总长 {song.get('duration')} 秒\n\n"
        f"这一块：{sec['title']}（id {sid}，视频时间 {sec['range']}）\n\n## 用户的要求\n\n{message}\n\n"
        f"## 字段说明\n\n{guide(sec['kind'], song)}\n\n## 当前 JSON\n\n```json\n"
        f"{json.dumps(sec['data'], ensure_ascii=False, indent=1)}\n```\n\n"
        "## 相关代码\n\n- 想象画面：visions.py（VISIONS）\n- 小动画：moments.py（KINDS）\n"
        "- 开头小剧场：opening.py（SCENES、Office / ChatOffice）\n- 结尾小剧场：ending.py（SCENES、Home / Crossing）\n"
        "- 小人画法：clawd_anim.py（Pose、CLIPS、LOOKS）\n- 场景道具：scenes.py\n", encoding="utf-8")
    if progress:
        progress(0.05, "Claude 正在看这一块")
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "& claude -p $env:CC_SECTION_PROMPT --allowedTools Read Write Edit Glob Grep "
                        "--permission-mode acceptEdits --setting-sources user --strict-mcp-config "
                        f"--add-dir '{job}' --output-format json --max-turns 60"],
                       cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400,
                       env={**os.environ, "CC_SECTION_PROMPT": CLAUDE_PROMPT.replace("{job}", str(job))})
    (job / "claude_out.json").write_text(r.stdout or "", encoding="utf-8")
    try:
        cost = float(json.loads(r.stdout or "{}").get("total_cost_usd") or json.loads(r.stdout or "{}").get("cost_usd") or 0)
    except ValueError:
        cost = 0.0
    changed = [p.name for p in HERE.glob("*.py")
               if not (job / "backup" / p.name).exists() or (job / "backup" / p.name).read_bytes() != p.read_bytes()]
    chk = subprocess.run([str(PY), "-c", "import visions, moments, opening, ending, clawd_anim, scenes, build"],
                         cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if chk.returncode != 0:                                      # 代码坏了：全部还原
        for name in changed:
            b = job / "backup" / name
            if b.exists():
                shutil.copy(b, HERE / name)
            else:
                (HERE / name).unlink(missing_ok=True)
        raise RuntimeError("Claude 改的代码没通过检查，已经全部还原：" + (chk.stderr or "")[-300:])
    res_file = job / "result.json"
    if not res_file.exists():
        raise RuntimeError("Claude 没写出 result.json：" + (r.stderr or r.stdout or "")[-300:])
    res = json.loads(res_file.read_text(encoding="utf-8-sig"))
    if changed:                                                  # 新代码要在新进程里生效：本进程重新加载
        import importlib
        for mod in (ca, visions, moments, opening, ending):
            importlib.reload(mod)
    saved = apply(stem, sid, res.get("data") or {}, via="claude")
    return {"summary": str(res.get("summary") or "改好了")[:500], "data": saved["data"], "history": saved["history"],
            "cost_usd": round(cost, 2), "changed": changed, "job": str(job)}


# ====================================================================== 预览这一块 / 出整片
def run_build(stem: str, extra: list[str], progress=None) -> dict:
    cmd = [str(PY), str(HERE / "build.py"), str(song_path(stem)), "--json-progress", *extra]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    result, tail = None, []
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("@@"):
            ev = json.loads(line[2:])
            if progress and ev.get("pct") is not None:
                progress(ev["pct"], ev.get("msg", ""))
            if ev["stage"] == "done":
                result = ev.get("result")
        elif line:
            tail = (tail + [line])[-12:]
    proc.wait()
    if proc.returncode != 0 or not result:
        raise RuntimeError("渲染失败：" + " / ".join(tail[-4:]))
    return result


def preview(stem: str, sid: str, progress=None) -> dict:
    sec = find(stem, sid)
    if not sec["range"]:
        raise ValueError("「整体」没有单独的预览，直接出整片看")
    a, b = sec["range"]
    res = run_build(stem, ["--range", f"{max(0.0, a):.2f}", f"{b:.2f}", "--fps", "30"], progress)
    out = JOBS / stem / "previews" / f"{sid.replace(':', '_')}_{datetime.now():%H%M%S}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(res["video"], out)
    return {"video": str(out), "range": res.get("range")}


def full_build(stem: str, progress=None) -> dict:
    return run_build(stem, ["--prepare"], progress)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="分段修改（调试用）")
    ap.add_argument("stem")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    for s in sections(a.stem)["sections"]:
        print(f"{s['id']:12} {s['title']:16} {s['range']}  {s['sub'][:30]}")
