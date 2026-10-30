"""MV 编剧（2026-10-28 起）：不要音轨拆解画面，整片是故事 MV，每段指定画风（3D 电影 / 手绘 / 过渡）。

和 screenwriter.py 共用 API 配置（web/writer_profiles.json）、歌词、旋律、评论（编号化、原文填回）；
输出逐段分镜（时间、画风、镜头、画面、评论、屏幕文字），存 output/writer/<歌>/mv_v<N>.json，
script_md() 导出给用户看的文字稿。
"""
import json
import re
from datetime import datetime

import screenwriter as sw

STYLES = ("3d", "handdrawn", "3d_to_handdrawn", "handdrawn_to_3d")
STYLE_ZH = {"3d": "3D 电影", "handdrawn": "手绘", "3d_to_handdrawn": "3D → 手绘（过渡）", "handdrawn_to_3d": "手绘 → 3D（过渡）"}

SYSTEM = """你是 cc-piano 的 MV 编剧。你只做一件事：为一条抖音「歌曲故事 MV」写分镜剧本。不聊别的；用户说与编剧无关的话时，
只回一句「这里只能编剧」，仍然按格式输出当前剧本。

这条视频没有音轨拆解画面，整片就是故事。主角是像素风格的小方块小人 CC（橙色身体、两只竖条眼睛、四条短腿），
还有他的妈妈（围裙、发髻）。每一段都要写画风：
- "3d"：3D 电影风格（three.js 实时渲染的电影感：景深、体积光、雾、辉光、胶片颗粒、慢推镜头），CC 是 3D 的方块小人；
- "handdrawn"：水彩手绘绘本风格（纸纹、墨线、水彩晕染）；
- "3d_to_handdrawn" / "handdrawn_to_3d"：两种画风之间的过渡镜头，要写清楚怎么变过去（比如 3D 的星光化成水彩、纸张从画面里铺开）。

规则：
1. 评论只能用给你的编号（c1、c2…），绝不改写、不编造；每条用到的评论要出现在画面里（像往事一样浮现），写清楚以什么形式浮现。
2. 评论放在意思对应的那句歌词处；分镜时间用视频秒数，覆盖 0 到总长，不重叠、不留空。
3. 避开：死亡细节、轻生、重病、枪、暴力、案件、政治、真人隐私。
4. 镜头要具体可画：景别、机位运动、画面里有什么、CC 在做什么、光和颜色；每段 1 句镜头 + 1~2 句画面，60 字以内。
5. 只输出一个 JSON（不要别的文字），格式：
{"title":"片名（12 字内）","logline":"一句话故事线（30 字内）","look":{"3d":"3D 部分的整体视觉（40 字内）","handdrawn":"手绘部分的整体视觉（40 字内）"},
 "shots":[{"from":秒,"to":秒,"part":"开头|中段|结尾","style":"3d|handdrawn|3d_to_handdrawn|handdrawn_to_3d","lyric":"这段唱到的歌词（可空）",
           "camera":"镜头","picture":"画面","comment":"c3 或 null","comment_show":"评论怎么浮现（有评论时写）","text":"屏幕上的其他字（可空）"}],
 "finale":{"text":"最后浮现的一句（20 字内，可以是短评论原句）","comment":"cN 或 null"},
 "question":"结尾问观众的话（25 字内）",
 "douyin_title":"抖音标题（30 字内，带「Claude」）","description":"抖音文案（200 字内，结尾一个问题）","tags":["5 个以内，不带 #"]}"""


def build_prompt(stem: str, structure: str) -> tuple[str, dict]:
    m = sw.materials(stem)
    s = m["song"]
    use = [c for c in m["comments"] if c.get("use", True)]
    ids = {f"c{i + 1}": c for i, c in enumerate(use[:60])}
    lyr = "\n".join(f"{sw._fmt(x['t'])} {x['text']}" for x in m["lyrics"]) or "（没有歌词）"
    mel = m["melody"]
    msg = (f"【歌】《{s['title']}》{s['artist']}，视频总长 {s['duration']} 秒（用的是原曲这一段）\n\n【结构要求】{structure}\n\n"
           f"【歌词（视频时间，AI 听写，rap 段个别字可能不准）】\n{lyr}\n\n【旋律】速度 {mel['tempo']} BPM；每 6 秒：\n" + "\n".join(mel["segments"]) +
           "\n\n【评论】（点赞数｜作者｜原文）\n" +
           "\n".join(f"{k}｜{c.get('likes') or '-'}｜{c.get('user') or '-'}｜{c['text'][:160]}" for k, c in ids.items()) +
           f"\n\n【知识库要点】\n{sw.knowledge_text()}\n\n【最近编过的故事】\n{sw.history_text()}")
    return msg, ids


def check(raw: dict, ids: dict, dur: float) -> dict:
    """评论编号换回原文；画风只能是四种之一；时间夹在 [0, 总长] 并按顺序排。"""
    def com(cid):
        return ids.get(str(cid).strip()) if cid not in (None, "", "null") else None
    shots = []
    for x in raw.get("shots") or []:
        try:
            a, b = max(0.0, float(x.get("from"))), min(dur, float(x.get("to")))
        except (TypeError, ValueError):
            continue
        if b - a < 0.5:
            continue
        c = com(x.get("comment"))
        shots.append({"from": round(a, 1), "to": round(b, 1), "part": str(x.get("part") or "")[:4],
                      "style": x.get("style") if x.get("style") in STYLES else "3d",
                      "lyric": str(x.get("lyric") or "")[:60], "camera": str(x.get("camera") or "")[:80],
                      "picture": str(x.get("picture") or "")[:160],
                      "comment": c["text"] if c else None, "user": c.get("user") if c else None,
                      "likes": c.get("likes") if c else None,
                      "comment_show": str(x.get("comment_show") or "")[:80] if c else "", "text": str(x.get("text") or "")[:40]})
    shots.sort(key=lambda s: s["from"])
    fin = raw.get("finale") or {}
    fc = com(fin.get("comment"))
    tags = [str(t).lstrip("#").replace(" ", "")[:20] for t in (raw.get("tags") or []) if str(t).strip()][:5]
    return {"title": str(raw.get("title") or "")[:16], "logline": str(raw.get("logline") or "")[:60],
            "look": {k: str((raw.get("look") or {}).get(k) or "")[:80] for k in ("3d", "handdrawn")}, "shots": shots,
            "finale": {"text": fc["text"][:40] if fc else str(fin.get("text") or "")[:20], "user": fc.get("user") if fc else None},
            "question": str(raw.get("question") or "")[:30], "douyin_title": str(raw.get("douyin_title") or "")[:30],
            "description": str(raw.get("description") or "")[:600], "tags": tags}


def _save(stem: str, script: dict, convo: list, usage: dict, ids: dict) -> int:
    d = sw.OUT / stem
    d.mkdir(parents=True, exist_ok=True)
    vs = [int(p.stem[4:]) for p in d.glob("mv_v*.json") if p.stem[4:].isdigit()]
    ver = max(vs) + 1 if vs else 1
    (d / f"mv_v{ver}.json").write_text(json.dumps({**script, "time": datetime.now().isoformat(timespec="seconds"), "usage": usage,
                                                   "convo": convo, "ids": {k: v["text"] for k, v in ids.items()}},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return ver


def generate(stem: str, structure: str, pid: str | None = None, hint: str = "") -> dict:
    msg, ids = build_prompt(stem, structure)
    if hint.strip():
        msg += f"\n\n【用户的想法】{hint.strip()[:800]}"
    text, usage = sw.llm(SYSTEM, [{"role": "user", "content": msg}], pid, max_tokens=5000)
    script = check(sw._parse(text), ids, float(sw.materials(stem)["song"]["duration"]))
    ver = _save(stem, script, [{"role": "user", "content": msg}, {"role": "assistant", "content": text}], usage, ids)
    return {"version": ver, "script": script, "usage": usage}


def refine(stem: str, ver: int, message: str, pid: str | None = None) -> dict:
    old = json.loads((sw.OUT / stem / f"mv_v{ver}.json").read_text(encoding="utf-8"))
    convo = old["convo"][:1] + old["convo"][-1:]
    convo += [{"role": "user", "content": "按下面的意见修改剧本，仍然只输出完整 JSON：" + message.strip()[:1200]}]
    ids = {k: {"text": v} for k, v in old["ids"].items()}
    for c in sw.load_comments(stem):                      # 作者、点赞从评论表补回
        for v in ids.values():
            if v["text"] == c["text"]:
                v.update({"user": c.get("user"), "likes": c.get("likes")})
    text, usage = sw.llm(SYSTEM, convo, pid, max_tokens=5000)
    script = check(sw._parse(text), ids, float(sw.materials(stem)["song"]["duration"]))
    ver2 = _save(stem, script, convo + [{"role": "assistant", "content": text}], usage, ids)
    return {"version": ver2, "script": script, "usage": usage}


def script_md(stem: str, ver: int) -> str:
    sc = json.loads((sw.OUT / stem / f"mv_v{ver}.json").read_text(encoding="utf-8"))
    song = sw._song(stem)
    out = [f"# 《{song.get('title', stem)}》MV 剧本 v{ver}：{sc.get('title', '')}", "",
           f"- 故事线：{sc.get('logline', '')}", f"- 3D 部分：{sc['look'].get('3d', '')}", f"- 手绘部分：{sc['look'].get('handdrawn', '')}",
           f"- 编剧：{(sc.get('usage') or {}).get('model', '')}，{sc.get('time', '')}；没有音轨拆解画面；评论都是录屏原文", "",
           "## 分镜", ""]
    for s in sc["shots"]:
        out.append(f"**{s['from']:.0f}–{s['to']:.0f} 秒｜{s['part']}｜{STYLE_ZH.get(s['style'], s['style'])}**  ")
        if s.get("lyric"):
            out.append(f"歌词：{s['lyric']}  ")
        out.append(f"镜头：{s['camera']}  ")
        out.append(f"画面：{s['picture']}")
        if s.get("comment"):
            out.append("\n> 「" + s["comment"].replace("\n", "\n> ") + f"」——{s.get('user') or ''}（{s.get('likes') or '?'} 赞）")
            out.append(f"\n评论浮现：{s['comment_show']}")
        if s.get("text"):
            out.append(f"\n屏幕文字：{s['text']}")
        out.append("")
    out += ["## 结尾", "", f"- 最后一句：{sc['finale'].get('text', '')}{' ——' + sc['finale']['user'] if sc['finale'].get('user') else ''}",
            f"- 问观众：{sc.get('question', '')}", "", "## 抖音文案", "", f"- 标题：{sc.get('douyin_title', '')}",
            f"- 文案：{sc.get('description', '')}", f"- 标签：{' '.join('#' + t for t in sc.get('tags', []))}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    print(script_md(sys.argv[1], int(sys.argv[2])) if len(sys.argv) > 2 else __doc__)


# ====================================================================== 歌词动画（2026-10-28 起：全手绘、整首歌、按卡点和歌词转场、不放评论）
LYRIC_SYSTEM = """你是 cc-piano 的歌词动画编剧。你只做一件事：为一首歌写「全手绘歌词动画」的分镜。不聊别的；用户说与编剧无关的话时，
只回一句「这里只能编剧」，仍然按格式输出当前剧本。

画面全部是水彩手绘绘本风格（纸纹、墨线、水彩晕染），角色是像素方块小人 CC：男生 CC（橙色身体、竖条眼睛、四条短腿），
女生 CC（偏粉、蝴蝶结、睫毛、蓝眼睛）；可以有其他路人小人（换颜色）、妈妈（围裙发髻）。CC 能做的：各种眼神（看上 / 下 / 左右、
星星眼、爱心眼、闭眼、哭、惊吓）、嘴型、举手、走、跑、跳、坐、躺、拿道具；头顶能冒小符号（汗、爱心、音符、问号、Z）。

规则：
1. 画面跟着歌词走：每句歌词都要有对应的画面，画面要具体可画（场景、道具、CC 在做什么、光和颜色），不要抽象的「意境」。
2. 转场要和歌词呼应，并卡在节拍上：比如「车门打开」用车门向两边滑开当转场；「点燃烦心事」用火苗烧穿画面；
   段落之间（rap → 副歌）用更大的转场。每个转场写清楚：怎么转、卡在哪个字或哪一拍。
3. 副歌出现三次（每次 8 句）：三次要有递进（比如第一次城市里看不到星星、第二次开始看到一两颗、第三次满天星星），同一句歌词三次画面不同。
4. 字幕：每镜写字幕放在哪（top|bottom|left|right|top_left|top_right|bottom_left|bottom_right|center），原则是不挡画面主体（CC 的脸、关键道具）。
5. 不要评论，不要网易云，不要音轨。避开：死亡、轻生、重病、暴力、政治、真人隐私；「依赖上了酒精」「抽进肺里」用象征画面（杯子、烟雾形状的乌云），不画真实抽烟喝酒的特写。
6. 只输出一个 JSON（不要别的文字），格式：
{"title":"片名（12 字内）","logline":"一句话（30 字内）","look":"整体视觉（50 字内）","motifs":["贯穿全片的视觉母题（3~5 个）"],
 "shots":[{"lines":[起始句号,结束句号],"first":"这一镜第一句歌词的前 8 个字（照抄）","picture":"画面（60 字内）","camera":"镜头（20 字内）","cc":"男生|女生|两人|路人|无",
           "transition":"进入这一镜的转场（30 字内）","cut_on":"卡在哪个字或第几拍（15 字内）","sub_pos":"字幕位置"}],
 "key_nodes":[{"line":句号,"title":"节点名（10 字内）","picture":"这一帧画什么（40 字内）"}],
 "douyin_title":"抖音标题（30 字内，带「Claude」）","description":"抖音文案（150 字内，结尾一个问题）","tags":["5 个以内"]}
shots 按句号顺序覆盖全部歌词（每镜 1~3 句，副歌一句一镜；句号就是给你的编号，一共只有给你的那么多句，重复的副歌也各有自己的句号），前奏和尾奏各单独一镜（lines 写 [0,0] 和 [999,999]）；key_nodes 12~18 个。"""


def lyric_prompt(stem: str) -> str:
    s = sw._song(stem)
    d = json.loads((sw._work(s) / "lyrics_full.json").read_text(encoding="utf-8"))
    lines = "\n".join(f"{i + 1}. [{ln['start']:.1f}-{ln['end']:.1f}] {ln['text']}" for i, ln in enumerate(d["lines"]))
    secs = "；".join(f"{n} {a:.0f}-{b:.0f}秒" for n, a, b in d["sections"])
    return (f"【歌】《{s.get('title', stem)}》{s.get('artist', '')}，全曲 {d['duration']} 秒，速度 {d['tempo']:.1f} BPM，"
            f"一小节约 {240 / d['tempo']:.2f} 秒，第一个强拍在 {d['downbeats'][0]:.2f} 秒。\n【段落】{secs}\n\n【歌词（句号. [开始-结束秒] 歌词）】\n{lines}")


def snap_lyric(raw: dict, stem: str) -> dict:
    """每镜的时间由句号算出，开头吸附到最近的节拍（段落开头吸附到强拍），首尾相接。"""
    s = sw._song(stem)
    d = json.loads((sw._work(s) / "lyrics_full.json").read_text(encoding="utf-8"))
    L, beats, dur = d["lines"], d["beats"], d["duration"]
    near = lambda t, grid: min(grid, key=lambda g: abs(g - t))   # noqa: E731
    shots, nxt = [], 1
    for x in raw.get("shots") or []:
        a, b = (x.get("lines") or [0, 0])[:2]
        a, b = int(a), int(b)
        first = re.sub(r"\W", "", str(x.get("first") or ""))[:6]
        if first and 0 < a < 999:                         # 模型的句号会漂：按「第一句的前几个字」从上一镜之后往下找
            hit = next((i for i in range(nxt, len(L) + 1) if re.sub(r"\W", "", L[i - 1]["text"]).startswith(first)), None)
            if hit:
                a, b = hit, min(len(L), hit + max(0, b - a))
        if 0 < a < 999:
            nxt = b + 1
        if a == 0:
            t0 = 0.0
        elif a >= 999:
            t0 = L[-1]["end"]
        else:
            t0 = L[max(1, min(a, len(L))) - 1]["start"]
            t0 = near(t0 - .05, beats)                          # 吸附到最近的一拍（强拍相位是推算的，不可靠）
        shots.append({**{k: str(x.get(k) or "")[:80] for k in ("picture", "camera", "cc", "transition", "cut_on", "sub_pos")},
                      "lines": [a, b], "from": round(t0, 2),
                      "text": " / ".join(L[i - 1]["text"] for i in range(max(1, a), min(b, len(L)) + 1)) if 0 < a < 999 else ""})
    shots.sort(key=lambda z: z["from"])
    for p, q in zip(shots, shots[1:]):
        p["to"] = q["from"]
    if shots:
        shots[-1]["to"] = dur
    for i in range(len(shots) - 2, -1, -1):              # 不到 0.3 秒的镜头（同时出现的两句，比如中英字幕）并进下一镜
        p, q = shots[i], shots[i + 1]
        if p["to"] - p["from"] < .3 and 0 < p["lines"][0] < 999 and 0 < q["lines"][0] < 999:
            q.update({"from": p["from"], "lines": [p["lines"][0], q["lines"][1]], "text": p["text"] + " / " + q["text"],
                      "picture": p["picture"] + " " + q["picture"]})
            del shots[i]
    nodes =[{"line": int(n.get("line") or 0), "title": str(n.get("title") or "")[:12], "picture": str(n.get("picture") or "")[:60]}
             for n in raw.get("key_nodes") or []]
    for n in nodes:
        n["t"] = L[n["line"] - 1]["start"] if 0 < n["line"] <= len(L) else (0.0 if n["line"] == 0 else L[-1]["end"])
        n["text"] = L[n["line"] - 1]["text"] if 0 < n["line"] <= len(L) else ""
    return {"title": str(raw.get("title") or "")[:16], "logline": str(raw.get("logline") or "")[:60], "look": str(raw.get("look") or "")[:80],
            "motifs": [str(m)[:30] for m in raw.get("motifs") or []][:6], "shots": shots, "key_nodes": nodes,
            "douyin_title": str(raw.get("douyin_title") or "")[:30], "description": str(raw.get("description") or "")[:400],
            "tags": [str(t).lstrip("#")[:20] for t in raw.get("tags") or []][:5]}


def generate_lyric(stem: str, pid: str | None = None, hint: str = "") -> dict:
    msg = lyric_prompt(stem) + (f"\n\n【用户的想法】{hint.strip()[:800]}" if hint.strip() else "")
    text, usage = sw.llm(LYRIC_SYSTEM, [{"role": "user", "content": msg}], pid, max_tokens=8000)
    script = snap_lyric(sw._parse(text), stem)
    d = sw.OUT / stem
    d.mkdir(parents=True, exist_ok=True)
    vs = [int(p.stem[7:]) for p in d.glob("lyric_v*.json") if p.stem[7:].isdigit()]
    ver = max(vs) + 1 if vs else 1
    (d / f"lyric_v{ver}.json").write_text(json.dumps({**script, "time": datetime.now().isoformat(timespec="seconds"), "usage": usage,
                                                      "convo": [{"role": "user", "content": msg}, {"role": "assistant", "content": text}]},
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    return {"version": ver, "script": script, "usage": usage}


SUB_ZH = {"top": "上方", "bottom": "下方", "left": "左侧", "right": "右侧", "top_left": "左上", "top_right": "右上",
          "bottom_left": "左下", "bottom_right": "右下", "center": "中间"}


def lyric_md(stem: str, ver: int) -> str:
    sc = json.loads((sw.OUT / stem / f"lyric_v{ver}.json").read_text(encoding="utf-8"))
    mm = lambda t: f"{int(t // 60)}:{t % 60:04.1f}"   # noqa: E731
    out = [f"# 《{sw._song(stem).get('title', stem)}》歌词动画剧本 v{ver}：{sc['title']}", "",
           f"- 一句话：{sc['logline']}", f"- 画面：{sc['look']}（全手绘）", f"- 贯穿母题：{'、'.join(sc['motifs'])}",
           f"- 编剧：{(sc.get('usage') or {}).get('model', '')}，{sc.get('time', '')}；转场卡在节拍上（时间已吸附到节拍 / 强拍）；不放评论", "",
           "## 关键动画节点", ""]
    for n in sc["key_nodes"]:
        out.append(f"- **{mm(n['t'])}｜{n['title']}**：{n['picture']}" + (f"（歌词：{n['text']}）" if n["text"] else ""))
    out += ["", "## 分镜", "", "| 时间 | 歌词 | 画面 | 镜头 | 转场（卡点） | 字幕位置 |", "|---|---|---|---|---|---|"]
    for s in sc["shots"]:
        out.append(f"| {mm(s['from'])}–{mm(s['to'])} | {s['text'] or '（前奏 / 尾奏）'} | {s['picture']} | {s['camera']} | "
                   f"{s['transition']}（{s['cut_on']}） | {SUB_ZH.get(s['sub_pos'], s['sub_pos'])} |")
    out += ["", "## 抖音文案", "", f"- 标题：{sc['douyin_title']}", f"- 文案：{sc['description']}", f"- 标签：{' '.join('#' + t for t in sc['tags'])}", ""]
    return "\n".join(out)
