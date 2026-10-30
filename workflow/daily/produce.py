"""每天 09:00：从「抖音运营」群取一段新录屏 → 认出歌名、裁出封面 → 按当前实验模板出片 → 发到群里审核。

用法（在 D:\\cc-engine 下）:
  douyin\\.venv\\Scripts\\python workflow\\daily\\produce.py            正常运行
  douyin\\.venv\\Scripts\\python workflow\\daily\\produce.py --dry-run  只看会处理哪一段，不下载不渲染
流程：
  1. 群里新的视频/音频消息下载到 douyin\\收件箱\\（处理过的 message_id 记在 workflow\\data\\inbox.json，不会重复）
  2. 取最早一段还没做过的录屏：抽一帧播放器画面，OCR 认出歌名歌手（tracks/song_ocr.py），裁出封面（tracks/cover_crop.py）
  3. 写 tracks\\songs\\<歌名>.json（引用 config.json 里的 template），运行 tracks\\build.py --prepare
  4. 成片发到群里（视频 + 标题），由用户审核；收件箱空了就列出剪映缓存里最新的 3 首，请用户选
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\cc-engine")
DOUYIN = ROOT / "douyin"
WF = ROOT / "workflow"
sys.path.insert(0, str(WF))
sys.path.insert(0, str(DOUYIN / "tracks"))
sys.path.insert(0, str(DOUYIN / "data"))
import notify  # noqa: E402
import db as studioDb  # noqa: E402

INBOX = DOUYIN / "收件箱"
STATE = WF / "data" / "inbox.json"
LOGS = WF / "logs"
PY = DOUYIN / ".venv" / "Scripts" / "python.exe"
CFG = json.loads((WF / "config.json").read_text(encoding="utf-8"))
MEDIA_EXT = {".mp4", ".mov", ".m4a", ".mp3", ".wav", ".aac", ".flac"}


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOGS / f"produce_{datetime.now():%Y-%m}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> dict:
    try:
        return studioDb.load_inbox_state()
    except Exception:
        if STATE.exists():
            return json.loads(STATE.read_text(encoding="utf-8"))
        return {"seen": [], "items": []}


def save_state(st: dict) -> None:
    try:
        studioDb.save_inbox_state(st)
    except Exception:
        pass
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


CJK = re.compile(r"[一-鿿]")


def _text(m: dict) -> str:
    c = m.get("content") or ""
    if c.startswith("{"):
        try:
            return json.loads(c).get("text", "")
        except ValueError:
            return ""
    return c


def lyrics_from_chat(msgs: list[dict], after: str, before: str | None = None) -> str | None:
    """录屏之后（下一条录屏之前）用户在群里发的文字，像歌词（至少 4 行英文）就当成这首歌的歌词。
    几条消息按顺序拼起来（歌词太长时用户可能分几次发）。"""
    parts = []
    for m in msgs:
        if m.get("msg_type") not in ("text", "post") or str(m.get("deleted")) == "True":
            continue
        if (m.get("sender") or {}).get("sender_type") != "user":
            continue
        t = m.get("create_time") or ""
        if t < after or (before and t >= before):
            continue
        parts.append(_text(m))
    text = "\n".join(parts)
    latin = [ln for ln in text.splitlines() if re.search(r"[A-Za-z]{2,}", ln) and not CJK.search(ln)]
    return text if len(latin) >= 4 else None


def fetch_inbox(st: dict, dry: bool) -> None:
    """群里新的录屏下载到收件箱，登记为待制作。"""
    since = (datetime.now().timestamp() - 14 * 86400)
    msgs = notify.messages(start=datetime.fromtimestamp(since).strftime("%Y-%m-%d"))
    for it in notify.media_items(msgs):
        if it["message_id"] in st["seen"]:
            continue
        if (it.get("sender") or {}).get("sender_type") != "user":   # 机器人自己发的成片预览不算录屏
            continue
        log(f"新录屏：{it['message_id']} {it.get('name') or ''}")
        if dry:
            continue
        path = notify.download(it, INBOX)
        st["seen"].append(it["message_id"])
        rec = {"message_id": it["message_id"], "file": str(path), "status": "new", "received": it.get("create_time")}
        later = [m.get("create_time") for m in notify.media_items(msgs)
                 if (m.get("create_time") or "") > (it.get("create_time") or "")]
        lyr = lyrics_from_chat(msgs, it.get("create_time") or "", min(later) if later else None)
        if lyr:                                # 录屏后面跟着发了歌词：存成 <录屏名>.lyrics.txt
            lp = path.with_suffix(".lyrics.txt")
            lp.write_text(lyr, encoding="utf-8")
            rec["lyrics"] = str(lp)
            log(f"  收到歌词：{lp.name}")
        st["items"].append(rec)
        save_state(st)


def grab_frame(video: Path, out: Path, t: float = 1.5) -> Path | None:
    import imageio_ffmpeg
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-q:v", "2", str(out)], capture_output=True)
    return out if r.returncode == 0 and out.exists() else None


def identify(media: Path, work: Path) -> dict:
    """录屏 → 歌名、歌手、封面图。录屏开头常是控制中心、后面可能翻到评论区，所以抽几个时间点，
    用第一张认得出「歌名 + 歌手 关注」的播放页画面。认不出歌名时用文件名。"""
    from PIL import Image
    import song_ocr
    info = {"title": media.stem, "artist": "", "cover": None}
    if media.suffix.lower() not in (".mp4", ".mov"):
        return info
    player = None
    for t in (3, 6, 10, 15, 22, 30):
        frame = grab_frame(media, work / f"frame_{t}.jpg", t)
        if not frame:
            break
        try:
            res = song_ocr.ocr(frame)
        except Exception as e:                 # OCR 失败不影响出片
            log(f"认歌名失败：{e}")
            break
        got = song_ocr.netease_player(res)
        if got:
            info.update(title=got["title"], artist=got["artist"])
            player = frame
            break
    if player:   # 网易云黑胶播放页：以唱片为中心裁成正方形（整张氛围图比唱片中间的小封面好看）
        im = Image.open(player).convert("RGB")
        w, h = im.size
        side = int(w * 0.94)                       # 稍微收一点，避开左下角的「xx人在听」
        left, top = (w - side) // 2, min(max(0, int(h * 0.40 - side / 2)), h - side)
        cover = work / "cover.jpg"
        im.crop((left, top, left + side, top + side)).save(cover, quality=95)
        info["cover"] = str(cover)
    return info


def library_match(title: str, artist: str) -> str | None:
    """拨片图库（douyin/flick/library.json）里名字是「歌名 - 歌手」的那张图，返回文件名。不区分大小写，
    歌手名里 OCR 常把 vs. 认成 VS.，所以只比字母数字。"""
    import flick_lib
    norm = lambda s: re.sub(r"[\W_]+", "", s.lower())   # noqa: E731
    t, a = norm(title), norm(artist)
    for it in flick_lib.load()["items"]:
        name = it.get("name", "")
        song_part, _, artist_part = name.partition(" - ")
        if norm(song_part) == t and (not a or not artist_part or norm(artist_part) == a):
            return it["file"]
    return None


def slugify(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s.lower()).strip("_") or "song"


def write_song(item: dict, info: dict) -> Path:
    songs = DOUYIN / "tracks" / "songs"
    path = songs / f"{slugify(info['title'])}.json"
    n = 2
    while path.exists() and json.loads(path.read_text(encoding="utf-8-sig")).get("audio") != item["file"]:
        path = songs / f"{slugify(info['title'])}_{n}.json"
        n += 1
    song = {"title": info["title"], "artist": info["artist"], "audio": item["file"],
            "template": CFG.get("template", "daw@v2"), "start": "auto",
            "douyin_title": info["title"], "description": "", "tags": ["音轨", "编曲", "纯音乐", "ClaudeCode"]}
    if item.get("lyrics"):                     # 群里发的歌词（原文 / 翻译交替）：女生小人唱歌时显示
        song["lyrics_text"] = item["lyrics"]
    lib_file = library_match(info["title"], info["artist"])
    if lib_file:                               # 拨片图库里已经有这首歌的图：用图库，主图就是它
        song.update(intro_from_library=True, intro_final=lib_file)
    elif info.get("cover"):                    # 图库里没有：开头用录屏裁出来的封面
        song.update(intro_from_library=False, final_image=info["cover"], images=[])
    path.write_text(json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build(song_path: Path) -> dict:
    """运行 build.py --prepare，返回 done 事件里的 result。"""
    proc = subprocess.Popen([str(PY), str(DOUYIN / "tracks" / "build.py"), str(song_path), "--prepare",
                             "--json-progress"], cwd=DOUYIN, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    result, tail, last_pct = None, [], -1
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("@@"):
            ev = json.loads(line[2:])
            pct = ev.get("pct")
            if pct is not None and int(pct * 10) != last_pct:
                last_pct = int(pct * 10)
                log(f"  {int(pct * 100)}% {ev['msg']}")
            if ev["stage"] == "done":
                result = ev.get("result")
        elif line:
            tail = (tail + [line])[-20:]
    proc.wait()
    if proc.returncode != 0 or not result:
        raise RuntimeError("出片失败：" + " / ".join(tail[-4:]))
    return result


def ask_for_song() -> None:
    """收件箱空了：列出剪映缓存里最新的几首，请用户在群里回复。"""
    music = Path.home() / "AppData/Local/JianyingPro/User Data/Cache/music"
    files = sorted(music.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)[:3] if music.is_dir() else []
    lines = [f"{i + 1}. {datetime.fromtimestamp(p.stat().st_mtime):%m-%d %H:%M} 加入剪映的 {p.name[:12]}…"
             for i, p in enumerate(files)]
    notify.send_markdown("**🎹 今天的收件箱是空的**\n\n请把 1–2 分钟的录屏发到这个群里；"
                         "或者从剪映最近用过的曲子里选一首（在琴房「音轨剪辑」里试听）：\n\n" +
                         ("\n".join(lines) or "（剪映缓存里也没有新曲子）"),
                         key=f"inbox-empty-{datetime.now():%Y%m%d}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    log("== 开始制作")
    st = load_state()
    fetch_inbox(st, a.dry_run)
    todo = [it for it in st["items"] if it["status"] == "new" and Path(it["file"]).suffix.lower() in MEDIA_EXT]
    if not todo:
        log("收件箱没有新录屏")
        if not a.dry_run:
            ask_for_song()
        return 0
    item = todo[0]
    log(f"今天做：{item['file']}")
    if a.dry_run:
        return 0
    work = WF / "data" / "produce" / Path(item["file"]).stem
    work.mkdir(parents=True, exist_ok=True)
    info = identify(Path(item["file"]), work)
    log(f"歌名：{info['title']} / {info['artist'] or '（没认出歌手）'}")
    song_path = write_song(item, info)
    item.update(status="rendering", song=str(song_path), title=info["title"])
    save_state(st)
    notify.send_markdown(f"已收到，开始制作《{info['title']}》（模板 {CFG.get('template')}，约 20–30 分钟）",
                         key=f"start-{item['message_id']}")
    try:
        res = build(song_path)
    except Exception as e:
        item["status"] = "failed"
        save_state(st)
        log(f"失败：{e}")
        notify.send_markdown(f"⚠️ 《{info['title']}》出片失败：{e}", key=f"fail-{item['message_id']}")
        return 1
    item.update(status="ready", folder=res["folder"], video=res["video"])
    save_state(st)
    folder = Path(res["folder"])
    notify.send_markdown(f"**✅ 今天的视频做好了，请审核：《{info['title']}》**\n\n"
                         f"- 模板：{CFG.get('template')}\n- 文件夹：{folder}\n"
                         f"- 今晚 22:00–22:30 随机时间会打开发布页并提醒你\n\n"
                         f"有要改的地方直接在群里说。", key=f"ready-{item['message_id']}")
    try:
        notify.send_video(folder / "video.mp4", folder / "cover.jpg", key=f"video-{item['message_id']}")
    except notify.LarkError as e:              # 视频太大等情况：只发文字，不算失败
        log(f"视频没发到群里：{e}")
    log(f"== 完成（{(time.time() - t0) / 60:.0f} 分钟）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
