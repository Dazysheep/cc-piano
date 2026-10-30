"""「开头设计」的模板库和渲染（用户 2026-10-30：拨片开头改名开头设计，可以设计新开头，设计好的保存成模板，下次直接用或者继续升级；
图片从专辑库（拨片图库 flick/library）里取；开头在剪辑页里要细分图层；模板在各类视频选开头时也能选）。

模板 = douyin/openers/<名>/v<N>.json：{"engine", "zh", "note", "params", "time"}，只追加新版本、不覆盖旧版。
引擎（engine）：
- flick：拨片（flick_intro）。params：images（图库文件名，按顺序；空 = 整个图库按图库顺序）、final（主图文件名，空 = 图库设置的主图）、
  seconds、vertical、text（落定后写歌名歌手）。出片时同时出分层剪辑工程（flick_layers）。
- opening：开头小剧场（opening.py，tracks/templates/opening/<script>/v<N>.json）。params：script、script_version、seconds。只有横屏。
- 交给 Claude 设计的新动效：tracks/openers/eng_<名>.py，里面写 ENGINE = {"zh", "guide", "defaults", "render"}，
  render(params, images, final, out_mp4, w, h, fps, seconds, title, artist, progress) -> {"video": mp4（无声）, "sfx": wav}。
内置模板：拨片、加班的夜（office）、在吗（zaima）。
"""
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRACKS = HERE.parent
ROOT = TRACKS.parent
for p in (str(TRACKS), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)
if str(ROOT / "piano") not in sys.path:
    sys.path.append(str(ROOT / "piano"))
import flick_lib  # noqa: E402

STORE = ROOT / "openers"
JOBS = ROOT / "output" / "openers"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
FF = next((ROOT / "tools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
NAME_RE = re.compile(r"^[\w\u4e00-\u9fff·\- ]{1,24}$")
BUILTIN = {
    "拨片": {"engine": "flick", "zh": "拨片", "note": "专辑卡片一张张向下滑过，停在主图上（原来的「拨片开头」）",
           "params": {"images": [], "final": "", "seconds": 4.0, "vertical": False, "text": True}},
    "加班的夜": {"engine": "opening", "zh": "加班的夜", "note": "开头小剧场：深夜办公室读评论，最后接拨片卡片（office 脚本）",
             "params": {"script": "office", "script_version": 0, "seconds": 20.0}},
    "在吗": {"engine": "opening", "zh": "在吗", "note": "开头小剧场：聊天窗口「在吗」（zaima 脚本）",
           "params": {"script": "zaima", "script_version": 0, "seconds": 20.0}},
}
ENGINE_ZH = {"flick": "拨片", "opening": "开头小剧场"}


# ====================================================================== 引擎
def custom_engines() -> dict:
    out = {}
    for p in sorted(HERE.glob("eng_*.py")):
        try:
            mod = importlib.import_module(p.stem)
            if isinstance(getattr(mod, "ENGINE", None), dict) and callable(mod.ENGINE.get("render")):
                out[p.stem[4:]] = mod.ENGINE
        except Exception:                                          # 坏掉的引擎不影响别的模板
            continue
    return out


def engine_names() -> list[str]:
    return ["flick", "opening", *custom_engines()]


def guide(engine: str) -> str:
    lib = flick_lib.load()
    files = "、".join(f"{it['file']}（{it['name']}）" for it in lib["items"])
    if engine == "flick":
        return ("拨片引擎的参数：\n- images：从专辑库里选哪些图、按什么顺序滑过（图库文件名列表；空列表 = 整个图库按图库顺序）\n"
                "- final：最后停留的主图（文件名；空 = 图库设置的主图）\n- seconds：时长 3~7 秒\n- vertical：true 竖屏 9:16 / false 横屏\n"
                f"- text：落定后是否写歌名歌手\n专辑库里有：{files}")
    if engine == "opening":
        scripts = sorted(p.name for p in (TRACKS / "templates" / "opening").iterdir() if p.is_dir())
        return (f"开头小剧场引擎的参数：\n- script：小剧场脚本，可选 {scripts}\n- script_version：脚本版本（0 = 最新）\n"
                "- seconds：时长 12~30 秒\n（只有横屏；最后会接上专辑库主图的拨片卡片）")
    eng = custom_engines().get(engine)
    return (eng or {}).get("guide", "") + (f"\n专辑库里有：{files}" if eng else "")


# ====================================================================== 模板库
def _seed() -> None:
    for name, tpl in BUILTIN.items():
        if not (STORE / name).is_dir():
            save(name, tpl["engine"], tpl["params"], tpl["note"], zh=tpl["zh"])


def versions(name: str) -> list[int]:
    d = STORE / name
    return sorted(int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit()) if d.is_dir() else []


def load(name: str, ver: int | None = None) -> dict:
    vs = versions(name)
    if not vs:
        raise FileNotFoundError(f"没有这个开头模板：{name}")
    ver = ver if ver in vs else vs[-1]
    return {**json.loads((STORE / name / f"v{ver}.json").read_text(encoding="utf-8")), "name": name, "version": ver}


def list_templates() -> list[dict]:
    _seed()
    out = []
    for d in STORE.iterdir() if STORE.is_dir() else []:
        if d.is_dir() and versions(d.name):
            t = load(d.name)
            out.append({**t, "versions": versions(d.name), "builtin": d.name in BUILTIN, "engine_zh": ENGINE_ZH.get(t["engine"], t["engine"])})
    order = list(BUILTIN)
    out.sort(key=lambda t: (order.index(t["name"]) if t["name"] in order else 99, -max(t["versions"])))
    return out


def clean(engine: str, params: dict, base: dict | None = None) -> dict:
    """模型 / Claude / 网页给的参数都不可信：只留认识的字段，图片必须在专辑库里。"""
    if not isinstance(params, dict):
        raise ValueError("参数不是 JSON 对象")
    base = base or {}
    get = lambda k, d=None: params.get(k, base.get(k, d))     # noqa: E731

    def num(k, lo, hi, d):
        try:
            return round(min(hi, max(lo, float(get(k, d)))), 2)
        except (TypeError, ValueError):
            return d
    if engine == "flick":
        files = {it["file"] for it in flick_lib.load()["items"]}
        imgs = [str(f) for f in (get("images", []) or []) if str(f) in files]
        final = str(get("final", "") or "")
        return {"images": list(dict.fromkeys(imgs)), "final": final if final in files else "", "seconds": num("seconds", 3, 7, 4.0),
                "vertical": bool(get("vertical", False)), "text": bool(get("text", True))}
    if engine == "opening":
        scripts = {p.name for p in (TRACKS / "templates" / "opening").iterdir() if p.is_dir()}
        sc = str(get("script", "office"))
        return {"script": sc if sc in scripts else "office", "script_version": int(num("script_version", 0, 999, 0)),
                "seconds": num("seconds", 12, 30, 20.0)}
    eng = custom_engines().get(engine)
    if not eng:
        raise ValueError(f"不认识的开头引擎：{engine}")
    defaults = eng.get("defaults", {})
    out = {}
    for k, d in defaults.items():                                   # 只留引擎声明过的参数，类型跟默认值一致
        v = get(k, d)
        try:
            out[k] = type(d)(v) if not isinstance(d, (list, dict)) else (v if isinstance(v, type(d)) else d)
        except (TypeError, ValueError):
            out[k] = d
    if "images" in out:
        files = {it["file"] for it in flick_lib.load()["items"]}
        out["images"] = [f for f in out["images"] if f in files]
    return out


def save(name: str, engine: str, params: dict, note: str = "", zh: str | None = None, base: dict | None = None) -> int:
    name = name.strip()
    if not NAME_RE.match(name):
        raise ValueError("模板名 1~24 个字，只能用中文、字母、数字、空格、·、-")
    if engine not in engine_names():
        raise ValueError(f"不认识的开头引擎：{engine}")
    p = clean(engine, params, base)
    vs = versions(name)
    ver = (vs[-1] + 1) if vs else 1
    (STORE / name).mkdir(parents=True, exist_ok=True)
    (STORE / name / f"v{ver}.json").write_text(json.dumps({"engine": engine, "zh": zh or name, "note": str(note)[:300], "params": p,
                                                          "time": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return ver


# ====================================================================== 出片
def _images(params: dict) -> tuple[list[Path], Path, list[str]]:
    """(依次滑过的图, 主图, 每张卡片的歌名)。"""
    lib = flick_lib.load()
    by = {it["file"]: it for it in lib["items"]}
    others, final = flick_lib.sequence(lib, final=params.get("final") or None)
    if params.get("images"):
        others = [flick_lib.LIB_DIR / f for f in params["images"] if f in by and flick_lib.LIB_DIR / f != final]
    names = [by.get(p.name, {}).get("name", "") for p in others] + [by.get(final.name, {}).get("name", "")]
    return others, final, names


def render(name: str, ver: int | None, title: str, artist: str, progress=None, dest: Path | None = None,
           with_layers: bool = True, fps: int = 60) -> dict:
    """按模板出一个独立的开头：<成片位置>/开头_<时间>_<标题>/intro.mp4（带音效）、intro.jpg、intro_sfx.wav、job.json、film/（分层工程）。"""
    import imageio_ffmpeg
    import storage
    tpl = load(name, ver)
    p, engine = tpl["params"], tpl["engine"]
    prog = progress or (lambda *_: None)
    slug = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_") or name
    dest = dest or storage.deliver_dir() / f"开头_{datetime.now():%Y%m%d_%H%M}_{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    silent = dest / "intro_silent.mp4"
    others, final, names = _images(p)
    vertical = bool(p.get("vertical")) and engine != "opening"
    w, h = (1080, 1920) if vertical else (1920, 1080)
    seconds = float(p.get("seconds") or 4)
    text = p.get("text", True)
    cb = lambda f, n: prog(.6 * f / max(n, 1), "渲染开头")   # noqa: E731
    if engine == "flick":
        import flick_intro
        info = flick_intro.render(final, others, silent, w, h, fps, seconds, title if text else "", artist if text else "", progress=cb)
    elif engine == "opening":
        import opening
        spec = {"name": p["script"], **({"version": p["script_version"]} if p.get("script_version") else {})}
        info = opening.render(opening.load_script(spec), final, others, silent, seconds, 30, title, artist, progress=cb)
    else:
        eng = custom_engines().get(engine)
        if not eng:
            raise RuntimeError(f"这个模板的引擎不见了：{engine}")
        info = eng["render"](p, others, final, silent, w, h, 30, seconds, title, artist, cb)
    sfx_wav = Path(info["sfx"])
    sfx_wav = sfx_wav.replace(dest / "intro_sfx.wav") if sfx_wav != dest / "intro_sfx.wav" else sfx_wav
    jpg = silent.with_suffix(".jpg")
    if jpg.exists():
        jpg.replace(dest / "intro.jpg")
    else:
        subprocess.run([str(FF), "-y", "-loglevel", "error", "-sseof", "-0.1", "-i", str(silent), "-frames:v", "1", str(dest / "intro.jpg")])
    last = dest / "intro_silent_last.png"
    if last.exists():
        last.replace(dest / "intro_last.png")
    out = dest / "intro.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(silent), "-i", str(sfx_wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    res = {"video": str(out), "cover": str(dest / "intro.jpg"), "sfx": str(sfx_wav), "folder": str(dest), "template": name, "version": tpl["version"]}
    (dest / "job.json").write_text(json.dumps({"kind": "intro", "title": title or name, "artist": artist, "template": name,
                                               "version": tpl["version"], "engine": engine}, ensure_ascii=False, indent=1), encoding="utf-8")
    prog(.62, "写剪辑工程")
    if with_layers and engine == "flick":
        import flick_layers
        res["project"] = str(flick_layers.render_layers(final, others, dest, w, h, 30, seconds, title if text else "", artist if text else "",
                                                        names, sfx_wav, lambda q, m="": prog(.62 + .36 * q, m)))
    elif with_layers:
        res["project"] = str(simple_project(dest, silent, sfx_wav, w, h, title or name))
    silent.unlink(missing_ok=True)
    prog(1.0, "开头已生成")
    return res


def simple_project(dest: Path, video: Path, sfx_wav: Path, w: int, h: int, title: str) -> Path:
    """没有分层渲染的引擎：画面一轨 + 音效一轨。"""
    import html
    film = dest / "film"
    assets = film / "assets"
    if film.exists():
        shutil.rmtree(film)
    assets.mkdir(parents=True)
    shutil.copy2(video, assets / "intro.mp4")
    shutil.copy2(sfx_wav, assets / "sfx.wav")
    r = subprocess.run([str(FF.with_name("ffprobe.exe")), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    dur = float(r.stdout.strip() or 1)
    doc = (f'<!doctype html>\n<html>\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width={w}, height={h}">\n'
           f'<title>{html.escape(title)}</title>\n</head>\n<body>\n<section title="开头画面">\n'
           f'  <video id="intro" src="assets/intro.mp4#t=0,{dur - .001:.3f}" at="0.000"></video>\n</section>\n<section title="音效">\n'
           f'  <audio id="sfx" src="assets/sfx.wav#t=0,{dur - .001:.3f}" at="0.000"></audio>\n</section>\n</body>\n</html>\n')
    (film / "film.html").write_text(doc, encoding="utf-8")
    return film / "film.html"


# ====================================================================== 用在别的视频上（音轨视频的歌曲 json 里写 "opener": {"name", "version"}）
def apply_to_song(song: dict) -> dict:
    """把模板翻译成 build.py 原来就认识的字段（拨片 → 图库顺序 / 主图 / 是否写歌名；小剧场 → opening 脚本）。
    Claude 设计的新引擎暂时只能单独出片：build.py 的正片转场要接开头最后一帧，新引擎还没有这个接口。"""
    spec = song.get("opener")
    if not spec:
        return song
    tpl = load(spec["name"] if isinstance(spec, dict) else str(spec), (spec or {}).get("version") if isinstance(spec, dict) else None)
    p = tpl["params"]
    if tpl["engine"] == "flick":
        song.pop("opening", None)
        song["intro_from_library"] = True
        if p.get("final"):
            song["intro_final"] = p["final"]
        song["intro_text"] = p.get("text", True)
        if p.get("images"):
            song["intro_images"] = p["images"]
    elif tpl["engine"] == "opening":
        song["opening"] = {"name": p["script"], **({"version": p["script_version"]} if p.get("script_version") else {})}
    else:
        raise RuntimeError(f"开头模板「{tpl['name']}」是新设计的动效，暂时只能在「开头设计」里单独出片，不能接进音轨视频")
    return song


# ====================================================================== 聊天设计（A：用户自己的大模型；B：交给 Claude）
def chat(name: str, message: str, history: list[dict]) -> dict:
    import anim_lib
    tpl = load(name)
    system = ("你是 cc-piano「开头设计」的助手：帮用户设计抖音音乐视频的开头（几秒钟的片头动画）。图片只能用专辑库里的。\n"
              f"现在打开的模板：{tpl['name']}（{ENGINE_ZH.get(tpl['engine'], tpl['engine'])}）：{tpl.get('note', '')}\n"
              "回答格式：先用一两句中文说明你打算怎么改，然后给一个 ```json 代码块：{\"params\": 完整的新参数, \"note\": \"这一版的说明（一句话）\"}。"
              "如果用户只是在提问，就只回答文字。如果用户要的是现在的引擎做不到的新动画效果（新的运动方式、新的画面元素），"
              "就告诉用户点「交给 Claude」设计一个新动效，不要硬凑参数。\n\n" + guide(tpl["engine"]) +
              "\n\n当前参数：\n```json\n" + json.dumps(tpl["params"], ensure_ascii=False, indent=1) + "\n```")
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
            raw = json.loads(m.group(1))
            proposal = {"params": clean(tpl["engine"], raw.get("params", raw), tpl["params"]), "note": str(raw.get("note") or "")[:200]}
        except (ValueError, json.JSONDecodeError) as e:
            err = str(e)
    reply = re.sub(r"```(?:json)?\s*\{.*\}\s*```", "", text, flags=re.S).strip() or "新参数在下面，看看要不要存成新版本。"
    if err:
        reply += f"\n（方案没通过检查：{err}）"
    return {"reply": reply, "proposal": proposal}


CLAUDE_PROMPT = """你在 cc-piano 项目的 douyin/tracks 目录里。用户在「开头设计」页面想要一个新的开头动效（抖音音乐视频的片头，几秒钟），
详细要求在 {job}\\request.md，先读它。

做法：新建一个引擎文件 openers/eng_{eng}.py（只能新建这一个文件，不要改任何已有文件），里面定义：
ENGINE = {{"zh": "中文名", "guide": "给聊天助手看的参数说明（每个参数一行）", "defaults": {{参数名: 默认值, ...}}, "render": render}}
def render(params, images, final, out, w, h, fps, seconds, title, artist, progress) -> dict
  - images：依次出现的专辑图（Path 列表），final：主图（Path），out：要写的无声 mp4 路径，w×h 画幅，fps 帧率，seconds 时长；
  - 用 PIL + numpy 逐帧画，用 imageio_ffmpeg.write_frames 写 mp4（参考 flick_intro.py 的 render 写法：libx264、yuv420p、crf 16）；
  - 音效：import sfx，参考 sfx.py 里已有的函数合成（或者安静的底噪），写到 out 同目录的 <out 文件名>_sfx.wav（sfx.write_wav）；
  - progress(已完成帧数, 总帧数) 时不时调用一下；返回 {{"video": out, "sfx": wav 路径}}。
  - title / artist 不为空时，落定后把歌名歌手写在画面上（字体 C:/Windows/Fonts/segoeuil.ttf / segoeui.ttf / msyh.ttc）。
参数里如果有图片相关的，用 "images"（专辑库文件名列表）这个名字；defaults 里每个参数都要有默认值。
写完后用 Read 检查一遍语法。最后写 {job}\\result.json：{{"engine": "{eng}", "params": 这个模板的参数, "note": "一句话说明", "summary": "用一两句中文告诉用户做了什么"}}。
"""


def claude_job(name: str, message: str, new_name: str, progress=None) -> dict:
    """交给 Claude 设计一个新动效引擎 → 试渲染 → 存成新模板 new_name 的 v1（或新版本）。代码不过就删掉。"""
    tpl = load(name)
    new_name = (new_name or "").strip() or f"{tpl['name']}·新动效"
    if not NAME_RE.match(new_name):
        raise ValueError("模板名 1~24 个字，只能用中文、字母、数字、空格、·、-")
    eng = f"d{datetime.now():%m%d%H%M%S}"
    job = JOBS / f"claude_{eng}"
    job.mkdir(parents=True, exist_ok=True)
    lib = flick_lib.load()
    (job / "request.md").write_text(
        f"# 新开头动效\n\n## 用户的要求\n\n{message}\n\n## 参考：当前模板\n\n{tpl['name']}（{ENGINE_ZH.get(tpl['engine'], tpl['engine'])}）："
        f"{tpl.get('note', '')}\n\n```json\n{json.dumps(tpl['params'], ensure_ascii=False, indent=1)}\n```\n\n"
        f"## 专辑库（flick/library）\n\n" + "\n".join(f"- {it['file']}：{it['name']}" for it in lib["items"]) +
        "\n\n## 可以参考的代码\n\n- tracks/flick_intro.py（拨片：卡片、阴影、模糊背景、运动模糊）\n- tracks/sfx.py（音效合成）\n"
        "- tracks/opening.py（开头小剧场：更复杂的场景）\n", encoding="utf-8")
    if progress:
        progress(.05, "Claude 正在设计新动效")
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "& claude -p $env:CC_OPENER_PROMPT --allowedTools Read Write Edit Glob Grep "
                        "--permission-mode acceptEdits --setting-sources user --strict-mcp-config "
                        f"--add-dir '{job}' --output-format json --max-turns 60"],
                       cwd=TRACKS, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2400,
                       env={**os.environ, "CC_OPENER_PROMPT": CLAUDE_PROMPT.replace("{job}", str(job)).replace("{eng}", eng)})
    (job / "claude_out.json").write_text(r.stdout or "", encoding="utf-8")
    try:
        cost = float(json.loads(r.stdout or "{}").get("total_cost_usd") or 0)
    except ValueError:
        cost = 0.0
    path = HERE / f"eng_{eng}.py"
    res_file = job / "result.json"
    if not path.exists() or not res_file.exists():
        path.unlink(missing_ok=True)
        raise RuntimeError("Claude 没做完新动效：" + (r.stderr or r.stdout or "")[-300:])
    if progress:
        progress(.6, "试渲染新动效")
    chk = subprocess.run([str(PY), "-c", f"import sys; sys.path[:0] = [r'{TRACKS}', r'{HERE}']; import eng_{eng} as m; "
                          "assert callable(m.ENGINE['render']) and isinstance(m.ENGINE['defaults'], dict)"],
                         cwd=TRACKS, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if chk.returncode:
        path.unlink(missing_ok=True)
        raise RuntimeError("新动效的代码没通过检查，已经删掉：" + chk.stderr[-300:])
    res = json.loads(res_file.read_text(encoding="utf-8-sig"))
    importlib.invalidate_caches()
    ver = save(new_name, eng, res.get("params") or {}, res.get("note") or message[:100])
    try:                                                            # 试渲染一次（不出分层），渲染失败也删掉引擎
        trial = render(new_name, ver, "", "", dest=job / "trial", with_layers=False)
    except Exception as e:
        path.unlink(missing_ok=True)
        shutil.rmtree(STORE / new_name, ignore_errors=True) if versions(new_name) == [ver] else (STORE / new_name / f"v{ver}.json").unlink()
        raise RuntimeError(f"新动效试渲染失败，已经删掉：{e}")
    return {"summary": str(res.get("summary") or "新动效做好了")[:500], "name": new_name, "version": ver, "engine": eng,
            "cost_usd": round(cost, 2), "video": trial["video"]}
