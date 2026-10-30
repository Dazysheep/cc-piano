"""剪辑过程记录：OpenFilm Studio 每次改动都会写回工程的 film.html，这里把每一个版本都留下来。

每个工程（成片文件夹里的 film/）有一个 .cc-history/：
  <时间>.html     那一刻的 film.html 全文
  log.jsonl       每行一条：{"id", "time", "summary"（改了什么，用片段的说法）, "restored_from"?}
琴房服务启动后由 watch() 在后台每秒检查一次所有工程；恢复到某一步（restore）会把那一版写回 film.html，
这本身也记成新的一步，所以任何操作都可以再撤回来。OpenFilm 自己的「命名版本」（git）照常可用，两者互不影响。
"""
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

HIST = ".cc-history"
CLIP_RE = re.compile(r"<(video|audio|img|iframe)\b([^>]*)>", re.I)
ATTR_RE = re.compile(r'([\w-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')


def _clips(doc: str) -> dict[str, dict]:
    """film.html 里的片段：{id: {tag, track, 属性…}}。"""
    out = {}
    for k, sec in enumerate(re.split(r"<section\b", doc)[1:]):
        for m in CLIP_RE.finditer(sec):
            attrs = {a.group(1): a.group(3) if a.group(3) is not None else a.group(4) for a in ATTR_RE.finditer(m.group(2))}
            cid = attrs.get("id") or Path(attrs.get("src", "?").split("#")[0]).name
            out[cid] = {"tag": m.group(1).lower(), "track": k + 1, **attrs}
    return out


NAMES = {"src": "截取/素材", "at": "位置", "volume": "音量", "speed": "速度", "style": "画面位置/样式",
         "overrides": "淡入淡出/调整", "track": "轨道", "class": "样式"}


def summary(old: str | None, new: str) -> str:
    """两版 film.html 的差别，用「片段」的说法描述。"""
    if old is None:
        return "开始记录"
    a, b = _clips(old), _clips(new)
    parts = [f"新增 {cid}" for cid in b if cid not in a] + [f"删除 {cid}" for cid in a if cid not in b]
    for cid in b:
        if cid in a and a[cid] != b[cid]:
            keys = sorted({k for k in a[cid].keys() | b[cid].keys() if a[cid].get(k) != b[cid].get(k)})
            parts.append(f"{cid}：改了" + "、".join(NAMES.get(k, k) for k in keys))
    if not parts:
        parts.append("改了全局样式或画面设置")
    return "；".join(parts)


def _log(film: Path) -> Path:
    return film / HIST / "log.jsonl"


def history(film: Path) -> list[dict]:
    p = _log(film)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def snapshot(film: Path, restored_from: str | None = None) -> dict | None:
    """film.html 和最近一版不同时存一版，返回这条记录；没变化返回 None。"""
    doc_path = film / "film.html"
    if not doc_path.exists():
        return None
    doc = doc_path.read_text(encoding="utf-8")
    hist = history(film)
    last = (film / HIST / f"{hist[-1]['id']}.html").read_text(encoding="utf-8") if hist else None
    if last == doc:
        return None
    now = datetime.now()
    sid = now.strftime("%Y%m%d_%H%M%S_%f")
    (film / HIST).mkdir(exist_ok=True)
    (film / HIST / f"{sid}.html").write_text(doc, encoding="utf-8")
    rec = {"id": sid, "time": now.strftime("%Y-%m-%d %H:%M:%S"), "summary": summary(last, doc)}
    if restored_from:
        rec["restored_from"] = restored_from
        rec["summary"] = f"恢复到 {restored_from}：" + rec["summary"]
    with open(_log(film), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def restore(film: Path, sid: str) -> dict | None:
    src = film / HIST / f"{sid}.html"
    if not src.exists():
        raise FileNotFoundError(f"没有这一步：{sid}")
    snapshot(film)                                   # 先把当前状态记下来，恢复操作本身也能撤回
    (film / "film.html").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return snapshot(film, restored_from=sid)


def watch(roots_fn, every: float = 3.0) -> threading.Thread:
    """后台线程：每隔 every 秒给 roots_fn() 列出的所有工程各存一次（有变化才存）。"""
    def loop():
        while True:
            for film in roots_fn():
                try:
                    snapshot(film)
                except OSError:
                    pass
            time.sleep(every)
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th
