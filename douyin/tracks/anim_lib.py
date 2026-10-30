"""cc-piano「动画库」的后台：表情库（男生 / 女生的动画片段和变体）、想象画面、开头动画、结尾动画。

- 每个条目都能预览：表情和想象画面导出「沿着人物边缘裁好的」透明动图（.webp，背景透明、四周没有多余空白），
  开头 / 结尾动画渲染一段小尺寸预览视频（.mp4）。
- 每个条目都有版本：表情变体在 assets/clawd/variants/<角色>/<名字>/v<N>.json，开头在 tracks/templates/opening/<名字>/，
  结尾在 tracks/templates/ending/<名字>/。保存只会新增版本，不覆盖旧的。
- 聊天设计：把用户的话 + 当前 JSON + 字段说明发给用户自己配置的大模型（OpenAI 兼容接口），模型只返回一份新的 JSON 方案，
  这里按字段说明检查、裁剪后再交给用户「采用」（采用 = 存成新版本 + 渲染预览）。
  接口地址和模型名存在 douyin/web/llm.json，密钥只存在用户环境变量 CC_PIANO_LLM_KEY 里（不写文件、不回传给网页）。

表情变体格式：{"base": 原片段名, "who": "male"|"female", "speed": 1.0, "scale": {"hop": 1, "lean": 1, "squash": 1},
              "set": {"eyes": ..., "mouth": ..., "arm_l": ..., "arm_r": ..., "legs": ..., "blush": true}, "fx": ["heart", ...],
              "note": "这一版改了什么"}
"""
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

from PIL import Image

import clawd_anim as ca
import visions

ROOT = Path(__file__).resolve().parent.parent
ANIM = ROOT / "assets" / "clawd" / "animations"
VARIANTS = ROOT / "assets" / "clawd" / "variants"
VIS_DIR = ROOT / "assets" / "clawd" / "visions"
SCENE_PREV = ROOT / "assets" / "scenes"
TPL = Path(__file__).resolve().parent / "templates"
LLM_CFG = ROOT / "web" / "llm.json"
KEY_ENV = "CC_PIANO_LLM_KEY"

EYES = ["open", "blink", "closed", "happy", "sad", "wide", "down", "look_l", "look_r", "look_up", "heart", "narrow"]
MOUTHS = ["closed", "smile", "grin", "open", "o", "frown"]
ARMS = ["down", "up", "out", "wave", "fist", "hold", "hug", "face"]
LEGS = ["stand", "step0", "step1", "sit", "stomp_l", "stomp_r"]
FX = ["tear", "heart", "spark", "steam", "note", "sweat"]


# ====================================================================== 透明动图（沿边缘裁剪）
def trimmed_webp(frames: list[Image.Image], path: Path, fps: int = 30, pad: int = 6) -> Path:
    """所有帧的不透明区域取并集，四周只留 pad 像素，存成循环播放的透明 webp。"""
    box = None
    for f in frames:
        b = f.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    if box:
        w, h = frames[0].size
        box = (max(0, box[0] - pad), max(0, box[1] - pad), min(w, box[2] + pad), min(h, box[3] + pad))
        frames = [f.crop(box) for f in frames]
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, lossless=False,
                   quality=88, method=4)
    return path


# ====================================================================== 表情变体
def _versions(d: Path) -> list[int]:
    return sorted(int(p.stem[1:]) for p in d.glob("v*.json") if p.stem[1:].isdigit()) if d.is_dir() else []


def variant_pose(spec: dict, t: float) -> ca.Pose:
    base = ca.CLIPS[spec["base"]]
    p = base.pose(t * float(spec.get("speed", 1.0)))
    sc = spec.get("scale") or {}
    p = replace(p, hop=p.hop * float(sc.get("hop", 1)), lean=p.lean * float(sc.get("lean", 1)),
                squash=1 + (p.squash - 1) * float(sc.get("squash", 1)))
    sets = {k: v for k, v in (spec.get("set") or {}).items() if v is not None}
    if sets:
        p = replace(p, **sets)
    if spec.get("fx"):
        p = replace(p, fx=list(p.fx) + [(k, t / 1.3 + i * 0.37) for i, k in enumerate(spec["fx"])])
    return p


def variant_frames(spec: dict, fps: int = 30) -> list[Image.Image]:
    base = ca.CLIPS[spec["base"]]
    dur = base.duration / max(float(spec.get("speed", 1.0)), 0.1)
    dur = dur * (2 if base.loop and dur < 1.5 else 1)
    look = ca.LOOKS[spec.get("who", base.cast[0])]
    out = []
    for i in range(max(2, round(dur * fps))):
        p = variant_pose(spec, i / fps)
        canvas = Image.new("RGBA", (360, 300), (0, 0, 0, 0))
        sh = ca.shadow(p, 5)
        shade = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        shade.putalpha(sh)
        ca._put(canvas, shade, (180 - sh.width / 2, 260 - sh.height / 2))
        im, (fx, fy) = ca.render(p, 5, look)
        ca._put(canvas, im, (180 - fx, 260 - fy))
        ca.draw_fx(canvas, p, (180, 260), 5)
        out.append(canvas)
    return out


# ====================================================================== 列表
def _url(p: Path, media_url) -> str | None:
    return media_url(p) + f"&v={int(p.stat().st_mtime)}" if p.exists() else None


def ensure_trimmed(who: str, name: str) -> Path:
    """原片段的裁边透明动图（没有时现做，几秒）。"""
    path = ANIM / who / f"{name}.webp"
    if not path.exists():
        c = ca.CLIPS[name]
        dur = c.duration * (2 if c.loop and c.duration < 1.5 else 1)
        trimmed_webp([ca.frame(name, i / 30, look=ca.LOOKS[who]) for i in range(max(2, round(dur * 30)))], path)
    return path


def listing(media_url) -> dict:
    chars = {}
    for who in ("male", "female"):
        items = []
        for name, c in ca.CLIPS.items():
            if who not in c.cast:
                continue
            vdir = VARIANTS / who / name
            vs = _versions(vdir)
            prev = vdir / f"v{vs[-1]}.webp" if vs else ANIM / who / f"{name}.webp"
            items.append({"kind": "clip", "who": who, "name": name, "zh": c.zh, "mood": name in ca.MOODS,
                          "duration": c.duration, "versions": vs, "preview": _url(prev, media_url),
                          "webm": _url(ANIM / who / f"{name}.webm", media_url),
                          "note": json.loads((vdir / f"v{vs[-1]}.json").read_text(encoding="utf-8")).get("note", "")
                          if vs else ""})
        chars[who] = items
    vis = [{"kind": "vision", "name": n, "zh": zh, "preview": _url(VIS_DIR / f"{n}.webp", media_url)
            or _url(VIS_DIR / f"{n}.gif", media_url)} for n, (_, zh) in visions.VISIONS.items() if n not in visions.HD]
    # 手绘（douyin/handdrawn 工作室）：表情按男生 / 女生，画面按歌
    hd = {}
    idx = ROOT / "assets" / "clawd" / "handdrawn" / "index.json"
    zh_of = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    for who in ("male", "female"):
        d = ROOT / "assets" / "clawd" / "handdrawn" / who
        hd[f"hd_{who}"] = [{"kind": "handdrawn", "who": who, "name": p.stem, "zh": zh_of.get(who, {}).get(p.stem, ""),
                            "preview": _url(p, media_url)} for p in sorted(d.glob("*.webp"))] if d.is_dir() else []
    hd["hd_scenes"] = [{"kind": "handdrawn", "name": n, "zh": f"{h['zh']}（{h['song']}）", "preview": _url(h["preview"], media_url)}
                       for n, h in visions.HD.items()]
    scenes = {}
    for kind in ("opening", "ending"):
        rows = []
        for d in sorted(p for p in (TPL / kind).iterdir() if p.is_dir()) if (TPL / kind).is_dir() else []:
            vs = _versions(d)
            if not vs:
                continue
            latest = json.loads((d / f"v{vs[-1]}.json").read_text(encoding="utf-8"))
            rows.append({"kind": kind, "name": d.name, "versions": vs, "note": latest.get("note", ""),
                         "preview": _url(SCENE_PREV / kind / f"{d.name}_v{vs[-1]}.mp4", media_url),
                         "poster": _url(SCENE_PREV / kind / f"{d.name}_v{vs[-1]}.jpg", media_url)})
        scenes[kind] = rows
    return {"characters": chars, "visions": vis, **hd, **scenes, "llm": llm_public()}


def current(kind: str, name: str, who: str = "male", version: int | None = None) -> dict:
    """某个条目当前（或指定版本）的 JSON。"""
    if kind == "clip":
        vdir = VARIANTS / who / name
        vs = _versions(vdir)
        if vs:
            return json.loads((vdir / f"v{version or vs[-1]}.json").read_text(encoding="utf-8"))
        return {"base": name, "who": who, "speed": 1.0, "scale": {"hop": 1, "lean": 1, "squash": 1}, "set": {},
                "fx": [], "note": "原始片段"}
    d = TPL / kind / name
    vs = _versions(d)
    if not vs:
        raise FileNotFoundError(f"没有这个{kind}：{name}")
    return json.loads((d / f"v{version or vs[-1]}.json").read_text(encoding="utf-8"))


# ====================================================================== 检查方案（模型给的 JSON 不可信）
def _num(v, lo, hi, default):
    try:
        return min(hi, max(lo, float(v)))
    except (TypeError, ValueError):
        return default


def clean(kind: str, data: dict, base: dict) -> dict:
    """按字段说明裁剪：只留认识的字段，数值夹在范围里，枚举值不认识就丢掉。"""
    if not isinstance(data, dict):
        raise ValueError("方案不是 JSON 对象")
    if kind == "clip":
        out = {"base": data.get("base") if data.get("base") in ca.CLIPS else base["base"],
               "who": base["who"], "speed": _num(data.get("speed", base.get("speed", 1)), 0.25, 3, 1.0)}
        sc = data.get("scale") or {}
        out["scale"] = {k: _num(sc.get(k, 1), 0, 3, 1.0) for k in ("hop", "lean", "squash")}
        allowed = {"eyes": EYES, "mouth": MOUTHS, "arm_l": ARMS, "arm_r": ARMS, "legs": LEGS}
        st = {}
        for k, v in (data.get("set") or {}).items():
            if k in allowed and v in allowed[k]:
                st[k] = v
            elif k == "blush" and isinstance(v, bool):
                st[k] = v
        out["set"] = st
        out["fx"] = [f for f in (data.get("fx") or []) if f in FX][:4]
        out["note"] = str(data.get("note") or "")[:200]
        return out
    out = json.loads(json.dumps(base))                     # 开头 / 结尾：在当前脚本上逐项覆盖认识的字段
    def merge(dst, src, path=""):
        for k, v in src.items():
            if k not in dst:
                continue
            if isinstance(dst[k], dict) and isinstance(v, dict):
                merge(dst[k], v, path + k + ".")
            elif isinstance(dst[k], list) and isinstance(v, list):
                if path.startswith("beats") or path == "beats.":
                    if len(v) == 2:
                        a, b = _num(v[0], 0, 1, dst[k][0]), _num(v[1], 0, 1, dst[k][1])
                        dst[k] = [round(min(a, b), 3), round(max(a, b), 3)]
                else:
                    dst[k] = [str(x)[:80] for x in v][:12]
            elif isinstance(dst[k], (int, float)) and not isinstance(dst[k], bool):
                dst[k] = _num(v, 0, 1, dst[k])
            elif isinstance(dst[k], str):
                dst[k] = str(v)[:200]
    merge(out, data)
    if kind == "opening" and out.get("vision") not in visions.VISIONS:
        out["vision"] = base.get("vision", "reader_smile")
    return out


# ====================================================================== 保存 + 预览
def save(kind: str, name: str, data: dict, who: str = "male") -> int:
    d = VARIANTS / who / name if kind == "clip" else TPL / kind / name
    vs = _versions(d)
    ver = (vs[-1] + 1) if vs else 1
    d.mkdir(parents=True, exist_ok=True)
    (d / f"v{ver}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return ver


def render_preview(kind: str, name: str, version: int, who: str = "male", progress=None) -> Path:
    """渲染预览：表情 → 裁边透明 webp；开头 / 结尾 → 960×540 小视频 + 封面图。"""
    if kind == "clip":
        spec = current(kind, name, who, version)
        return trimmed_webp(variant_frames(spec), VARIANTS / who / name / f"v{version}.webp")
    import imageio_ffmpeg
    import numpy as np
    import flick_lib
    script = current(kind, name, version=version)
    out = SCENE_PREV / kind / f"{name}_v{version}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    others, final = flick_lib.sequence()
    fps, size = 24, (960, 540)
    if kind == "opening":
        import opening
        seconds = 19.0
        op = opening.Opening(script, final, others, seconds, fps, "歌名 Song Title", "歌手 Artist")
        frame = lambda t: op.frame(t)               # noqa: E731
    else:
        import ending
        seconds = 10.0
        e = ending.HomeEnding(script, Image.open(final), "歌名 Song Title", "歌手 Artist", 0.0, seconds)

        def frame(t):
            im = Image.new("RGB", (1920, 1080), (40, 36, 52))
            e(im, t)
            return im
    w = imageio_ffmpeg.write_frames(str(out), size, fps=fps, codec="libx264", pix_fmt_out="yuv420p", quality=None,
                                    output_params=["-crf", "23", "-preset", "fast"], macro_block_size=1,
                                    ffmpeg_log_level="error")
    w.send(None)
    n = int(seconds * fps)
    for i in range(n):
        im = frame(i / fps).resize(size, Image.BILINEAR)
        if i == int(n * 0.45):
            im.save(out.with_suffix(".jpg"), quality=86)
        w.send(np.asarray(im).tobytes())
        if progress and i % 12 == 0:
            progress(i / n)
    w.close()
    return out


# ====================================================================== 聊天设计（用户自己的大模型）
def llm_cfg() -> dict:
    cfg = {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"}
    if LLM_CFG.exists():
        cfg.update(json.loads(LLM_CFG.read_text(encoding="utf-8")))
    return cfg


def llm_key() -> str:
    key = os.environ.get(KEY_ENV, "")
    if not key and os.name == "nt":                          # 刚在设置里填的：从用户环境变量读（当前进程还没有）
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, KEY_ENV)[0]
        except OSError:
            key = ""
    return key


def llm_public() -> dict:
    c = llm_cfg()
    return {"base_url": c["base_url"], "model": c["model"], "has_key": bool(llm_key()), "key_env": KEY_ENV}


def set_llm(base_url: str, model: str, key: str | None) -> dict:
    if not re.match(r"^https?://", base_url or ""):
        raise ValueError("接口地址要以 http:// 或 https:// 开头")
    LLM_CFG.write_text(json.dumps({"base_url": base_url.rstrip("/"), "model": model.strip() or "deepseek-chat"},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    if key:                                                   # 密钥写进用户环境变量（不写文件）
        os.environ[KEY_ENV] = key
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, KEY_ENV, 0, winreg.REG_SZ, key)
    return llm_public()


GUIDE = {
    "clip": ("这是一个像素小人的表情动画「变体」：在一段原始动画（base）上调速度和幅度、改表情和手势、加特效。\n"
             f"- base：原始片段名，可选 {list(ca.CLIPS)}\n- speed：播放速度 0.25~3\n"
             "- scale.hop / scale.lean / scale.squash：跳跃高度、身体倾斜、挤压拉伸的幅度倍数 0~3\n"
             f"- set（可选，写了就一直保持）：eyes 可选 {EYES}；mouth 可选 {MOUTHS}；arm_l / arm_r 可选 {ARMS}；"
             f"legs 可选 {LEGS}；blush 是 true/false\n- fx：额外特效，最多 4 个，可选 {FX}\n- note：一句话说明这一版改了什么"),
    "opening": ("这是视频开头小剧场「加班的夜」的脚本：夜空半月里浮现一条评论 → 镜头下摇进高楼办公室，男生读评论 → 读到那条评论（头顶想象云朵）"
                "→ 老板来电（乱码气泡）→ 难过 → 女朋友来电（粉色气泡）→ 拨片开头从右边拉进来，他下班离开。\n"
                "- comment：开头和他读到的那条评论\n"
                f"- vision：想象云朵里的画面，可选 {list(visions.VISIONS)}\n"
                "- boss.name / boss.lines：老板的称呼、电话里冒出来的乱码句子（像 ！……#（@……（！& 这样）\n"
                "- partner.name / partner.line：女朋友的称呼、她在电话里说的话\n"
                "- beats：每一段占整段开头的比例 [开始, 结束]（0~1），段名 comment / tilt / feel / boss / sad / partner / pan，"
                "顺序要合理、首尾相接\n- note：一句话说明这一版改了什么"),
    "ending": ("这是视频结尾小剧场「回家」的脚本：画面中间小窗里，男生回家，和女生在餐桌旁聊天，女生用网易云放这首歌，两人鞠躬，镜头推近直到消失。\n"
               "- chat.girl / chat.boy：两人聊天的两句话\n"
               "- beats：每一段占结尾的比例 [开始, 结束]（0~1），段名 enter / chat / play / listen / bow\n"
               "- zoom_from：从哪里开始镜头推近（0~1）；fade_from：从哪里开始变黑（0~1）\n- note：一句话说明这一版改了什么"),
}


def llm_complete(msgs: list[dict], temperature: float = 0.7) -> str:
    """调用用户配置的大模型（OpenAI 兼容 /chat/completions），返回回复文字。"""
    key = llm_key()
    if not key:
        raise PermissionError("还没有配置大模型：点右上角「API 设置」，填接口地址、模型和密钥")
    cfg = llm_cfg()
    req = urllib.request.Request(cfg["base_url"].rstrip("/") + "/chat/completions",
                                 json.dumps({"model": cfg["model"], "messages": msgs, "temperature": temperature}).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"大模型接口返回 {e.code}：{e.read().decode('utf-8', 'replace')[:200]}") from e
    except OSError as e:
        raise RuntimeError(f"连不上大模型接口：{e}") from e
    return data["choices"][0]["message"]["content"]


def chat(kind: str, name: str, message: str, history: list[dict], who: str = "male") -> dict:
    """发给用户配置的大模型，返回 {reply, proposal}（proposal 已检查裁剪；模型没给方案时为 None）。"""
    key = llm_key()
    if not key:
        raise PermissionError("还没有配置大模型：点右上角「API 设置」，填接口地址、模型和密钥")
    base = current(kind, name, who)
    system = ("你是 cc-piano 的动画设计助手，帮用户改一个动画。只能改下面说明里的字段。"
              "回答格式：先用一两句中文说明你打算怎么改，然后给一个 ```json 代码块，里面是完整的新 JSON（在当前 JSON 基础上修改）。"
              "如果用户只是在提问、不需要改，就只回答文字，不给代码块。\n\n" + GUIDE[kind] +
              "\n\n当前 JSON：\n```json\n" + json.dumps(base, ensure_ascii=False, indent=1) + "\n```")
    msgs = [{"role": "system", "content": system}]
    for h in history[-8:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": h["content"][:4000]})
    msgs.append({"role": "user", "content": message[:2000]})
    text = llm_complete(msgs)
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    proposal = None
    if m:
        try:
            proposal = clean(kind, json.loads(m.group(1)), base)
        except (ValueError, json.JSONDecodeError):
            proposal = None
    reply = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.S).strip() or "方案在下面，看看要不要采用。"
    return {"reply": reply, "proposal": proposal, "raw": text}


def export_all_trimmed() -> int:
    """给动画库补齐所有原片段和想象画面的裁边透明动图。"""
    n = 0
    for who in ("male", "female"):
        for name, c in ca.CLIPS.items():
            if who in c.cast:
                p = ANIM / who / f"{name}.webp"
                if p.exists():
                    p.unlink()
                ensure_trimmed(who, name)
                n += 1
    for name in visions.VISIONS:
        trimmed_webp([visions.draw(name, i / 15) for i in range(45)], VIS_DIR / f"{name}.webp", fps=15)
        n += 1
    return n


if __name__ == "__main__":
    print("裁边透明动图：", export_all_trimmed())
    for kind in ("opening", "ending"):
        for d in sorted(p for p in (TPL / kind).iterdir() if p.is_dir()):
            vs = _versions(d)
            if vs and not (SCENE_PREV / kind / f"{d.name}_v{vs[-1]}.mp4").exists():
                print(kind, d.name, "预览：", render_preview(kind, d.name, vs[-1]))
