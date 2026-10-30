"""琴房：钢琴视频工作台的本地服务（仅监听 127.0.0.1）。

启动: 双击 douyin\\启动琴房.bat，或 .venv\\Scripts\\python web\\server.py
"""
import html
import json
import mimetypes
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from email.utils import formatdate
from urllib.parse import parse_qs, quote, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
UPLOADS = ROOT / "uploads"
sys.path.insert(0, str(ROOT / "piano"))
sys.path.insert(0, str(ROOT / "publish"))
sys.path.insert(0, str(ROOT / "tracks"))
sys.path.insert(0, str(ROOT / "editor"))       # OpenFilm 剪辑器的启动器和剪辑过程记录
sys.path.insert(0, str(ROOT / "blender3d"))    # 3D 建模：Blender 启动器、图片转 3D、3D 建模库
import audio  # noqa: E402
import flick_lib  # noqa: E402
import midi_notes  # noqa: E402
import storage  # noqa: E402
import template_lib  # noqa: E402
from platforms import PLATFORMS  # noqa: E402
from render import load_config  # noqa: E402

PORT = int(os.environ.get("QINFANG_PORT", 8765))
CFG = load_config({})
# 成片保存位置：默认 D:\cc-engine\douyin\待上传，也可跟随浏览器下载文件夹或自定义（piano/storage.py）
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
KINDS = {"midi": {".mid", ".midi"},
         "background": IMAGES | {".mp4", ".mov", ".webm"},
         "bgm": {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"},
         "audio": {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"},   # 钢琴录音，转写成 MIDI
         "cover": IMAGES,      # 开头右侧唱片：曲子封面
         "flick": IMAGES,      # 拨片开头图库：截图自动裁封面
         "avatar": IMAGES,     # 开头左侧唱片：账号头像（保存为默认）
         # 音轨剪辑：整首歌；iPhone 录屏（mp4/mov）也可以，只取声音
         "track_audio": {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".mov"},
         "lrc": {".lrc"},      # 音轨剪辑：歌词（校对 AI 识别结果）
         "model3d": IMAGES}    # 3D 建模：要转成 3D 的图片
mimetypes.add_type("text/javascript", ".js")      # three.js 是 ES 模块：类型不对浏览器会拒绝加载
mimetypes.add_type("model/gltf-binary", ".glb")
TRACK_SONGS = ROOT / "tracks" / "songs"
PAGES = {"/": "landing.html", "/app": "app.html", "/anim": "anim.html", "/studio": "index.html", "/index.html": "index.html",
         "/flick": "flick.html", "/flick.html": "flick.html", "/opener": "flick.html", "/tracks": "tracks.html", "/works": "works.html",
         "/tour": "tour.html", "/settings": "settings.html", "/edit": "edit.html", "/sections": "sections.html",
         "/writer": "writer.html", "/model3d": "model3d.html"}
AVATAR = ROOT / CFG["intro"]["avatar"]

STARTED = time.time()
# 服务进程启动时加载、改了需要重启才生效的文件（render.py 每次任务都重新启动，不在此列）
WATCHED = [ROOT / "web" / "server.py", ROOT / "piano" / "audio.py", ROOT / "piano" / "midi_notes.py",
           ROOT / "publish" / "platforms.py", ROOT / "tracks" / "flick_lib.py", ROOT / "tracks" / "cover_crop.py"]
RESTART_MSG = "琴房的程序已更新，请关闭黑色命令行窗口，再双击「启动琴房.bat」重启后重试"


def stale() -> bool:
    return any(p.stat().st_mtime > STARTED for p in WATCHED if p.exists())


jobs: dict[str, dict] = {}
job_queue: "queue.Queue[str]" = queue.Queue()
publish_queue: "queue.Queue[str]" = queue.Queue()


# ---------------------------------------------------------------- 工具函数
def media_url(p: Path) -> str:
    return "/media?path=" + quote(str(p))


def inside_root(p: Path) -> bool:
    try:
        p.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", Path(name).name) or "file"


def midi_summary(path: Path) -> dict:
    n = midi_notes.load(path)
    notes = [[int(p), round(float(s), 4), round(float(e), 4), int(h)]
             for p, s, e, h in zip(n["pitch"], n["start"], n["end"], n["hand"])]
    return {"count": len(notes), "duration": round(float(n["end"].max()), 2),
            "low": int(n["pitch"].min()), "high": int(n["pitch"].max()), "notes": notes}


SONGS = ROOT / "songs"


def song_meta(midi: Path) -> dict:
    """曲库里 MIDI 的同名 yaml（标题、开头封面等）；路径换成绝对路径和网页地址。"""
    import yaml
    side = midi.with_suffix(".yaml")
    meta = (yaml.safe_load(side.read_text(encoding="utf-8")) if side.exists() else None) or {}
    for k in ("background", "bgm", "intro_cover"):
        if meta.get(k):
            p = (midi.parent / meta[k]).resolve()
            meta[k] = {"path": str(p), "url": media_url(p), "name": p.name} if p.exists() else None
    if isinstance(meta.get("tags"), list):
        meta["tags"] = " ".join(map(str, meta["tags"]))
    return meta


def song_list() -> list[dict]:
    items = []
    for midi in sorted(SONGS.glob("*.mid"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = song_meta(midi)
        items.append({"file": midi.name, "title": meta.get("title") or midi.stem,
                      "subtitle": meta.get("subtitle", ""), "has_intro": bool(meta.get("intro_cover"))})
    return items


def work_kind(d: Path) -> str:
    """作品类型：piano（钢琴下落音符）/ tracks（音轨剪辑）/ intro（拨片开头）/ lyricfilm（手绘歌词动画）。"""
    if d.name.startswith("开头_"):
        return "intro"
    if (d / "intro_sfx.wav").exists():        # 音轨剪辑的成片都带开头音效
        return "tracks"
    try:
        kind = json.loads((d / "job.json").read_text(encoding="utf-8")).get("kind")
        if kind in ("tracks", "lyricfilm"):          # lyricfilm：手绘歌词动画（douyin/handdrawn）
            return kind
    except (OSError, ValueError):
        pass
    return "piano"


def library(include_intro: bool = False) -> list[dict]:
    """待上传里的成片（新的在前）。include_intro：同时列出拨片开头（intro.mp4），作品库用。"""
    items = []
    folders = [p for base in storage.all_dirs() if base.is_dir() for p in base.iterdir() if p.is_dir()]
    if folders:   # 当前保存位置 + 原来项目里的「待上传」
        for d in sorted(folders, key=lambda p: p.stat().st_mtime, reverse=True):
            video = d / "video.mp4"
            edited = d / "video_edited.mp4"            # 剪辑页选用了剪辑器导出的版本：发布台预览和发布都用它
            if video.exists() and edited.exists():
                video = edited
            if not video.exists() and include_intro and (d / "intro.mp4").exists():
                video = d / "intro.mp4"
            if not video.exists():
                continue
            pub = (d / "publish.md").read_text(encoding="utf-8") if (d / "publish.md").exists() else ""
            m = re.search(r"\*\*标题\*\*：(.+)", pub)
            cover = next((d / c for c in ("cover.jpg", "intro.jpg") if (d / c).exists()), None)
            items.append({
                "folder": str(d), "name": d.name, "title": m.group(1).strip() if m else d.name,
                "kind": work_kind(d),
                "has_vertical": (d / "video_vertical.mp4").exists(), "has_job": (d / "job.json").exists(),
                "edited": video == edited, "video": media_url(video), "cover": media_url(cover) if cover else None,
                "publish": pub, "size_mb": round(video.stat().st_size / 1e6, 1),
                "time": time.strftime("%m-%d %H:%M", time.localtime(video.stat().st_mtime)),
            })
    return items


def publish_defaults(folder: Path) -> dict:
    """一条成片在各平台的默认标题/文案/话题（来自生成时填写的内容）。"""
    job = json.loads((folder / "job.json").read_text(encoding="utf-8")) if (folder / "job.json").exists() else {}
    pub = (folder / "publish.md").read_text(encoding="utf-8") if (folder / "publish.md").exists() else ""
    title = job.get("douyin_title") or job.get("title") or ""
    if not title and (m := re.search(r"\*\*标题\*\*：(.+)", pub)):
        title = m.group(1).strip()
    desc = job.get("description", "")
    if not desc and (m := re.search(r"\*\*文案\*\*：(.*?)(?:\n\*\*|\Z)", pub, re.S)):
        desc = re.sub(r"\s*#\S+", "", m.group(1)).strip()
    tags = job.get("tags") or re.findall(r"#(\S+)", pub)
    if isinstance(tags, str):
        tags = [t.lstrip("#") for t in re.split(r"[,，\s]+", tags) if t.strip()]
    targets = []
    for p in PLATFORMS.values():
        targets.append({
            "key": p.key, "name": p.name, "vertical": p.vertical, "title_max": p.title_max,
            "title_min": p.title_min, "desc_max": p.desc_max, "tag_max": p.tag_max, "note": p.note,
            "title": title[: p.title_max] if p.title_max else "", "desc": desc[: p.desc_max], "tags": tags[: p.tag_max],
        })
    return {"folder": str(folder), "has_vertical": (folder / "video_vertical.mp4").exists(),
            "has_job": bool(job), "platforms": targets}


# ---------------------------------------------------------------- 音轨剪辑
JIANYING_MUSIC = Path(os.environ.get("LOCALAPPDATA", "")) / "JianyingPro" / "User Data" / "Cache" / "music"
DURATIONS_FILE = ROOT / "output" / ".cache" / "durations.json"
_durations: dict | None = None
_durations_lock = threading.Lock()


def _duration_key(p: Path) -> str:
    st = p.stat()
    return f"{p}|{int(st.st_mtime)}|{st.st_size}"


def audio_duration(p: Path) -> float | None:
    """音频时长（秒）。按 路径+修改时间+大小 存在磁盘缓存里（每次启动不用再对几十个文件各跑一次 ffmpeg，
    那是开端页启动卡 1 秒多的原因）。"""
    global _durations
    import imageio_ffmpeg
    key = _duration_key(p)
    with _durations_lock:
        if _durations is None:
            try:
                _durations = json.loads(DURATIONS_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _durations = {}
        if key in _durations:
            return _durations[key]
    out = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(p)], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", creationflags=0x08000000).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    with _durations_lock:
        _durations[key] = dur
        try:
            DURATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            DURATIONS_FILE.write_text(json.dumps(_durations, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return dur


CACHE_NAMES = ROOT / "tracks" / "cache_names.json"     # 剪映缓存的歌名（手动改名或「识别」得到）


def cache_names() -> dict:
    try:
        return json.loads(CACHE_NAMES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache_name(file: str, **fields) -> dict:
    names = cache_names()
    names[file] = {**names.get(file, {}), **fields}
    CACHE_NAMES.write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
    return names[file]


def jianying_cache() -> list[dict]:
    """剪映音乐缓存里的整首歌（1 分钟以上，新的在前）：在剪映里把歌加进任意草稿，这里就能选到。
    剪映不在本地存歌名，所以附上：加入时间（剪映自己的下载记录）、来源、大小、已经用在哪首歌里、
    手动起的名字或「识别」出来的歌名和歌词。"""
    items = []
    if not JIANYING_MUSIC.is_dir():
        return items
    meta = {}
    try:   # 剪映的下载记录：文件名 → 下载时间(毫秒)、类型、资源编号
        for it in json.loads((JIANYING_MUSIC / "downLoadcfg").read_text(encoding="utf-8")).get("list", []):
            meta[it.get("path")] = it
    except (OSError, ValueError):
        pass
    used = {}      # 已经用在音轨剪辑歌曲里的音频（同样大小的文件视为同一个）
    for s in track_songs():
        a = Path(str(s.get("audio", "")))
        if a.is_file():
            used.setdefault(a.stat().st_size, []).append(s["title"])
    names = cache_names()
    files = sorted(JIANYING_MUSIC.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)[:60]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:                    # 没缓存过的新文件并行查时长
        durs = dict(zip(files, ex.map(audio_duration, files)))
    for p in files:
        dur = durs[p]
        if not dur or dur < 60:
            continue
        m, st = meta.get(p.name, {}), p.stat()
        added = int(m["date"]) / 1000 if str(m.get("date", "")).isdigit() else st.st_mtime
        n = names.get(p.name, {})
        items.append({"path": str(p), "file": p.name, "duration": round(dur, 1), "url": media_url(p),
                      "time": time.strftime("%m-%d %H:%M", time.localtime(added)),
                      "source": "剪映音乐库" if m.get("cacheType") == 4 else "剪映素材",
                      "size_mb": round(st.st_size / 1e6, 1), "used_by": used.get(st.st_size, []),
                      "name": n.get("name", ""), "lyric": n.get("lyric", ""), "auto": n.get("auto", False)})
    items.sort(key=lambda x: x["time"], reverse=True)
    return items


def track_songs() -> list[dict]:
    out = []
    for p in sorted(TRACK_SONGS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            song = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        try:                                   # 引用了模板的歌：网页表单显示模板 + 歌曲覆盖后的实际效果
            resolved = template_lib.resolve(song)
        except FileNotFoundError:
            resolved = song
        lt = song.get("lyrics_text")
        lp = (Path(lt) if Path(lt).is_absolute() else TRACK_SONGS / lt) if lt else None
        paste = lp.read_text(encoding="utf-8-sig") if lp and lp.is_file() else ""
        out.append({"file": p.name, **song, "resolved": resolved, "lyrics_paste": paste})
    return out


def track_themes() -> list[dict]:
    import themes
    hexc = lambda c: "#%02x%02x%02x" % tuple(c)   # noqa: E731
    res = []
    for k, t in themes.THEMES.items():
        prev = WEB / "assets" / "themes" / f"{k}.jpg"
        res.append({"key": k, "name": t["name"], "bg": hexc(t["bg"]), "colors": [hexc(c) for c in t["colors"].values()],
                    "preview": media_url(prev) + f"&v={int(prev.stat().st_mtime)}" if prev.exists() else None})
    return res


TEMPLATE_KEYS = {"theme", "backdrop", "grain", "fireworks", "lyrics", "loop", "duration", "intro_from_library"}


def save_track_song(data: dict) -> str:
    """保存（新建或更新）tracks/songs/<名字>.json，返回文件名。只更新传来的字段。"""
    song = data.get("song") or {}
    if not str(song.get("title", "")).strip():
        raise ValueError("请填写歌名")
    if not song.get("audio") or not Path(song["audio"]).is_file():
        raise ValueError("请先选择整首歌的音频")
    if song.get("lrc") and not Path(song["lrc"]).is_file():
        raise ValueError("歌词文件不存在")
    name = data.get("file") or (re.sub(r"[^\w\-]+", "_", song["title"].lower()).strip("_") or "song")
    name = safe_name(name)
    name = name if name.endswith(".json") else name + ".json"
    path = TRACK_SONGS / name
    old = {"intro": 4.0, "intro_from_library": True}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8-sig"))
    paste = song.pop("lyrics_paste", None)
    old.update(song)
    if paste is not None:                       # 粘贴的歌词：存成同名 .lyrics.txt；清空就不用了
        txt = TRACK_SONGS / (Path(name).stem + ".lyrics.txt")
        if paste.strip():
            txt.write_text(paste.strip() + "\n", encoding="utf-8")
            old["lyrics_text"] = txt.name
        elif old.get("lyrics_text") == txt.name:
            old.pop("lyrics_text")
    for k in data.get("unset") or []:          # 和模板一样的效果不写进歌曲，让模板说了算（以后改模板也跟着变）
        if k in TEMPLATE_KEYS:
            old.pop(k, None)
    old.pop("resolved", None)
    if old.get("template") == "":
        old.pop("template")
    path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    return name


# ---------------------------------------------------------------- 分段修改（一首歌的视频按块聊天修改、单独预览）
section_jobs: dict[str, dict] = {}
section_lock = threading.Lock()                     # 渲染和 Claude 都很吃 CPU：一次只跑一个，其余排队


def section_job(kind: str, fn) -> str:
    """后台跑 fn(progress)；返回任务号。任务状态：queued → running → done / error，result 是 fn 的返回值。"""
    jid = uuid.uuid4().hex[:10]
    section_jobs[jid] = {"status": "queued", "kind": kind, "progress": 0.0, "msg": "排队中"}

    def prog(p, msg=""):
        section_jobs[jid].update(progress=round(float(p), 3), msg=msg or section_jobs[jid]["msg"])

    def run():
        with section_lock:
            section_jobs[jid].update(status="running", msg="开始")
            try:
                res = fn(prog)
                section_jobs[jid].update(status="done", progress=1.0, msg="完成", result=res)
            except Exception as e:
                section_jobs[jid].update(status="error", error=str(e))
    threading.Thread(target=run, daemon=True).start()
    return jid


def section_media(res: dict) -> dict:
    """任务结果里的本地视频路径换成网页能放的地址。"""
    out = dict(res or {})
    for k in ("video", "cover"):
        if out.get(k):
            out[k + "_url"] = media_url(Path(out[k]))
    return out


# ---------------------------------------------------------------- 编剧（歌词 + 旋律 + 评论 → 故事线，用户自己的接口）
writer_jobs: dict[str, dict] = {}


def writer_job(kind: str, fn) -> str:
    """后台跑 fn(progress)（调用大模型、认评论、导入录屏）；不和渲染抢锁。"""
    jid = uuid.uuid4().hex[:10]
    writer_jobs[jid] = {"status": "running", "kind": kind, "progress": 0.0, "msg": "开始"}

    def prog(p, msg=""):
        writer_jobs[jid].update(progress=round(float(p), 3), msg=msg or writer_jobs[jid]["msg"])

    def run():
        try:
            writer_jobs[jid].update(status="done", progress=1.0, msg="完成", result=fn(prog))
        except PermissionError as e:
            writer_jobs[jid].update(status="error", error=str(e), need_key=True)
        except Exception as e:
            writer_jobs[jid].update(status="error", error=str(e))
    threading.Thread(target=run, daemon=True).start()
    return jid


def writer_script(stem: str, ver: int) -> dict:
    """某一版剧本 + 每个节点的配图地址（动画库里现成的预览）。"""
    import screenwriter
    sc = screenwriter.load_version(stem, ver)
    for n in sc.get("nodes", []):
        p = screenwriter.node_image(n.get("anim") or {})
        n["img"] = media_url(p) + f"&v={int(p.stat().st_mtime)}" if p and p.exists() else None
    return {"version": ver, **{k: sc.get(k) for k in ("theme", "logline", "nodes", "plan", "new_animations", "usage", "time",
                                                      "applied")}}


def writer_songs() -> dict:
    """编剧页左边的歌：有歌曲 json 的 + 收件箱里还没做成歌曲的录屏（可以「导入」）。"""
    import screenwriter
    sys.path.insert(0, str(ROOT.parent / "workflow" / "daily"))
    rows, linked = [], set()
    for p in sorted(TRACK_SONGS.glob("*.json"), key=lambda q: q.stat().st_mtime, reverse=True):
        try:
            raw = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        linked.add(str(raw.get("audio", "")))
        rows.append({"stem": p.stem, "title": raw.get("title", p.stem), "artist": raw.get("artist", ""),
                     "comments": len(screenwriter.load_comments(p.stem)), "versions": len(screenwriter.versions(p.stem))})
    inbox = []
    try:
        import produce
        for it in produce.load_state()["items"]:
            if it.get("file") and it["file"] not in linked and it.get("status") not in ("published",):
                inbox.append({"message_id": it["message_id"], "received": it.get("received"), "status": it.get("status"),
                              "name": Path(it["file"]).name})
    except Exception:                                   # 没有收件箱也照常显示歌曲
        pass
    return {"songs": rows, "inbox": inbox, "profiles": screenwriter.profiles()}


def writer_import(message_id: str, prog) -> dict:
    """收件箱里的录屏 → 认歌、写歌曲 json、分离音轨和分析（约几分钟）、认评论。"""
    sys.path.insert(0, str(ROOT.parent / "workflow" / "daily"))
    import produce
    import screenwriter
    st = produce.load_state()
    item = next((i for i in st["items"] if i["message_id"] == message_id), None)
    if not item:
        raise ValueError("收件箱里没有这条录屏")
    media = Path(item["file"])
    work = ROOT.parent / "workflow" / "data" / "produce" / media.stem
    work.mkdir(parents=True, exist_ok=True)
    prog(0.05, "认歌名")
    info = produce.identify(media, work)
    song = produce.write_song(item, info)
    item["song"] = str(song)
    produce.save_state(st)
    prog(0.15, "分离音轨、分析旋律（第一次要几分钟）")
    r = subprocess.run([sys.executable, str(ROOT / "tracks" / "prepare.py"), str(song)], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        raise RuntimeError("准备失败：" + (r.stdout + r.stderr)[-300:])
    prog(0.6, "识别录屏里的评论")
    rows = screenwriter.ocr_comments(song.stem, lambda u, m="": prog(0.6 + 0.4 * u, m))
    return {"stem": song.stem, "title": info.get("title"), "comments": len(rows)}


# ---------------------------------------------------------------- 3D 建模（Blender：图片 → 3D，3D 建模库）
model3d_jobs: dict[str, dict] = {}


def model3d_job(fn) -> str:
    """后台跑 fn(progress)。后台 Blender 自己会和视频渲染排队（output/.render.lock）。"""
    jid = uuid.uuid4().hex[:10]
    model3d_jobs[jid] = {"status": "running", "progress": 0.0, "msg": "开始"}

    def prog(u, msg=""):
        model3d_jobs[jid].update(progress=round(float(u), 3), msg=msg or model3d_jobs[jid]["msg"])

    def run():
        try:
            model3d_jobs[jid].update(status="done", progress=1.0, msg="完成", result=fn(prog))
        except Exception as e:
            model3d_jobs[jid].update(status="error", error=str(e))
    threading.Thread(target=run, daemon=True).start()
    return jid


def model3d_state() -> dict:
    """3D 建模页要的全部状态：是否启用、库文件夹、Blender、MCP、云端密钥、库里的模型（带网页地址）。"""
    import blender as bl
    import model3d_lib
    c = model3d_lib.config()
    st = bl.status()
    rows = []
    for m in model3d_lib.models():
        v = int(Path(m["glb"]).stat().st_mtime)
        rows.append({**m, "glb_url": media_url(Path(m["glb"])) + f"&v={v}",
                     "thumb_url": media_url(Path(m["thumb"])) + f"&v={v}" if m["thumb"] else None})
    return {**c, "blender": st["blender"], "mcp_running": st["mcp_running"], "mcp_port": st["mcp_port"],
            "cloud_ready": model3d_lib.cloud_ready(), "cloud_key_env": model3d_lib.CLOUD_KEY_ENV, "models": rows}


# ---------------------------------------------------------------- 动画库（表情、想象画面、开头 / 结尾动画）
anim_jobs: dict[str, dict] = {}


def anim_preview_job(kind: str, name: str, version: int, who: str) -> str:
    """后台渲染预览（开头 / 结尾约 1~2 分钟，表情几秒），返回任务号。"""
    import anim_lib
    jid = uuid.uuid4().hex[:10]
    anim_jobs[jid] = {"status": "running", "progress": 0.0}

    def run():
        try:
            anim_lib.render_preview(kind, name, version, who,
                                    progress=lambda u: anim_jobs[jid].update(progress=round(u, 2)))
            anim_jobs[jid].update(status="done", progress=1.0)
        except Exception as e:                      # 预览失败不影响已保存的版本
            anim_jobs[jid].update(status="error", error=str(e))
    threading.Thread(target=run, daemon=True).start()
    return jid


def film_dirs() -> list[Path]:
    """所有带 OpenFilm 工程（film/film.html）的成片文件夹里的 film/。"""
    return [p / "film" for base in storage.all_dirs() if base.is_dir() for p in base.iterdir()
            if (p / "film" / "film.html").is_file()]


def edit_projects() -> list[dict]:
    """「剪辑」页左侧的工程列表：可以在 OpenFilm 里剪的成片（新的在前）。"""
    import journal
    out = []
    for film in sorted(film_dirs(), key=lambda f: (f / "film.html").stat().st_mtime, reverse=True):
        d = film.parent
        cover = d / "cover.jpg" if (d / "cover.jpg").exists() else d / "intro.jpg"      # 开头设计的开头只有 intro.jpg
        out.append({"folder": str(d), "name": d.name, "steps": len(journal.history(film)),
                    "cover": media_url(cover) if cover.exists() else None,
                    "edited": (d / "video_edited.mp4").exists(),
                    "time": time.strftime("%m-%d %H:%M", time.localtime((film / "film.html").stat().st_mtime))})
    return out


def edit_film(folder: str) -> Path:
    film = Path(folder) / "film"
    if not (is_work_folder(Path(folder)) and (film / "film.html").is_file()):
        raise ValueError("这条成片没有剪辑工程")
    return film


def film_title(film: Path) -> str:
    m = re.search(r"<title>(.*?)</title>", (film / "film.html").read_text(encoding="utf-8"), re.S)
    return html.unescape(m.group(1).strip()) if m else film.parent.name


def edit_exports(folder: str) -> dict:
    """这条成片在剪辑器里导出过的视频（比原成片新的），以及现在发布用的是不是剪辑版。"""
    import studio
    film = edit_film(folder)
    d = film.parent
    since = (d / "video.mp4").stat().st_mtime if (d / "video.mp4").exists() else (d / "job.json").stat().st_mtime
    files = studio.exports_for(film_title(film), since)
    edited = d / "video_edited.mp4"
    used = edited.stat() if edited.exists() else None      # 选用时是 copy2，大小和修改时间都一样
    return {"exports": [{"path": str(p), "name": p.name, "size": round(p.stat().st_size / 1e6, 1),
                         "time": time.strftime("%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
                         "used": bool(used and (used.st_size, int(used.st_mtime)) == (p.stat().st_size, int(p.stat().st_mtime)))}
                        for p in files],
            "using_edited": used is not None}


def is_work_folder(folder: Path) -> bool:
    """一条成片的文件夹：在项目里或成片保存位置里，并且有 video.mp4；
    或者有剪辑工程 + job.json（剪辑页导入的文件夹、开头设计出的开头，还没导出成片）。"""
    return folder.is_dir() and (inside_root(folder) or storage.inside(folder)) and (
        (folder / "video.mp4").exists() or ((folder / "film" / "film.html").is_file() and (folder / "job.json").is_file()))


def readable(p: Path) -> bool:
    """/media 允许读取的文件：项目目录里的、成片保存位置里的，或剪映音乐缓存里的（试听用）。"""
    try:                                              # 3D 建模库（用户可以指定到任意文件夹）：只在启用后才可读
        import model3d_lib
        if model3d_lib.blocked(p):
            return False
        if model3d_lib.inside_library(p):
            return True
    except Exception:
        pass
    if inside_root(p) or storage.inside(p):
        return True
    try:
        p.resolve().relative_to(JIANYING_MUSIC.resolve())
        return True
    except (ValueError, OSError):
        return False


PICK_FOLDER_PS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = $(if ($env:QF_DESC) { $env:QF_DESC } else { '选择视频保存位置（每条成片会在这里建一个子文件夹）' })
$d.ShowNewFolderButton = $true
if ($env:QF_START -and (Test-Path $env:QF_START)) { $d.SelectedPath = $env:QF_START }
$owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true; ShowInTaskbar = $false }
if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { $d.SelectedPath }
"""


def pick_folder(start: str = "", desc: str = "") -> dict:
    """用 Windows 自带的选择文件夹对话框（服务在本机运行，对话框弹在你的桌面上）。取消时 path 为空。desc：对话框上的提示文字。"""
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", PICK_FOLDER_PS],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "QF_START": start, "QF_DESC": desc}, creationflags=0x08000000)
    return {"path": (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else ""}


def py(*args) -> list[str]:
    """运行项目里的 Python 脚本/模块；打包成 exe 后由 exe 自己代为执行（见 app/launcher.py）。"""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--py", *map(str, args)]
    return [sys.executable, *map(str, args)]


# ---------------------------------------------------------------- 渲染任务（串行执行，避免内存不足）
def build_args(jid: str, o: dict) -> list[str]:
    """任务参数写进 JSON 文件交给 render.py，用户输入的文字不经过命令行解析（任何字符都安全）。"""
    job_file = UPLOADS / "jobs" / f"{jid}.json"
    job_file.parent.mkdir(parents=True, exist_ok=True)
    job_file.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
    return py(ROOT / "piano" / "render.py", "--job", job_file, "--json-progress")


def worker() -> None:
    """渲染与转写都很吃内存和 CPU，放在同一个队列里依次执行。"""
    while True:
        jid = job_queue.get()
        job = jobs[jid]
        job.update(status="running", started=time.time())
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        if job.get("kind") == "transcribe":
            src = Path(job["options"]["path"])
            out = SONGS / f"{re.sub(r'[^\w\-]+', '_', src.stem).strip('_') or 'song'}.mid"   # 转写结果直接进曲库
            n = 2
            while out.exists():
                out = out.with_name(f"{out.stem.rsplit('_v', 1)[0]}_v{n}.mid")
                n += 1
            cmd = py(ROOT / "piano" / "transcribe.py", src, "--out", out, "--json-progress")
        elif job.get("kind") == "flick":
            o = job["options"]
            cmd = py(ROOT / "tracks" / "flick_render.py", "--json-progress",
                     f"--title={o.get('title', '')}", f"--artist={o.get('artist', '')}",
                     f"--seconds={float(o.get('seconds') or 4)}")
            if o.get("vertical"):
                cmd.append("--vertical")
            if not o.get("draft", True):
                cmd.append("--no-draft")
        elif job.get("kind") == "tracks":       # 音轨剪辑：准备（分离/歌词/分析，已做过的跳过）+ 出片
            o = job["options"]
            cmd = py(ROOT / "tracks" / "build.py", TRACK_SONGS / o["file"], "--prepare", "--json-progress")
            if o.get("preview"):
                cmd += ["--preview", str(float(o["preview"]))]
            if not o.get("draft", True):
                cmd.append("--no-draft")
        else:
            cmd = build_args(jid, job["options"])
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
        job["pid"] = proc.pid
        tail = []
        for line in proc.stdout:
            line = line.rstrip()
            if line.startswith("@@"):
                ev = json.loads(line[2:])
                job["stage"], job["message"] = ev["stage"], ev["msg"]
                if ev.get("pct") is not None:
                    job["progress"] = ev["pct"]
                if ev["stage"] == "done" and job.get("kind") == "transcribe":
                    midi = Path(ev["midi"])
                    try:   # 转写完成：直接给出和导入 MIDI 一样的信息，网页可立即预览
                        res = {"path": str(midi), "name": midi.name, "url": media_url(midi), **midi_summary(midi)}
                        prev = Path(job["options"]["path"]).with_name("piano_preview.wav")
                        res["audio"] = media_url(audio.render_wav(midi, prev, CFG))
                        job["result"] = res
                    except Exception as e:
                        job["message"] = f"转写结果无法读取：{e}"
                elif ev["stage"] == "done":
                    r = ev["result"]
                    job["result"] = {**r, "video_url": media_url(Path(r["video"])),
                                     "cover_url": media_url(Path(r["cover"]))}
            elif line:
                tail = (tail + [line])[-30:]
        proc.wait()
        if proc.returncode == 0 and job.get("result"):
            job.update(status="done", progress=1)
        else:
            job.update(status="failed", message="渲染失败，详见日志", log="\n".join(tail))
        job["finished"] = time.time()


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 保持控制台清爽
        pass

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg, code=400):
        self._json({"error": msg}, code)

    def _file(self, path: Path):
        if not path.is_file():
            return self._error("文件不存在", 404)
        st = path.stat()
        size = st.st_size
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        modified = formatdate(int(st.st_mtime), usegmt=True)
        if not rng and self.headers.get("If-Modified-Since") == modified:   # 没改过：用浏览器缓存（启动更快）
            self.send_response(304)
            self.send_header("Last-Modified", modified)
            self.end_headers()
            return
        start, end = 0, size - 1
        if rng and (m := re.match(r"bytes=(\d*)-(\d*)", rng)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = size - int(m.group(2))
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Last-Modified", modified)
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass  # 浏览器拖动进度条时会中断请求

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in PAGES:
            return self._file(WEB / PAGES[url.path])
        if url.path == "/glass.css":
            return self._file(WEB / "glass.css")
        if url.path.startswith("/ui/"):          # 发布台、作品集、设置中心共用的样式和脚本
            return self._file(WEB / "ui" / safe_name(url.path[4:]))
        if url.path == "/api/tracks/songs":
            return self._json(track_songs())
        if url.path == "/api/tracks/themes":
            return self._json(track_themes())
        if url.path == "/api/edit/projects":      # 剪辑页：可以在 OpenFilm 里剪的成片
            return self._json(edit_projects())
        if url.path == "/api/edit/history":       # 一个工程的全部剪辑步骤
            import journal
            try:
                return self._json(list(reversed(journal.history(edit_film(q.get("folder", [""])[0])))))
            except ValueError as e:
                return self._error(str(e))
        if url.path == "/api/edit/exports":       # 剪辑器导出过的视频
            try:
                return self._json(edit_exports(q.get("folder", [""])[0]))
            except ValueError as e:
                return self._error(str(e))
        if url.path == "/api/edit/status":
            import studio
            return self._json({"address": studio.address()})
        if url.path == "/api/anim/library":       # 动画库：表情（男 / 女）、想象画面、开头动画、结尾动画
            import anim_lib
            return self._json(anim_lib.listing(media_url))
        if url.path == "/api/anim/item":          # 某个条目的当前 JSON（或指定版本）
            import anim_lib
            try:
                v = q.get("version", [""])[0]
                return self._json(anim_lib.current(q.get("kind", [""])[0], safe_name(q.get("name", [""])[0]),
                                                   q.get("who", ["male"])[0], int(v) if v else None))
            except (FileNotFoundError, ValueError, KeyError) as e:
                return self._error(str(e))
        if url.path == "/api/anim/job":
            return self._json(anim_jobs.get(q.get("id", [""])[0], {"status": "missing"}))
        if url.path == "/api/sections/songs":     # 分段修改：音轨视频 + 手绘动画 / 3D MV / 以后的新类型（钢琴不分段）
            import section_lib
            return self._json({"songs": section_lib.list_songs(media_url), "llm": __import__("anim_lib").llm_public()})
        if url.path == "/api/sections/list":      # 一首歌的分块（带整片里的缩略图）
            import section_lib
            stem = safe_name(q.get("song", [""])[0])
            try:
                res = section_lib.sections(stem)
            except (FileNotFoundError, KeyError, ValueError) as e:
                return self._error(str(e))
            v = res["song"]["video"]
            if v:
                res["song"]["video_url"] = media_url(Path(v))
                for s in res["sections"]:
                    if s["range"]:
                        t = (s["range"][0] + s["range"][1]) / 2
                        th = section_lib.thumb(Path(v), t, section_lib.JOBS / stem / "thumbs" /
                                               f"{s['id'].replace(':', '_')}_{int(t * 10)}.jpg")
                        s["thumb"] = media_url(th) + f"&v={int(th.stat().st_mtime)}" if th else None
            return self._json(res)
        if url.path in ("/api/model3d/config", "/api/model3d/state"):   # 3D 建模：设置页只要配置，3D 建模页要全部
            import blender as bl
            import model3d_lib
            if url.path == "/api/model3d/config":
                return self._json({**model3d_lib.config(), "blender": bl.version()})
            return self._json(model3d_state())
        if url.path == "/api/model3d/job":
            return self._json(model3d_jobs.get(q.get("id", [""])[0], {"status": "missing"}))
        if url.path == "/api/writer/state":       # 编剧：歌、收件箱录屏、接口配置
            return self._json(writer_songs())
        if url.path in ("/api/writer/materials", "/api/writer/version"):
            import screenwriter
            stem = safe_name(q.get("song", [""])[0])
            try:
                if url.path == "/api/writer/materials":
                    return self._json(screenwriter.materials(stem))
                return self._json(writer_script(stem, int(q.get("v", ["0"])[0])))
            except (FileNotFoundError, ValueError, KeyError) as e:
                return self._error(str(e))
        if url.path == "/api/writer/job":
            return self._json(writer_jobs.get(q.get("id", [""])[0], {"status": "missing"}))
        if url.path == "/api/sections/job":
            j = section_jobs.get(q.get("id", [""])[0], {"status": "missing"})
            return self._json({**j, "result": section_media(j.get("result"))} if j.get("result") else j)
        if url.path == "/api/opener/templates":   # 开头设计：模板库 + 专辑库（拨片图库）+ 聊天接口设置
            import openers
            scripts = sorted(p.name for p in (ROOT / "tracks" / "templates" / "opening").iterdir() if p.is_dir())
            return self._json({"templates": openers.list_templates(), "engines": openers.engine_names(), "scripts": scripts,
                               "library": flick_library(), "llm": __import__("anim_lib").llm_public()})
        if url.path == "/api/tracks/templates/get":   # 某个模板的某个版本（含说明）
            try:
                name, ver = template_lib.parse_ref(q.get("ref", [""])[0])
                if not template_lib.NAME_RE.match(name) or ver not in template_lib.versions(name):
                    raise FileNotFoundError("没有这个模板版本")
                return self._json(json.loads((template_lib.DIR / name / f"v{ver}.json").read_text(encoding="utf-8")))
            except (FileNotFoundError, ValueError) as e:
                return self._error(str(e))
        if url.path == "/api/tracks/templates":   # 模板库：每个模板的所有版本 + 最新版内容
            import template_lib
            return self._json(template_lib.listing())
        if url.path == "/api/tracks/cache":
            return self._json(jianying_cache())
        if url.path == "/api/flick/library":
            return self._json(flick_library())
        if url.path == "/media":
            p = Path(unquote(q.get("path", [""])[0]))
            return self._file(p) if readable(p) else self._error("路径不允许", 403)
        if url.path == "/api/songs":
            return self._json(song_list())
        if url.path == "/api/intro":
            return self._json({"avatar": media_url(AVATAR) + f"&v={int(AVATAR.stat().st_mtime)}" if AVATAR.exists() else None,
                               "left_name": CFG["intro"]["left_name"],
                               "enabled": bool(CFG["intro"].get("enabled", True))})
        if url.path == "/api/storage":           # 成片保存位置（设置 → 存储）
            return self._json(storage.info())
        if url.path == "/api/ui-state":          # 网页设置的服务端备份（端口变了也不丢）
            return self._json(storage.ui_state())
        if url.path == "/api/version":           # 软件版本（app/VERSION，打包时写进安装包名）
            v = ROOT / "app" / "VERSION"
            return self._json({"version": v.read_text(encoding="utf-8").strip() if v.exists() else "dev"})
        if url.path == "/api/health":
            return self._json({"ok": True, "stale": stale(), "message": RESTART_MSG if stale() else ""})
        if url.path == "/api/library":
            return self._json(library(include_intro=q.get("all", ["0"])[0] == "1"))
        if url.path == "/api/publish/defaults":
            folder = Path(unquote(q.get("folder", [""])[0]))
            if not is_work_folder(folder):
                return self._error("没有找到这条成片")
            return self._json(publish_defaults(folder))
        if url.path.startswith("/api/jobs/"):
            job = jobs.get(url.path.rsplit("/", 1)[-1])
            return self._json({k: v for k, v in job.items() if k != "pid"}) if job else self._error("任务不存在", 404)
        if url.path == "/api/jobs":
            out = []
            for k, v in jobs.items():
                o = v.get("options") or {}
                item = {"id": k, **{x: v[x] for x in ("status", "progress", "message")},
                        "kind": v.get("kind") or "render", "preview": bool(o.get("preview") or o.get("intro_only"))}
                r = v.get("result") or {}
                if v["status"] == "done" and r.get("video_url"):     # 给「文件包」的飞入动画用
                    item.update(video_url=r["video_url"], cover_url=r.get("cover_url"),
                                title=o.get("douyin_title") or o.get("title") or Path(r.get("video", "")).parent.name)
                out.append(item)
            return self._json(out)
        self._error("未找到", 404)

    def do_POST(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        if url.path == "/api/upload":
            kind = q.get("kind", [""])[0]
            name = safe_name(unquote(q.get("name", ["file"])[0]))
            if kind not in KINDS or Path(name).suffix.lower() not in KINDS[kind]:
                return self._error(f"不支持的文件类型：{name}")
            if kind == "flick":    # 拨片开头图库：截图自动裁出封面，普通图片裁成正方形，重复的跳过
                tmp = UPLOADS / "flick_in" / name
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(body)
                try:
                    r = flick_lib.add(tmp, Path(name).stem)
                except Exception as e:
                    return self._error(f"图片无法读取：{e}")
                finally:
                    tmp.unlink(missing_ok=True)
                return self._json({"duplicate": r["duplicate"], "name": r["item"]["name"], "file": r["item"]["file"],
                                   "song": r["song"], "new_song": r["new_song"], "library": flick_library()})
            if kind == "avatar":   # 头像固定使用，统一转成 jpg 存到 assets/intro
                from io import BytesIO
                from PIL import Image
                try:
                    Image.open(BytesIO(body)).convert("RGB").save(AVATAR, quality=95)
                except Exception as e:
                    return self._error(f"图片无法读取：{e}")
                return self._json({"path": str(AVATAR), "url": media_url(AVATAR) + f"&v={int(time.time())}"})
            session = re.sub(r"\W", "", q.get("session", [""])[0]) or uuid.uuid4().hex[:12]
            folder = UPLOADS / session
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / name
            path.write_bytes(body)
            res = {"session": session, "path": str(path), "url": media_url(path), "name": name}
            if kind == "midi":
                try:
                    res.update(midi_summary(path))
                    wav = audio.render_wav(path, folder / "piano_preview.wav", CFG)
                    res["audio"] = media_url(wav)
                except Exception as e:
                    return self._error(f"MIDI 无法解析：{e}")
            return self._json(res)

        data = json.loads(body or b"{}")
        if url.path == "/api/render":
            if stale():
                return self._error(RESTART_MSG, 409)
            midi = Path(data.get("midi", ""))
            if not (midi.is_file() and inside_root(midi)):
                return self._error("请先导入 MIDI")
            for k in ("background", "bgm", "intro_cover"):
                if data.get(k) and not inside_root(Path(data[k])):
                    return self._error("素材路径不允许")
            if not CFG["intro"].get("enabled", True):   # 开头功能关闭时忽略网页传来的开头参数
                data["intro"] = data["intro_only"] = False
            elif (data.get("intro") or data.get("intro_only")) and not data.get("intro_cover"):
                return self._error("加开头需要先上传曲子封面")
            jid = uuid.uuid4().hex[:10]
            jobs[jid] = {"id": jid, "status": "queued", "progress": 0, "stage": "queued",
                         "message": "排队中", "options": data, "created": time.time()}
            job_queue.put(jid)
            return self._json({"id": jid})
        if url.path == "/api/open":
            p = Path(data.get("path", ""))
            if not (inside_root(p) or storage.inside(p)) or not p.exists():
                return self._error("路径不允许")
            os.startfile(p)
            return self._json({"ok": True})
        if url.path == "/api/songs/load":
            midi = (SONGS / Path(data.get("file", "")).name)
            if not midi.is_file() or midi.suffix.lower() not in (".mid", ".midi"):
                return self._error("曲库里没有这首")
            session = uuid.uuid4().hex[:12]
            folder = UPLOADS / session
            folder.mkdir(parents=True, exist_ok=True)
            try:
                res = {"session": session, "path": str(midi), "url": media_url(midi), "name": midi.name,
                       **midi_summary(midi), "meta": song_meta(midi)}
                res["audio"] = media_url(audio.render_wav(midi, folder / "piano_preview.wav", CFG))
            except Exception as e:
                return self._error(f"MIDI 无法解析：{e}")
            return self._json(res)
        if url.path == "/api/tracks/save":
            try:
                return self._json({"file": save_track_song(data), "songs": track_songs()})
            except ValueError as e:
                return self._error(str(e))
        if url.path in ("/api/tracks/cache/name", "/api/tracks/cache/identify"):
            p = JIANYING_MUSIC / safe_name(data.get("file", ""))
            if not p.is_file():
                return self._error("剪映缓存里没有这个文件")
            if url.path.endswith("/name"):
                return self._json(save_cache_name(p.name, name=str(data.get("name", "")).strip()[:120], auto=False))
            # 识别要加载 Whisper，单独开进程跑（约 30~60 秒），不占渲染队列
            r = subprocess.run(py(ROOT / "tracks" / "cache_identify.py", p), cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            try:
                res = json.loads(r.stdout.strip().splitlines()[-1])
            except (IndexError, ValueError):
                return self._error("识别失败：" + (r.stderr.strip().splitlines() or ["未知错误"])[-1][:200])
            fields = {"lyric": res["lyric"] or "（没听到人声，可能是纯音乐）"}
            if res["name"] and not cache_names().get(p.name, {}).get("name"):   # 不覆盖手动起的名字
                fields.update(name=res["name"], auto=True)
            return self._json({**save_cache_name(p.name, **fields), "score": res["score"]})
        if url.path == "/api/tracks/render":
            if stale():
                return self._error(RESTART_MSG, 409)
            f = TRACK_SONGS / safe_name(data.get("file", ""))
            if not f.is_file():
                return self._error("请先保存歌曲设置")
            jid = uuid.uuid4().hex[:10]
            jobs[jid] = {"id": jid, "kind": "tracks", "status": "queued", "progress": 0, "stage": "queued",
                         "message": "排队中", "options": {**data, "file": f.name}, "created": time.time()}
            job_queue.put(jid)
            return self._json({"id": jid})
        if url.path == "/api/edit/open":               # 在 OpenFilm Studio 里打开工程（没在运行就先启动）
            import journal
            import studio
            try:
                film = edit_film(str(data.get("folder", "")))
            except ValueError as e:
                return self._error(str(e))
            journal.snapshot(film)                     # 打开前先记下起点
            out = studio.open_project(film)
            m = re.search(r"(http://127\.0\.0\.1:\d+/open\?\S+)", out)
            if not m:
                return self._error("剪辑器没有启动：" + out[-300:])
            return self._json({"url": m.group(1)})
        if url.path.startswith("/api/model3d/"):      # 3D 建模：配置 / 生成 / 删除 / 打开 Blender / 打开文件夹
            import blender as bl
            import model3d_lib
            try:
                if url.path == "/api/model3d/config":
                    c = model3d_lib.set_config(data.get("enabled") if "enabled" in data else None,
                                               str(data["dir"]) if "dir" in data else None)
                    return self._json({**c, "blender": bl.version()})
                if url.path == "/api/model3d/generate":
                    img = Path(str(data.get("path", "")))
                    if not (img.is_file() and (inside_root(img) or readable(img)) and img.suffix.lower() in IMAGES):
                        return self._error("图片不存在或不能读取")
                    kw = {k: float(data[k]) for k in ("strength", "thickness", "smooth") if k in data}
                    mode = "cloud" if data.get("mode") == "cloud" else "local"
                    name = safe_name(str(data.get("name") or img.stem))
                    return self._json({"job": model3d_job(lambda pr: model3d_lib.generate(img, name, mode, progress=pr, **kw))})
                if url.path == "/api/model3d/delete":
                    model3d_lib.delete(safe_name(str(data.get("name", ""))))
                    return self._json({"ok": True})
                if url.path == "/api/model3d/open_blender":     # 带界面的 Blender + MCP 连接（可以带上某个模型）
                    name = str(data.get("name") or "")
                    blend = model3d_lib.model_dir(safe_name(name)) / "model.blend" if name else None
                    return self._json(bl.open_gui(blend if blend and blend.exists() else None))
                if url.path == "/api/model3d/reveal":           # 在资源管理器里打开建模库 / 某个模型的文件夹
                    name = str(data.get("name") or "")
                    folder = model3d_lib.model_dir(safe_name(name)) if name else model3d_lib.library_dir()
                    if not folder:
                        return self._error("3D 建模还没有启用")
                    folder.mkdir(parents=True, exist_ok=True)
                    os.startfile(str(folder))
                    return self._json({"ok": True})
                return self._error("没有这个操作", 404)
            except PermissionError as e:
                return self._error(str(e), 412)
            except (ValueError, FileNotFoundError, KeyError, RuntimeError, OSError) as e:
                return self._error(str(e))
        if url.path.startswith("/api/writer/"):       # 编剧：接口配置 / 评论 / 认评论 / 编 / 改 / 套用 / 导入录屏
            import screenwriter
            stem = safe_name(str(data.get("song", "")))
            try:
                if url.path == "/api/writer/profile":
                    return self._json(screenwriter.save_profile(
                        str(data.get("id", "")), str(data.get("name", "")), str(data.get("kind", "openai")),
                        str(data.get("base_url", "")), str(data.get("model", "")), str(data.get("key") or "") or None,
                        bool(data.get("activate", True))))
                if url.path == "/api/writer/profile/delete":
                    return self._json(screenwriter.delete_profile(str(data.get("id", ""))))
                if url.path == "/api/writer/profile/active":
                    return self._json(screenwriter.set_active(str(data.get("id", ""))))
                if url.path == "/api/writer/import":
                    mid = str(data.get("message_id", ""))
                    return self._json({"job": writer_job("import", lambda p: writer_import(mid, p))})
                screenwriter.song_path(stem)
                if url.path == "/api/writer/comments":
                    return self._json({"comments": screenwriter.save_comments(stem, data.get("rows") or [])})
                if url.path == "/api/writer/ocr":
                    return self._json({"job": writer_job("ocr", lambda p: {"comments": screenwriter.ocr_comments(stem, p)})})
                pid = str(data.get("profile") or "") or None
                if url.path == "/api/writer/generate":
                    hint = str(data.get("hint", ""))

                    def gen(p):
                        p(0.1, "编剧中（大模型在想，通常 20~90 秒）")
                        r = screenwriter.generate(stem, pid, hint)
                        return {"version": r["version"], "usage": r["usage"]}
                    return self._json({"job": writer_job("generate", gen)})
                if url.path == "/api/writer/refine":
                    ver, msg = int(data.get("version", 0)), str(data.get("message", "")).strip()
                    if not msg:
                        return self._error("先写要怎么改")

                    def ref(p):
                        p(0.1, "按你的意见改剧本")
                        r = screenwriter.refine(stem, ver, msg, pid)
                        return {"version": r["version"], "usage": r["usage"]}
                    return self._json({"job": writer_job("refine", ref)})
                if url.path in ("/api/writer/apply", "/api/writer/kb"):   # 套用后 / 单独：DeepSeek 写歌曲档案进知识库
                    ver = int(data.get("version", 0))
                    res = screenwriter.apply(stem, ver) if url.path == "/api/writer/apply" else {}
                    sys.path.insert(0, str(ROOT.parent / "workflow" / "kb"))
                    import kb

                    def kb_write(p):
                        p(0.1, "DeepSeek 正在写这首歌的歌曲档案")
                        page = kb.write_song(stem, ver)
                        return {"page": str(page)}
                    return self._json({**res, "kb_job": writer_job("kb", kb_write)})
                return self._error("没有这个操作", 404)
            except PermissionError as e:
                return self._error(str(e), 412)
            except (ValueError, FileNotFoundError, KeyError, RuntimeError) as e:
                return self._error(str(e))
        if url.path.startswith("/api/opener/"):       # 开头设计：出片 / 存模板 / 聊天（自己的 API）/ 交给 Claude 设计新动效（任务用分段修改的队列）
            import openers
            name = str(data.get("name", "")).strip()[:24]
            try:
                if url.path == "/api/opener/render":
                    title, artist, ver = str(data.get("title", ""))[:80], str(data.get("artist", ""))[:80], data.get("version")
                    openers.load(name, ver)
                    return self._json({"job": section_job("opener", lambda p: openers.render(name, ver, title, artist, p))})
                if url.path == "/api/opener/save":     # 存成新版本（new_name 给了就存成新模板）
                    base = openers.load(name)
                    target = str(data.get("new_name") or name).strip()
                    ver = openers.save(target, base["engine"], data.get("params") or {}, str(data.get("note", ""))[:300],
                                       base=base["params"])
                    return self._json({"name": target, "version": ver, "templates": openers.list_templates()})
                if url.path == "/api/opener/chat":
                    return self._json(openers.chat(name, str(data.get("message", "")), data.get("history") or []))
                if url.path == "/api/opener/claude":
                    msg = str(data.get("message", "")).strip()
                    if not msg:
                        return self._error("先在输入框里写想要什么样的开头")
                    new_name = str(data.get("new_name", ""))[:24]
                    return self._json({"job": section_job("opener-claude", lambda p: openers.claude_job(name, msg, new_name, p))})
                return self._error("没有这个操作", 404)
            except (ValueError, FileNotFoundError, KeyError, RuntimeError) as e:
                return self._error(str(e))
        if url.path.startswith("/api/sections/"):     # 分段修改：聊天（自己的 API）/ 采用 / 交给 Claude / 预览 / 出整片
            import section_lib
            stem, sid = safe_name(str(data.get("song", ""))), str(data.get("sid", ""))[:20]
            try:
                section_lib.check(stem)                     # 歌曲 json（音轨视频）或待上传里的作品文件夹（手绘动画等）
                if url.path == "/api/sections/chat":
                    return self._json(section_lib.chat(stem, sid, str(data.get("message", "")), data.get("history") or []))
                if url.path == "/api/sections/apply":       # 采用方案：存版本，然后预览这一块
                    res = section_lib.apply(stem, sid, data.get("data") or {}, via="api")
                    pre = section_job("preview", lambda p: section_lib.preview(stem, sid, p)) \
                        if sid != "song" else None
                    return self._json({**res, "job": pre})
                if url.path == "/api/sections/claude":      # 交给 Claude：改完自动采用并预览
                    msg = str(data.get("message", "")).strip()
                    if not msg:
                        return self._error("先在输入框里写要改什么")

                    def work(p):
                        res = section_lib.claude_job(stem, sid, msg, p)
                        if sid != "song":
                            p(0.6, "Claude 改好了，正在渲染这一块")
                            res["preview"] = section_media(section_lib.preview(
                                stem, sid, lambda u, m="": p(0.6 + 0.4 * u, m)))
                        return res
                    return self._json({"job": section_job("claude", work)})
                if url.path == "/api/sections/preview":
                    return self._json({"job": section_job("preview", lambda p: section_lib.preview(stem, sid, p))})
                if url.path == "/api/sections/build":       # 出整片（约 35 分钟）
                    return self._json({"job": section_job("build", lambda p: section_lib.full_build(stem, p))})
                if url.path == "/api/sections/restore":
                    return self._json({"saved": section_lib.restore(stem, int(data.get("version", 0)))})
                return self._error("没有这个操作", 404)
            except PermissionError as e:
                return self._error(str(e), 412)
            except (ValueError, FileNotFoundError, KeyError, RuntimeError) as e:
                return self._error(str(e))
        if url.path in ("/api/anim/chat", "/api/anim/save", "/api/anim/llm"):
            import anim_lib
            kind, name = str(data.get("kind", "")), safe_name(str(data.get("name", "")))
            who = "female" if data.get("who") == "female" else "male"
            try:
                if url.path == "/api/anim/llm":     # 大模型设置：密钥只进用户环境变量，不回传
                    return self._json(anim_lib.set_llm(str(data.get("base_url", "")), str(data.get("model", "")),
                                                       str(data.get("key") or "") or None))
                if kind not in ("clip", "opening", "ending"):
                    return self._error("这个条目不能设计")
                if url.path == "/api/anim/chat":
                    res = anim_lib.chat(kind, name, str(data.get("message", "")), data.get("history") or [], who)
                    return self._json({"reply": res["reply"], "proposal": res["proposal"]})
                base = anim_lib.current(kind, name, who)
                clean = anim_lib.clean(kind, data.get("data") or {}, base)
                ver = anim_lib.save(kind, name, clean, who)
                return self._json({"version": ver, "job": anim_preview_job(kind, name, ver, who), "data": clean})
            except PermissionError as e:
                return self._error(str(e), 412)
            except (ValueError, FileNotFoundError, KeyError, RuntimeError) as e:
                return self._error(str(e))
        if url.path == "/api/edit/import":             # 导入文件夹：选文件夹 → 复制进项目 → 分轨工程（任务用分段修改的队列）
            import importer
            folder = str(data.get("path") or "").strip() or pick_folder("", "选择要导入剪辑的文件夹（里面的视频、图片、音频、字幕会分轨放进剪辑器）")["path"]
            if not folder:
                return self._json({"cancelled": True})
            if not Path(folder).is_dir():
                return self._error("没有这个文件夹")
            return self._json({"job": section_job("import", lambda p: importer.import_folder(Path(folder), p)), "path": folder})
        if url.path == "/api/edit/adopt":              # 发布时改用剪辑器导出的版本（file 为空 = 改回原成片）
            import studio
            try:
                d = edit_film(str(data.get("folder", ""))).parent
            except ValueError as e:
                return self._error(str(e))
            target = d / "video_edited.mp4"
            src = str(data.get("file") or "")
            if not src:
                target.unlink(missing_ok=True)
                return self._json({"using_edited": False})
            src_p = Path(src)
            if src_p not in studio.exports_for(film_title(d / "film")):
                return self._error("找不到这个导出文件")
            target.unlink(missing_ok=True)
            shutil.copy2(src_p, target)
            if not (d / "video.mp4").exists():             # 导入的工程 / 开头：第一次导出就当它的成片（作品集、发布台、一键发布都认 video.mp4）
                shutil.copy2(src_p, d / "video.mp4")
            return self._json({"using_edited": True})
        if url.path == "/api/edit/restore":            # 恢复到某一步（恢复本身也记成新的一步）
            import journal
            try:
                rec = journal.restore(edit_film(str(data.get("folder", ""))), str(data.get("id", "")))
            except (ValueError, FileNotFoundError) as e:
                return self._error(str(e))
            return self._json({"restored": rec})
        if url.path == "/api/tracks/templates/save":   # 当前效果另存为模板的新版本（旧版本不覆盖）
            import template_lib
            try:
                ver = template_lib.save_new_version(str(data.get("name", "")).strip(), data.get("data") or {})
            except ValueError as e:
                return self._error(str(e))
            return self._json({"version": ver, "templates": template_lib.listing()})
        if url.path == "/api/tracks/batch":            # 用同一个模板批量生成：逐首写入模板引用，再依次排队
            if stale():
                return self._error(RESTART_MSG, 409)
            ref = str(data.get("template", "")).strip()
            ids = []
            for name in data.get("files") or []:
                f = TRACK_SONGS / safe_name(name)
                if not f.is_file():
                    continue
                song = json.loads(f.read_text(encoding="utf-8-sig"))
                if ref:
                    song["template"] = ref
                    song["start"] = "auto"            # 片段按模板的目标时长重新选
                    f.write_text(json.dumps(song, ensure_ascii=False, indent=2), encoding="utf-8")
                jid = uuid.uuid4().hex[:10]
                jobs[jid] = {"id": jid, "kind": "tracks", "status": "queued", "progress": 0, "stage": "queued",
                             "message": "排队中", "options": {"file": f.name, "draft": data.get("draft", True)},
                             "created": time.time()}
                job_queue.put(jid)
                ids.append(jid)
            return self._json({"ids": ids})
        if url.path == "/api/storage":
            try:
                return self._json(storage.set_storage(str(data.get("mode", "")), str(data.get("path", ""))))
            except ValueError as e:
                return self._error(str(e))
        if url.path == "/api/ui-state":
            return self._json(storage.set_ui_state(data.get("ts", 0), data.get("keys") or {}))
        if url.path == "/api/storage/pick":      # 弹出系统的「选择文件夹」窗口（置顶）
            return self._json(pick_folder(str(data.get("start", ""))))
        if url.path == "/api/flick/songs":        # 一张专辑图的歌曲列表和选中的那首
            try:
                lib = flick_lib.set_songs(str(data.get("file", "")), data.get("songs") or [], int(data.get("pick", 0)))
            except (ValueError, TypeError) as e:
                return self._error(str(e))
            return self._json(flick_library(lib))
        if url.path == "/api/flick/update":
            lib = flick_lib.update(data.get("order", []), data.get("names"), data.get("final"))
            return self._json(flick_library(lib))
        if url.path == "/api/flick/render":
            if stale():
                return self._error(RESTART_MSG, 409)
            if not flick_lib.load()["items"]:
                return self._error("图库是空的，请先导入图片")
            jid = uuid.uuid4().hex[:10]
            jobs[jid] = {"id": jid, "kind": "flick", "status": "queued", "progress": 0, "stage": "queued",
                         "message": "排队中", "options": data, "created": time.time()}
            job_queue.put(jid)
            return self._json({"id": jid})
        if url.path == "/api/transcribe":
            if stale():
                return self._error(RESTART_MSG, 409)
            src = Path(data.get("path", ""))
            if not (src.is_file() and inside_root(src) and src.suffix.lower() in KINDS["audio"]):
                return self._error("请先上传钢琴录音（mp3、wav、m4a、flac）")
            jid = uuid.uuid4().hex[:10]
            jobs[jid] = {"id": jid, "kind": "transcribe", "status": "queued", "progress": 0, "stage": "queued",
                         "message": "排队中", "options": {"path": str(src)}, "created": time.time()}
            job_queue.put(jid)
            return self._json({"id": jid})
        if url.path == "/api/publish":
            if stale():
                return self._error(RESTART_MSG, 409)
            folder = Path(data.get("folder", ""))
            chosen = {k: v for k, v in (data.get("platforms") or {}).items() if k in PLATFORMS}
            if not is_work_folder(folder):
                return self._error("没有找到这条成片")
            if not chosen:
                return self._error("请至少选择一个平台")
            busy = [j for j in jobs.values() if j.get("kind") == "publish" and j["status"] in ("queued", "running")]
            if busy:
                return self._error("上一次的发布窗口还开着，请先在 Edge 里处理完并关闭窗口")
            jid = uuid.uuid4().hex[:10]
            jobs[jid] = {"id": jid, "kind": "publish", "status": "queued", "progress": 0, "stage": "queued",
                         "message": "排队中", "options": {"folder": str(folder), "platforms": chosen,
                                                         "orientation": data.get("orientation", "auto")},
                         "platforms": {k: {"state": "queued", "msg": "等待中"} for k in chosen},
                         "created": time.time()}
            publish_queue.put(jid)
            return self._json({"id": jid})
        if url.path == "/api/open-deliver":
            d = storage.deliver_dir()
            d.mkdir(parents=True, exist_ok=True)
            os.startfile(d)
            return self._json({"ok": True})
        if url.path == "/api/open-jianying":
            exe = Path(os.environ["LOCALAPPDATA"]) / "JianyingPro" / "Apps" / "JianyingPro.exe"
            if not exe.exists():
                return self._error("没有找到剪映专业版")
            subprocess.Popen([str(exe)])
            return self._json({"ok": True})
        self._error("未找到", 404)


def publish_worker() -> None:
    """一次只开一个发布窗口；进程会一直运行到你关掉 Edge 窗口。"""
    while True:
        jid = publish_queue.get()
        job = jobs[jid]
        job.update(status="running", started=time.time())
        job_file = UPLOADS / "jobs" / f"{jid}.json"
        job_file.parent.mkdir(parents=True, exist_ok=True)
        job_file.write_text(json.dumps(job["options"], ensure_ascii=False), encoding="utf-8")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(py(ROOT / "publish" / "publisher.py", "--job", job_file),
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=env)
        tail = []
        for line in proc.stdout:
            line = line.rstrip()
            if not line.startswith("@@"):
                if line:
                    tail = (tail + [line])[-30:]
                continue
            ev = json.loads(line[2:])
            job["stage"], job["message"] = ev["stage"], ev["msg"]
            if ev["stage"] == "platform":
                job["platforms"][ev["platform"]] = {k: ev.get(k) for k in ("state", "msg", "filled", "missing", "note")}
            elif ev["stage"] == "vertical":
                job["progress"] = ev.get("pct") or 0
            elif ev["stage"] == "error":
                job["error"] = ev["msg"]
        proc.wait()
        ok = proc.returncode == 0 and not job.get("error")
        job.update(status="done" if ok else "failed", finished=time.time())
        if not ok:
            job["log"] = "\n".join(tail)
            job.setdefault("error", "发布程序异常退出，详见日志")


def flick_library(lib: dict | None = None) -> dict:
    """拨片开头图库，附带每张图的网页地址（带修改时间，替换图片后浏览器不会用旧缓存）。"""
    lib = lib or flick_lib.load()
    items = []
    for it in lib["items"]:
        p = flick_lib.LIB_DIR / it["file"]
        if p.exists():
            items.append({"file": it["file"], "name": it["name"], "songs": flick_lib._songs(it),
                          "song": it.get("song", 0), "url": media_url(p) + f"&v={int(p.stat().st_mtime)}"})
    return {"items": items, "final": lib.get("final"), "final_pinned": bool(lib.get("final_pinned"))}


def main():
    try:
        sys.path.insert(0, str(ROOT / "data"))
        import db as _studioDb
        _studioDb.get_db()
    except Exception:
        pass
    page = sys.argv[sys.argv.index("--page") + 1] if "--page" in sys.argv else ""
    url = f"http://127.0.0.1:{PORT}/{page}"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:   # 琴房已经在运行：直接打开对应页面
        print(f"琴房已经在运行，正在打开 {url}")
        webbrowser.open(url)
        return
    try:
        storage.deliver_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=publish_worker, daemon=True).start()
    import journal                    # 剪辑过程记录：每秒检查一次各工程的 film.html，有改动就存一版
    journal.watch(film_dirs)
    print(f"琴房已启动：{url}  （关闭此窗口即停止）")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
