"""「分段修改」里除了音轨评论故事以外的视频（用户 2026-10-30：以后所有视频都进分段修改，关键节点也能编辑；钢琴下落音符不分段）。

作品 = 待上传/<文件夹>（job.json 的 kind 不是钢琴 / 音轨 / 导入），分段修改页里用文件夹名当 stem。两种适配：
- 手绘歌词动画（job.json 的 source 指向 handdrawn/songs/<歌>）：一镜一块（= 关键节点），能改节点名、画面描述、开始时间（吸附节拍）、
  字幕位置、转场；改的是 film_data.js（整片的镜头表）。「交给 Claude」可以重画这一镜（改 scenes.js / film.js 里这一镜的画法，
  只许新增函数、不许改别的镜头），改完 node --check + 无头渲染检查，不过就还原。预览 = 只渲染这一镜（缩成 720p，带原声）；
  出整片 = handdrawn/film_build.py（整片 + 分层剪辑工程）。每次改之前，film_data.js / scenes.js / film.js 存一份历史版本。
- 其他（3D MV、以后的新类型）：分段来自 job.json 的 sections（[{title, from, to, note}]），没有就按画面切换点自动切；
  能改每段的名字和备注、整体的标题文案话题；预览是原片里的这一段。以后的新流程出片时在 job.json 写 kind 和 sections 就会出现在这里。
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import anim_lib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT / "piano") not in sys.path:
    sys.path.append(str(ROOT / "piano"))                          # storage（保存位置）；放在最后，不遮住 tracks 里同名的模块
HAND = ROOT / "handdrawn"
JOBS = ROOT / "output" / "sections"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
ENV_SH = Path(r"D:\cc-engine\filmlab\env.sh").as_posix()
PREVIEW_TMP = Path(r"D:\cc-engine\.tmp\handdrawn\preview")
NOT_FILM = (None, "piano", "tracks", "intro", "import")
SUB_ZH = {"top": "上方", "bottom": "下方", "left": "左侧", "right": "右侧", "top_left": "左上", "top_right": "右上",
          "bottom_left": "左下", "bottom_right": "右下", "center": "中间"}
TR_ZH = {"open": "撕开黑场", "page": "翻页 / 日历页扫过", "lid": "盖子砸下", "flash": "白闪", "mask": "面具翻面", "dark": "关灯",
         "rain": "雨刷", "bubbles": "气泡砸满屏", "rewind": "倒带", "swing": "甩镜", "crack": "玻璃碎裂", "ding": "叮一声",
         "masks": "面具掉落", "torch": "手电光圈", "leaf": "叶子扫过", "confetti": "彩纸炸开", "cable": "耳机线拉过", "iris": "圆形开合",
         "doors": "车门开合", "burn": "火烧穿", "smoke": "烟雾", "screen": "屏幕推进", "stars": "星光闪", "brush": "笔刷擦过"}


# ====================================================================== 作品
def deliver() -> Path:
    import storage
    return storage.deliver_dir()


def _job(folder: Path) -> dict:
    return json.loads((folder / "job.json").read_text(encoding="utf-8"))


def work(stem: str) -> Path:
    d = (deliver() / stem).resolve()
    if d.parent != deliver().resolve() or not (d / "job.json").exists():
        raise FileNotFoundError(f"没有这个作品：{stem}")
    return d


def is_work(stem: str) -> bool:
    try:
        return _job(work(stem)).get("kind") not in NOT_FILM
    except (FileNotFoundError, OSError, ValueError):
        return False


def hd_song(job: dict) -> str | None:
    """手绘片：job.json 的 source 里写的 handdrawn/songs/<歌>。"""
    m = re.search(r"handdrawn/songs/([^（(\s/]+)", str(job.get("source") or ""))
    return m.group(1) if m and (HAND / "songs" / m.group(1) / "film_data.js").exists() else None


def kind_zh(job: dict) -> str:
    if hd_song(job):
        return "手绘动画"
    if "cinematic" in str(job.get("source") or ""):
        return "3D MV"
    return {"lyricfilm": "动画"}.get(job.get("kind"), str(job.get("kind") or "视频"))


def list_works(media_url) -> list[dict]:
    out = []
    for jf in sorted(deliver().glob("*/job.json"), key=lambda p: p.parent.name, reverse=True):
        try:
            job = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if job.get("kind") in NOT_FILM or not (jf.parent / "video.mp4").exists():
            continue
        cover = jf.parent / "cover.jpg"
        out.append({"stem": jf.parent.name, "title": job.get("title") or jf.parent.name, "artist": job.get("artist", ""),
                    "cover": media_url(cover) if cover.exists() else None, "kind": kind_zh(job), "versions": hist_versions(jf.parent.name)})
    return out


# ====================================================================== 历史版本（改之前存一份）
def _hist_dir(stem: str) -> Path:
    return JOBS / stem / "history"


def _hist_files(stem: str) -> list[Path]:
    w = work(stem)
    song = hd_song(_job(w))
    files = [w / "job.json", w / "publish.md"]
    if song:
        files += [HAND / "songs" / song / f for f in ("film_data.js", "scenes.js", "film.js")]
    return [f for f in files if f.exists()]


def hist_versions(stem: str) -> list[int]:
    d = _hist_dir(stem)
    return sorted(int(p.name[1:]) for p in d.glob("v*") if p.is_dir() and p.name[1:].isdigit()) if d.is_dir() else []


def snapshot(stem: str, note: str) -> int:
    vs = hist_versions(stem)
    ver = (vs[-1] + 1) if vs else 1
    dst = _hist_dir(stem) / f"v{ver}"
    dst.mkdir(parents=True)
    for f in _hist_files(stem):
        shutil.copy2(f, dst / f.name)
    with open(_hist_dir(stem) / "log.jsonl", "a", encoding="utf-8") as fp:
        fp.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "saved_before": ver, "note": note}, ensure_ascii=False) + "\n")
    return ver


def restore(stem: str, ver: int) -> int:
    src = _hist_dir(stem) / f"v{int(ver)}"
    if not src.is_dir():
        raise FileNotFoundError(f"没有 v{ver}")
    saved = snapshot(stem, f"回到 v{ver} 之前")
    for f in _hist_files(stem):
        if (src / f.name).exists():
            shutil.copy2(src / f.name, f)
    return saved


# ====================================================================== 手绘片的数据
def load_film(song: str) -> tuple[str, dict]:
    s = (HAND / "songs" / song / "film_data.js").read_text(encoding="utf-8")
    return s[: s.index("{")], json.loads(s[s.index("{"): s.rindex("}") + 1])


def save_film(song: str, head: str, d: dict) -> None:
    (HAND / "songs" / song / "film_data.js").write_text(head + json.dumps(d, ensure_ascii=False) + ";\n", encoding="utf-8")


def transitions(song: str) -> list[str]:
    """这首歌的 film.js 里画了哪些转场（type === '…'）。"""
    js = (HAND / "songs" / song / "film.js").read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"type === '([a-z]+)'", js)))
    return names + (["brush"] if "brushWipe" in js and "brush" not in names else [])


def _pictures(job: dict, d: dict) -> list[str]:
    """每镜的画面描述：film_data 里有就用；没有就从剧本 lyric_v<N>.json 里按顺序取（镜头数对得上时）。"""
    if all(s.get("picture") for s in d["shots"]):
        return [s["picture"] for s in d["shots"]]
    out = [s.get("picture") or "" for s in d["shots"]]
    m = re.search(r"tracks/songs/(.+?)\.json", str(job.get("song") or ""))
    wdir = ROOT / "output" / "writer" / (m.group(1) if m else "")
    vs = sorted(wdir.glob("lyric_v*.json"), key=lambda p: int(p.stem[7:]) if p.stem[7:].isdigit() else 0)
    if vs:
        sc = json.loads(vs[-1].read_text(encoding="utf-8"))
        if len(sc.get("shots", [])) == len(d["shots"]):
            out = [o or s.get("picture", "") for o, s in zip(out, sc["shots"])]
    return [o or s.get("zh", "") for o, s in zip(out, d["shots"])]


def _line_text(d: dict, s: dict) -> str:
    a, b = (s.get("lines") or [0, 0])[:2]
    if not (0 < a < 999):
        return "（前奏 / 尾奏）"
    return " / ".join(d["lines"][i - 1]["text"].replace("，", " · ") for i in range(a, min(b, len(d["lines"])) + 1) if 0 < i <= len(d["lines"]))


SHOT_FIELDS = lambda trs: [   # noqa: E731
    {"key": "zh", "label": "节点名", "type": "text", "max": 24},
    {"key": "picture", "label": "画面描述（改了它，点「交给 Claude」重画这一镜）", "type": "textarea", "max": 200},
    {"key": "from", "label": "开始时间（秒，自动吸附到最近的节拍）", "type": "number", "step": .01},
    {"key": "sub", "label": "字幕位置", "type": "select", "options": [[k, v] for k, v in SUB_ZH.items()]},
    {"key": "tr", "label": "进入这一镜的转场", "type": "select", "options": [[t, TR_ZH.get(t, t)] for t in trs]}]
SONG_FIELDS = [{"key": "douyin_title", "label": "抖音标题", "type": "text", "max": 30},
               {"key": "description", "label": "抖音文案", "type": "textarea", "max": 600},
               {"key": "tags", "label": "话题（空格分开，最多 5 个）", "type": "tags"}]
SEG_FIELDS = [{"key": "title", "label": "这一段的名字", "type": "text", "max": 24},
              {"key": "note", "label": "备注 / 想怎么改", "type": "textarea", "max": 300}]


# ====================================================================== 分块
def sections(stem: str) -> dict:
    w = work(stem)
    job = _job(w)
    song = hd_song(job)
    blocks = []
    if song:
        _, d = load_film(song)
        pics, trs = _pictures(job, d), transitions(song)
        for i, s in enumerate(d["shots"]):
            data = {"zh": s.get("zh", ""), "picture": pics[i], "from": s["from"], "sub": s.get("sub", "bottom"), "tr": s.get("tr", "")}
            blocks.append({"id": f"shot:{i}", "kind": "shot", "title": f"第 {i + 1} 镜 · {s.get('zh', '')[:12]}", "sub": _line_text(d, s),
                           "range": [s["from"], s["to"]], "data": data, "fields": SHOT_FIELDS(trs)})
        dur, mode = d["dur"], "handdrawn"
    else:
        dur = _duration(w / "video.mp4")
        for i, s in enumerate(_segments(stem, w, job, dur)):
            blocks.append({"id": f"seg:{i}", "kind": "seg", "title": s["title"] or f"第 {i + 1} 段", "sub": s.get("note", ""),
                           "range": [s["from"], s["to"]], "data": {"title": s["title"], "note": s.get("note", "")}, "fields": SEG_FIELDS})
        mode = "generic"
    blocks.append({"id": "song", "kind": "song", "title": "整体", "sub": "抖音标题、文案、话题", "range": None,
                   "data": {k: job.get(k) for k in ("douyin_title", "description", "tags")}, "fields": SONG_FIELDS})
    return {"song": {"stem": stem, "title": job.get("title") or stem, "artist": job.get("artist", ""), "duration": dur, "intro": 0.0,
                     "video": str(w / "video.mp4"), "versions": hist_versions(stem), "kind": kind_zh(job), "mode": mode,
                     "can_build": bool(song), "can_claude": bool(song),
                     "build_label": "重出整片 + 剪辑工程（约 1 小时）" if song else "这类视频不能在这里重出整片"},
            "sections": blocks}


def find(stem: str, sid: str) -> dict:
    for s in sections(stem)["sections"]:
        if s["id"] == sid:
            return s
    raise KeyError(f"没有这一块：{sid}")


def _duration(video: Path) -> float:
    r = subprocess.run([str(FF.with_name("ffprobe.exe")), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip()), 2)
    except ValueError:
        return 0.0


def _segments(stem: str, w: Path, job: dict, dur: float) -> list[dict]:
    """job.json 的 sections；没有就按画面切换点自动切（缓存），每段至少 2 秒、最多 30 段。"""
    if job.get("sections"):
        return [{"title": str(s.get("title") or ""), "note": str(s.get("note") or ""), "from": float(s["from"]), "to": float(s["to"])}
                for s in job["sections"]]
    cache = JOBS / stem / "scenes.json"
    v = w / "video.mp4"
    if cache.exists() and json.loads(cache.read_text(encoding="utf-8")).get("mtime") == v.stat().st_mtime:
        cuts = json.loads(cache.read_text(encoding="utf-8"))["cuts"]
    else:
        r = subprocess.run([str(FF), "-hide_banner", "-i", str(v), "-vf", "select='gt(scene,0.3)',showinfo", "-an", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        cuts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"mtime": v.stat().st_mtime, "cuts": cuts}), encoding="utf-8")
    pts = [0.0]
    for c in cuts:
        if c - pts[-1] >= 2 and dur - c >= 2:
            pts.append(round(c, 2))
    while len(pts) > 30:                                          # 太碎：合并最短的一段
        gaps = [(pts[i + 1] if i + 1 < len(pts) else dur) - pts[i] for i in range(len(pts))]
        del pts[max(1, gaps.index(min(gaps[1:])))]
    return [{"title": "", "note": "", "from": a, "to": b} for a, b in zip(pts, pts[1:] + [dur])]


# ====================================================================== 检查（模型和 Claude 给的 JSON 都不可信）
def clean(stem: str, sec: dict, data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("方案不是 JSON 对象")
    base = sec["data"]
    get = lambda k: data.get(k, base.get(k))             # noqa: E731
    if sec["kind"] == "song":
        tags = get("tags") or []
        if isinstance(tags, str):
            tags = tags.replace("#", " ").split()
        return {"douyin_title": str(get("douyin_title") or "")[:30], "description": str(get("description") or "")[:600],
                "tags": [str(t).lstrip("#").replace(" ", "")[:20] for t in tags if str(t).strip()][:5]}
    if sec["kind"] == "seg":
        return {"title": str(get("title") or "")[:24], "note": str(get("note") or "")[:300]}
    song = hd_song(_job(work(stem)))
    _, d = load_film(song)
    i = int(sec["id"].split(":")[1])
    trs = transitions(song)
    if i == 0:
        t = 0.0
    else:
        lo = d["shots"][i - 1]["from"] + .4
        hi = (d["shots"][i + 1]["from"] if i + 1 < len(d["shots"]) else d["dur"]) - .4
        try:
            t = float(get("from"))
        except (TypeError, ValueError):
            t = base["from"]
        beat = 60 / d["bpm"]
        t = d["beat0"] + round((t - d["beat0"]) / beat) * beat                # 吸附到最近的一拍
        t = round(min(hi, max(lo, t)), 2)
    return {"zh": str(get("zh") or "")[:24], "picture": str(get("picture") or "")[:200], "from": t,
            "sub": get("sub") if get("sub") in SUB_ZH else base["sub"], "tr": get("tr") if get("tr") in trs else base["tr"]}


# ====================================================================== 采用
def _publish_md(w: Path, job: dict) -> None:
    (w / "publish.md").write_text(f"# 发布信息\n\n**标题**：{job.get('douyin_title', '')}\n\n**文案**：{job.get('description', '')} "
                                  + " ".join("#" + t for t in job.get("tags") or []) + "\n", encoding="utf-8")


def apply(stem: str, sid: str, data: dict, via: str = "api") -> dict:
    w = work(stem)
    sec = find(stem, sid)
    new = clean(stem, sec, data)
    hist = snapshot(stem, f"{via}：改 {sid}")
    job = _job(w)
    if sec["kind"] == "song":
        job.update(new)
        (w / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        _publish_md(w, job)
    elif sec["kind"] == "seg":
        if not job.get("sections"):
            job["sections"] = [{"title": s["data"]["title"], "note": s["data"]["note"], "from": s["range"][0], "to": s["range"][1]}
                               for s in sections(stem)["sections"] if s["kind"] == "seg"]
        job["sections"][int(sid.split(":")[1])].update(new)
        (w / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        song = hd_song(job)
        head, d = load_film(song)
        i = int(sid.split(":")[1])
        d["shots"][i].update(new)
        if i > 0:
            d["shots"][i - 1]["to"] = new["from"]
        save_film(song, head, d)
    return {"history": hist, "data": new}


# ====================================================================== A：用户自己的大模型
def guide(sec: dict) -> str:
    lines = []
    for f in sec.get("fields", []):
        opt = f"，可选 {[o[0] for o in f['options']]}（{'、'.join(o[1] for o in f['options'])}）" if f.get("options") else ""
        lines.append(f"- {f['key']}：{f['label']}{opt}")
    return "字段：\n" + "\n".join(lines)


def chat(stem: str, sid: str, message: str, history: list[dict]) -> dict:
    sec = find(stem, sid)
    info = sections(stem)["song"]
    what = ("这是一条全手绘的歌词动画（水彩绘本风，一镜对应一句歌词，转场卡在节拍上）。这一块是一个镜头（关键节点）。"
            "改画面描述只是记下新想法，真正把画面重画出来要点「交给 Claude」，你要提醒用户。") if sec["kind"] == "shot" else \
        "这一块是整体的发布信息。" if sec["kind"] == "song" else "这一块是视频里的一段，只能改名字和备注（画面要在原来的流程里改）。"
    system = (f"你是 cc-piano 的视频分段设计助手。视频是《{info['title']}》（{info['artist']}），类型：{info['kind']}，总长 {info['duration']} 秒。"
              f"{what}用户现在只想改：{sec['title']}（{sec['sub'][:60]}）。\n"
              "回答格式：先用一两句中文说明你打算怎么改，然后给一个 ```json 代码块，里面是这一块完整的新 JSON（在当前 JSON 基础上修改）。"
              "如果用户只是在提问，就只回答文字。\n\n" + guide(sec) +
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
            proposal = clean(stem, sec, json.loads(m.group(1)))
        except (ValueError, json.JSONDecodeError) as e:
            err = str(e)
    reply = re.sub(r"```(?:json)?\s*\{.*\}\s*```", "", text, flags=re.S).strip() or "方案在下面，看看要不要采用。"
    if err:
        reply += f"\n（方案没通过检查：{err}）"
    return {"reply": reply, "proposal": proposal}


# ====================================================================== B：交给 Claude 重画这一镜
CLAUDE_PROMPT = """你在 cc-piano 的手绘工作室里（douyin/handdrawn：p5.js + p5.brush 水彩绘本风，引擎 engine/core.js、engine/clawd.js，
表情库 library/expressions.js）。用户要重画一首歌词动画里的「一个镜头」，详细要求在 {job}\\request.md，先读它，再读里面提到的文件。

规则：
1. 只改这一镜。这首歌的画面代码在 {song_dir}：scenes.js（节点画面 node('node_NN', …)、共用的场景函数）、film.js（全片：每镜调用哪个画面、运镜、转场）。
2. 别的镜头必须和原来一模一样：被几个镜头共用的场景函数不要改，要改就复制一份新函数（新名字）给这一镜用；不要删除或改动别的节点。
3. 只能改上面两个文件，不要改 engine/、library/、别的歌的文件。函数名别和 p5.js 的全局函数重名（box、plane、sign、text、line、rect、mask 等）。
4. 风格保持：水彩 + 墨线（paint / inkLine / letter），角色用已有的 clawd() / boy() / person() 等；分层标签照原来的写法（tagged('props', …) 等）。
5. 写完用 Read 检查一遍括号。
6. 最后写 {job}\\result.json：{{"data": 这一镜完整的新 JSON（字段见 request.md，picture 写成你实际画出来的样子）, "summary": "用一两句中文告诉用户改了什么"}}。
   做不到就 data 写当前 JSON 原样，summary 说明原因。
"""


def _render_check(song: str, times: list[float]) -> list[str]:
    """无头渲染这几个时间点，返回页面报错。"""
    out = PREVIEW_TMP / song / "check.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = (f'. "{ENV_SH}" && cd "{HAND.as_posix()}" && node render.mjs --song="{song}" --scene=film '
           f'--sheet={",".join(f"{t:.2f}" for t in times)} --cols={len(times)} --w=480 --out="{out.as_posix()}"')
    r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    errs = [ln for ln in (r.stdout + r.stderr).splitlines() if "page error" in ln or ("Error" in ln and "ERR_FILE" not in ln)]
    if r.returncode and not errs:
        errs = [(r.stderr or r.stdout)[-300:]]
    return errs


def claude_job(stem: str, sid: str, message: str, progress=None) -> dict:
    w = work(stem)
    song = hd_song(_job(w))
    if not song:
        raise RuntimeError("这类视频还不能让 Claude 重画画面：可以先改文字，或者在原来的流程里改")
    sec = find(stem, sid)
    if sec["kind"] != "shot":
        raise RuntimeError("「整体」只能改文字：直接在上面的表单里改，或点「发送」")
    sdir = HAND / "songs" / song
    job = JOBS / stem / f"claude_{datetime.now():%Y%m%d_%H%M%S}"
    (job / "backup").mkdir(parents=True, exist_ok=True)
    files = [sdir / "scenes.js", sdir / "film.js"]
    for f in files:
        shutil.copy2(f, job / "backup" / f.name)
    i = int(sid.split(":")[1])
    info = sections(stem)["song"]
    (job / "request.md").write_text(
        f"# 要重画的镜头\n\n视频：《{info['title']}》{info['artist']}（全手绘歌词动画，总长 {info['duration']} 秒）\n\n"
        f"这一镜：第 {i + 1} 镜（film_data.js 里 shots[{i}]，视频时间 {sec['range'][0]:.2f}–{sec['range'][1]:.2f} 秒），"
        f"歌词：{sec['sub']}\n\n## 用户的要求\n\n{message}\n\n## 字段说明\n\n{guide(sec)}\n\n## 当前 JSON\n\n```json\n"
        f"{json.dumps(sec['data'], ensure_ascii=False, indent=1)}\n```\n\n## 相关文件\n\n- {sdir / 'scenes.js'}\n- {sdir / 'film.js'}\n"
        f"- {sdir / 'film_data.js'}（镜头表，只读）\n- {HAND / 'engine' / 'core.js'}、{HAND / 'engine' / 'clawd.js'}（引擎，只读）\n", encoding="utf-8")
    if progress:
        progress(.05, "Claude 正在看这一镜")
    prompt = CLAUDE_PROMPT.replace("{job}", str(job)).replace("{song_dir}", str(sdir))
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "& claude -p $env:CC_SECTION_PROMPT --allowedTools Read Write Edit Glob Grep "
                        "--permission-mode acceptEdits --setting-sources user --strict-mcp-config "
                        f"--add-dir '{job}' --add-dir '{HAND}' --output-format json --max-turns 60"],
                       cwd=sdir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400,
                       env={**os.environ, "CC_SECTION_PROMPT": prompt})
    (job / "claude_out.json").write_text(r.stdout or "", encoding="utf-8")
    try:
        cost = float(json.loads(r.stdout or "{}").get("total_cost_usd") or 0)
    except ValueError:
        cost = 0.0
    changed = [f.name for f in files if (job / "backup" / f.name).read_bytes() != f.read_bytes()]

    def undo(why: str):
        for f in files:
            shutil.copy2(job / "backup" / f.name, f)
        raise RuntimeError(f"Claude 改的画面没通过检查，已经还原：{why[-300:]}")
    if progress:
        progress(.5, "检查 Claude 改的代码")
    for f in files:
        chk = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if chk.returncode:
            undo(chk.stderr)
    _, d = load_film(song)
    others = [s["from"] + .5 for k, s in enumerate(d["shots"]) if k != i][:: max(1, len(d["shots"]) // 3)][:3]
    errs = _render_check(song, [(sec["range"][0] + sec["range"][1]) / 2, *others])
    if errs:
        undo(" / ".join(errs[:3]))
    res_file = job / "result.json"
    res = json.loads(res_file.read_text(encoding="utf-8-sig")) if res_file.exists() else {}
    saved = apply(stem, sid, res.get("data") or sec["data"], via="claude")
    return {"summary": str(res.get("summary") or ("改好了" if changed else "Claude 没有改画面"))[:500], "data": saved["data"],
            "history": saved["history"], "cost_usd": round(cost, 2), "changed": changed, "job": str(job)}


# ====================================================================== 预览 / 出整片
def _work_dir(w: Path) -> Path:
    """原声和分轨所在的 output/tracks_<标题>/work（和 film_build 同一个算法）。"""
    sys.path.insert(0, str(HAND))
    import film_build
    return film_build.work_dir_of(w)


def preview(stem: str, sid: str, progress=None) -> dict:
    w = work(stem)
    sec = find(stem, sid)
    if not sec["range"]:
        raise ValueError("「整体」没有单独的预览")
    a, b = sec["range"]
    out = JOBS / stem / "previews" / f"{sid.replace(':', '_')}_{datetime.now():%H%M%S}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    song = hd_song(_job(w))
    if not song:                                                   # 其他类型：原片里的这一段
        subprocess.run([str(FF), "-y", "-loglevel", "error", "-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", str(w / "video.mp4"),
                        "-vf", "scale=-2:720", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", str(out)], check=True)
        return {"video": str(out), "range": [a, b]}
    a, b = max(0.0, a - .3), b + .3                                # 前后多 0.3 秒，看得到进出的转场
    frames = PREVIEW_TMP / song / sid.replace(":", "_")
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    if progress:
        progress(.05, "渲染这一镜")
    cmd = (f'. "{ENV_SH}" && cd "{HAND.as_posix()}" && node render.mjs --song="{song}" --scene=film --frames --fps=12 --jpg '
           f'--from={a:.2f} --to={b:.2f} --out="{frames.as_posix()}"')
    r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    shots = sorted(frames.glob("f*.jpg"))
    if not shots:
        raise RuntimeError("这一镜没渲染出来：" + (r.stdout + r.stderr)[-300:])
    if progress:
        progress(.85, "合成 720p 预览")
    first = int(shots[0].stem[1:])
    src = _work_dir(w) / "source.wav"
    args = [str(FF), "-y", "-loglevel", "error", "-framerate", "12", "-start_number", str(first), "-i", str(frames / "f%04d.jpg")]
    if src.exists():
        args += ["-ss", f"{first / 12:.3f}", "-t", f"{len(shots) / 12:.3f}", "-i", str(src)]
    args += ["-vf", "fps=30,scale=1280:720,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    args += (["-c:a", "aac", "-b:a", "160k", "-shortest"] if src.exists() else []) + [str(out)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError("预览合成失败：" + r.stderr[-300:])
    return {"video": str(out), "range": [a, b]}


def full_build(stem: str, progress=None) -> dict:
    w = work(stem)
    song = hd_song(_job(w))
    if not song:
        raise RuntimeError("这类视频不能在这里重出整片")
    proc = subprocess.Popen([str(PY), str(HAND / "film_build.py"), song, str(w), "--json-progress"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    result, tail = None, []
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("@@"):
            ev = json.loads(line[2:])
            if progress and ev.get("pct") is not None:
                progress(ev["pct"], ev.get("msg", ""))
            if ev["stage"] == "done":
                result = ev.get("result")
            if ev["stage"] == "error":
                tail.append(ev["msg"])
        elif line:
            tail = (tail + [line])[-12:]
    proc.wait()
    if proc.returncode or not result:
        raise RuntimeError("出整片失败：" + " / ".join(tail[-3:]))
    return result
