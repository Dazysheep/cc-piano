"""每天 14:00 的自动制作（定时任务「cc-piano\\每日制作」）：

1. 收飞书群里新的录屏（和录屏后面发的歌词），认歌名、找图库封面，写歌曲 json（模板用 config.json 的 template，现在是 daw@v6）；
2. 录屏抽帧拼成几张大图，交给 Claude Code 无界面模式（claude -p）读评论区，写评论故事、开头那条评论、抖音标题文案话题，
   结果写在 workflow/data/story/<录屏名>/story.json；
   - Claude 只能用 Read / Write，只能读写这个文件夹（不加载项目里的 hooks 和 MCP）；
   - 写出来的内容按 check_story() 检查（情绪、想象画面、音轨都必须是认识的值，条数、长度有上限），不合格就不出片、在群里说；
3. 合并进歌曲 json，出片（build.py），发群审核 + 视频；晚上 22 点的发布任务会用它。

没有新录屏时，在群里提醒发录屏（produce.ask_for_song）。
用法: douyin\\.venv\\Scripts\\python workflow\\daily\\daily_make.py [--dry-run] [--song 歌曲json]（--song：跳过收录屏，直接从第 2 步做）
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import notify  # noqa: E402
import produce  # noqa: E402

ROOT = produce.ROOT
STORY = produce.WF / "data" / "story"
TRACKS = produce.DOUYIN / "tracks"
sys.path.insert(0, str(TRACKS))
FF = next((produce.DOUYIN / "tools" / "ffmpeg").glob("ffmpeg-*/bin/ffmpeg.exe"))
MOODS = ["sad", "lonely", "happy", "love", "hope", "laugh", "nostalgic", "angry", "shy"]
TRACK_KEYS = ["vocals", "guitar", "bass"]


def log(msg: str) -> None:
    produce.log(msg)


# ---------------------------------------------------------------- 抽帧
def frame_sheets(media: Path, out: Path, every: float = 4.0) -> list[Path]:
    """录屏每隔 every 秒一帧（宽 540），4 张拼成一张大图，Claude 一张张读。"""
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("sheet_*.jpg"):
        p.unlink()
    r = subprocess.run([str(FF), "-v", "error", "-y", "-i", str(media), "-vf",
                        f"fps=1/{every},scale=540:-1,tile=4x1", str(out / "sheet_%02d.jpg")],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("抽帧失败：" + r.stderr[-300:])
    return sorted(out.glob("sheet_*.jpg"))


# ---------------------------------------------------------------- Claude 写故事
PROMPT = """你在给抖音账号「cc的音乐引擎」做一条「音轨拆解」视频写评论故事。这个文件夹里有：
- song.json：歌名、歌手（是从录屏认出来的，可能认错，你可以根据画面改正）
- lyrics.txt（可能没有）：歌词
- sheet_01.jpg、sheet_02.jpg ……：网易云录屏按时间顺序抽的帧，每张是 4 帧横排；前面通常是播放页，后面是评论区
- story_template.json：story.json 的模板（结构和字段名必须完全照它来）
- allowed.json：mood / vision / track 允许的值（vision 后面是中文意思）

步骤：先 Read story_template.json 和 allowed.json，再用 Read 依次看完所有 sheet 图片，读评论区里的网易云评论，
最后用 Write 写 story.json（只写这一个文件）。

要求：
- story.json 的结构必须和 story_template.json 一模一样：acts 是数组，每一幕是 {"name": ..., "cards": [...]}，
  每张卡片是对象 {"text", "track", "mood", "vision", "solo"}，不能写成字符串列表，也不要加模板里没有的字段。
- mood、vision、track 只能从 allowed.json 里选（vision 写英文名，比如 sunset_walk，不能自己编）。
- 评论必须是录屏里真实出现的原话，逐字照抄（用词、数字写法、标点都和画面一致，比如「八年」不能写成「8年」），太长可以截一段并用「……」表示省略，不要改写、不要编造；每条不超过 80 字。看不清的评论不要用，宁可少选。
- 不要选涉及自杀、自残、轻生、暴力、疾病绝症、亲人去世、具体个人隐私的评论。
- opening_comment：最戳人、最适合放在视频最开头的一条（不超过 100 字），它不要再出现在 acts 里。
- 一共 8~11 张卡片，分 3~4 幕，每幕 2~3 张，形成有起伏的故事（比如：心动 → 放手 → 家人 → 往前走）；
  全片最多 3 张 "solo": true（独白大字，只给最戳心的短句，不超过 40 字）。
- finale.text：你写的尾声一句话（中文，不超过 14 字）；finale.sub：一句英文（最好是歌词里的）。
- douyin_title 不超过 30 字，有钩子，不编造事实；description 3~5 段，第一人称，从评论里人们的经历出发，结合这首歌，真诚不煽情；
  tags 5 个，第一个是「音轨拆解」。
"""

TEMPLATE = {
    "title": "歌名（改正后）", "artist": "歌手（改正后）",
    "opening_comment": "最戳人的一条评论原话", "opening_vision": "reader_smile",
    "acts": [{"name": "心动", "cards": [
        {"text": "评论原话", "track": "vocals", "mood": "love", "vision": "sunset_walk", "solo": False},
        {"text": "评论原话", "track": "guitar", "mood": "shy", "vision": "hug", "solo": False}]}],
    "finale": {"text": "尾声一句话", "sub": "One line in English"},
    "douyin_title": "抖音标题", "description": "文案", "tags": ["音轨拆解", "歌名", "歌手", "话题", "话题"],
}

FIX = """story.json 没通过检查，问题：{errors}
请先 Read story_template.json、allowed.json 和现有的 story.json，按模板的结构和允许的值改好，再用 Write 覆盖 story.json。
评论原话不变（可以换别的录屏里的原话），只修结构和取值。"""


def _parse_claude_cost(raw: str) -> dict:
    """从 claude -p --output-format json 的输出里提取成本信息。"""
    try:
        out = json.loads(raw)
        return {"cost_usd": out.get("cost_usd", 0), "duration_ms": out.get("duration_ms", 0),
                "turns": out.get("num_turns", 0),
                "input_tokens": out.get("usage", {}).get("input_tokens", 0),
                "output_tokens": out.get("usage", {}).get("output_tokens", 0)}
    except (json.JSONDecodeError, AttributeError):
        return {"cost_usd": 0, "duration_ms": 0, "turns": 0, "input_tokens": 0, "output_tokens": 0}


def run_claude(job: Path, fix: str | None = None) -> tuple[dict, dict]:
    """在 job 文件夹里跑一次 claude -p；fix 给了时是让它按错误修 story.json。
    返回 (story_dict, cost_info)。"""
    import visions
    (job / "story_template.json").write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=1), encoding="utf-8")
    (job / "allowed.json").write_text(json.dumps(
        {"mood": MOODS, "track": TRACK_KEYS, "vision": {k: zh for k, (_, zh) in visions.VISIONS.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    prompt = FIX.replace("{errors}", fix) if fix else PROMPT
    if not fix:
        (job / "story.json").unlink(missing_ok=True)
    # 多行提示词经环境变量传给 PowerShell（cmd 的引号处理不了换行）。只给 Read / Write，不加载项目设置（hooks）和 MCP
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "& claude -p $env:CC_STORY_PROMPT --allowedTools Read Write --permission-mode acceptEdits "
                        "--setting-sources user --strict-mcp-config --output-format json --max-turns 40"],
                       cwd=job, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800,
                       env={**os.environ, "CC_STORY_PROMPT": prompt})
    out_file = "claude_fix.json" if fix else "claude_out.json"
    (job / out_file).write_text(r.stdout or "", encoding="utf-8")
    cost = _parse_claude_cost(r.stdout or "")
    phase = "修正" if fix else "首次"
    log(f"  Claude {phase}：${cost['cost_usd']:.2f}，{cost['turns']} 轮，"
        f"{cost['input_tokens']+cost['output_tokens']} tokens，{cost['duration_ms']/1000:.0f}s")
    if not (job / "story.json").exists():
        raise RuntimeError("Claude 没写出 story.json：" + (r.stderr or r.stdout or "")[-300:])
    return json.loads((job / "story.json").read_text(encoding="utf-8-sig")), cost


def write_story(job: Path) -> tuple[dict, dict]:
    """写故事；没通过检查时让 Claude 按错误修一次。返回 (story_dict, cost_summary)。"""
    story, cost1 = run_claude(job)
    try:
        return check_story(story), {"calls": 1, "fix": False, **cost1}
    except (ValueError, json.JSONDecodeError) as e:
        log(f"  第一次没通过检查：{e}，让 Claude 修一次")
        story2, cost2 = run_claude(job, fix=str(e))
        total_cost = cost1["cost_usd"] + cost2["cost_usd"]
        total_tokens = (cost1["input_tokens"] + cost1["output_tokens"] +
                        cost2["input_tokens"] + cost2["output_tokens"])
        log(f"  两次合计：${total_cost:.2f}，{total_tokens} tokens")
        return check_story(story2), {"calls": 2, "fix": True,
                                      "cost_usd": total_cost,
                                      "duration_ms": cost1["duration_ms"] + cost2["duration_ms"],
                                      "turns": cost1["turns"] + cost2["turns"],
                                      "input_tokens": cost1["input_tokens"] + cost2["input_tokens"],
                                      "output_tokens": cost1["output_tokens"] + cost2["output_tokens"]}


def check_story(st: dict) -> dict:
    """检查 Claude 写的故事，只留认识的字段和值；不合格抛 ValueError。"""
    import visions
    out = {"title": str(st.get("title") or "").strip()[:60], "artist": str(st.get("artist") or "").strip()[:60]}
    oc = str(st.get("opening_comment") or "").strip()
    if not 4 <= len(oc) <= 120:
        raise ValueError(f"opening_comment 缺失或太长（{len(oc)} 字，最多 120）")
    out["opening_comment"] = oc
    out["opening_vision"] = st.get("opening_vision") if st.get("opening_vision") in visions.VISIONS else "reader_smile"
    acts, n, solos = [], 0, 0
    for a in (st.get("acts") or [])[:4]:
        if not isinstance(a, dict) or not isinstance(a.get("cards"), list) or \
                not all(isinstance(c, dict) for c in a["cards"]):
            raise ValueError("acts 的每一幕必须是 {\"name\", \"cards\": [卡片对象…]}")
        cards = []
        for c in a["cards"][:3]:
            text = str(c.get("text") or "").strip()
            if not 2 <= len(text) <= 90 or text == oc:
                continue
            solo = bool(c.get("solo")) and solos < 3 and len(text) <= 40
            solos += solo
            cards.append({"text": text, "track": c.get("track") if c.get("track") in TRACK_KEYS else "vocals",
                          "mood": c.get("mood") if c.get("mood") in MOODS else "nostalgic",
                          "vision": c.get("vision") if c.get("vision") in visions.VISIONS else None, "solo": solo})
        if cards:
            acts.append({"name": str(a.get("name") or "")[:6], "cards": cards})
            n += len(cards)
    if not 6 <= n <= 12:
        raise ValueError(f"卡片数量不对（{n} 条）")
    out["acts"] = acts
    fin = st.get("finale") or {}
    out["finale"] = {"text": str(fin.get("text") or "愿你被这首歌好好接住")[:20], "sub": str(fin.get("sub") or "")[:60]}
    out["douyin_title"] = str(st.get("douyin_title") or out["title"])[:30]
    out["description"] = str(st.get("description") or "")[:600]
    tags = [str(t).lstrip("#").replace(" ", "")[:20] for t in (st.get("tags") or []) if str(t).strip()]
    out["tags"] = (["音轨拆解"] + [t for t in tags if t != "音轨拆解"])[:5]
    return out


def apply_story(song_path: Path, st: dict) -> None:
    """把故事合并进歌曲 json：各幕按卡片数分配时间（开头小剧场之后、结尾小剧场之前）。"""
    import template_lib
    song = json.loads(song_path.read_text(encoding="utf-8-sig"))
    full = template_lib.resolve(song)
    dur = float(full.get("duration", 84))
    t0 = float(full.get("intro", 19)) + 3.0                # 开头小剧场 + 水墨转场之后
    t1 = dur - float(full.get("ending_seconds", 10)) - 6.0  # 留给尾声那句话和结尾小剧场
    total = sum(len(a["cards"]) for a in st["acts"])
    acts, t = [], t0
    for a in st["acts"]:
        span = (t1 - t0) * len(a["cards"]) / total
        acts.append({"name": a["name"], "from": round(t, 2), "to": round(t + span - 0.5, 2),
                     "cards": [{k: v for k, v in c.items() if v is not None} for c in a["cards"]]})
        t += span
    song["story"] = {"acts": acts, "finale": {"from": round(t1 + 0.5, 2), **st["finale"]}}
    song["opening"] = {"name": "office", "comment": st["opening_comment"], "vision": st["opening_vision"]}
    for k in ("douyin_title", "description", "tags"):
        song[k] = st[k]
    if st["title"]:
        song["title"] = st["title"]
    if st["artist"]:
        song["artist"] = st["artist"]
    song_path.write_text(json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 主流程
def make_story(item: dict, song_path: Path) -> dict:
    """返回 cost_summary 供主流程记录。"""
    job = STORY / Path(item["file"]).stem
    sheets = frame_sheets(Path(item["file"]), job)
    song = json.loads(song_path.read_text(encoding="utf-8-sig"))
    (job / "song.json").write_text(json.dumps({"title": song["title"], "artist": song.get("artist", "")},
                                              ensure_ascii=False), encoding="utf-8")
    if song.get("lyrics_text"):
        lp = Path(song["lyrics_text"])
        lp = lp if lp.is_absolute() else TRACKS / "songs" / lp
        if lp.exists():
            (job / "lyrics.txt").write_text(lp.read_text(encoding="utf-8-sig"), encoding="utf-8")
    log(f"  抽帧 {len(sheets)} 张，交给 Claude 写评论故事")
    st, cost = write_story(job)
    (job / "story_checked.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    (job / "cost.json").write_text(json.dumps(cost, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from data import db as studioDb
        studioDb.save_story_cost(Path(item["file"]).stem, cost)
    except Exception:
        pass
    apply_story(song_path, st)
    log(f"  评论故事：{sum(len(a['cards']) for a in st['acts'])} 条，开头「{st['opening_comment'][:20]}」")
    return cost


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--song", type=Path, help="已有的歌曲 json（对应收件箱里的一条）：只做写故事 + 出片")
    a = ap.parse_args()
    t0 = time.time()
    log("== 每日制作开始")
    st = produce.load_state()
    if a.song:
        item = next((it for it in st["items"] if Path(it.get("song", "")) == a.song.resolve()), None)
        if not item:
            log("收件箱里没有这首歌")
            return 1
        song_path = a.song.resolve()
    else:
        produce.fetch_inbox(st, a.dry_run)
        todo = [it for it in st["items"] if it["status"] == "new" and Path(it["file"]).suffix.lower() in produce.MEDIA_EXT]
        if not todo:
            log("收件箱没有新录屏")
            if not a.dry_run:
                produce.ask_for_song()
            return 0
        item = todo[0]
        log(f"今天做：{item['file']}")
        if a.dry_run:
            return 0
        work = produce.WF / "data" / "produce" / Path(item["file"]).stem
        work.mkdir(parents=True, exist_ok=True)
        info = produce.identify(Path(item["file"]), work)
        song_path = produce.write_song(item, info)
        item.update(status="writing_story", song=str(song_path), title=info["title"])
        produce.save_state(st)
        notify.send_markdown(f"已收到录屏，开始制作《{info['title']}》：先让 Claude 读录屏里的评论写故事，再出片（约 40 分钟）",
                             key=f"start-{item['message_id']}")
    try:
        story_cost = make_story(item, song_path)
    except Exception as e:
        item["status"] = "story_failed"
        produce.save_state(st)
        log(f"写故事失败：{e}")
        notify.send_markdown(f"⚠️ 《{item.get('title')}》评论故事没写成：{e}\n\n可以在 Claude 对话里说一声，我手动写。",
                             key=f"story-fail-{item['message_id']}")
        return 1
    item.update(status="rendering", story_cost_usd=story_cost.get("cost_usd", 0),
                story_fix=story_cost.get("fix", False))
    produce.save_state(st)
    try:
        res = produce.build(song_path)
    except Exception as e:
        item["status"] = "failed"
        produce.save_state(st)
        notify.send_markdown(f"⚠️ 《{item.get('title')}》出片失败：{e}", key=f"fail-{item['message_id']}")
        return 1
    item.update(status="ready", folder=res["folder"], video=res["video"])
    produce.save_state(st)
    song = json.loads(song_path.read_text(encoding="utf-8-sig"))
    folder = Path(res["folder"])
    acts = song["story"]["acts"]
    cost_line = f"${story_cost['cost_usd']:.2f}"
    if story_cost.get("fix"):
        cost_line += f"（含修正轮次，共 {story_cost['calls']} 次调用）"
    notify.send_markdown(
        f"**✅ 今天的视频做好了，请审核：《{song['title']}》{song.get('artist', '')}**\n\n"
        f"- 模板：{produce.CFG.get('template')}（开头 / 结尾小剧场 + 两个小人）\n"
        f"- 开头评论：「{song['opening']['comment']}」\n"
        f"- 故事：{' → '.join(x['name'] for x in acts)}（{sum(len(x['cards']) for x in acts)} 条评论，Claude 读录屏写的，{cost_line}）\n"
        f"- 标题：{song.get('douyin_title')}\n- 话题：{' '.join('#' + t for t in song.get('tags', []))}\n\n"
        "评论是 Claude 读录屏抄的，偶尔会抄错字，审核时顺便对一下原话。\n"
        "今晚 22:00–22:30 会打开发布页并提醒你；有要改的地方直接在群里说。", key=f"ready-{item['message_id']}")
    try:
        notify.send_video(folder / "video.mp4", folder / "cover.jpg", key=f"video-{item['message_id']}")
    except notify.LarkError as e:
        log(f"视频没发到群里：{e}")
    log(f"== 完成（{(time.time() - t0) / 60:.0f} 分钟）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
