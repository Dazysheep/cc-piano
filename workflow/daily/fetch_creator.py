"""从抖音创作者中心读取每条作品的数据，存一份快照（日报、周报都从快照算）。

用发布台登录过的浏览器资料（douyin/publish/profile，Edge 无界面模式），只读，不点任何按钮。
发布台正开着时资料目录被占用，会读取失败，等发布台关掉再跑。

快照：workflow/data/creator/<日期_时分>.json
  {"time": ..., "items": [{"id", "title", "create_time", "duration", "play", "like", "comment", "share", "collect",
                          "metrics": {完整指标：completion_rate、completion_rate_5s、bounce_rate_2s、avg_view_second …}}]}
用法: douyin\\.venv\\Scripts\\python workflow\\daily\\fetch_creator.py [--quiet]
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "douyin" / "publish" / "profile"
OUT = ROOT / "workflow" / "data" / "creator"

sys.path.insert(0, str(ROOT / "douyin" / "data"))
import db as studioDb  # noqa: E402
MANAGE = "https://creator.douyin.com/creator-micro/content/manage"

WORK_LIST = """async (cursor) => {
  const r = await fetch('/janus/douyin/creator/pc/work_list?status=0&count=20&max_cursor=' + cursor +
                        '&scene=star_atlas&device_platform=android&aid=1128', {credentials: 'include'});
  return await r.text();
}"""
METRICS = """async (ids) => {
  const r = await fetch('/web/api/creator/item/mget?ids=' + ids + '&fields=metrics', {credentials: 'include'});
  return await r.text();
}"""


class NotLoggedIn(RuntimeError):
    pass


def _works(page) -> list[dict]:
    works, cursor = [], 0
    for _ in range(20):                                   # 最多 400 条
        d = json.loads(page.evaluate(WORK_LIST, str(cursor)))
        works += d.get("aweme_list") or []
        if not d.get("has_more"):
            break
        cursor = d.get("max_cursor") or 0
    return works


def _metrics(page, ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 10):
        d = json.loads(page.evaluate(METRICS, ",".join(ids[i:i + 10])))
        for it in d.get("items") or []:
            out[str(it["id"])] = {k: _num(v) for k, v in (it.get("metrics") or {}).items()}
    return out


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() and "." not in str(v) else f
    except (TypeError, ValueError):
        return v


def fetch() -> dict:
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=True)
        except PWError as e:
            raise RuntimeError("浏览器资料被占用（发布台开着？）或 Edge 打不开：" + str(e).splitlines()[0]) from e
        try:
            page = ctx.new_page()
            page.goto(MANAGE, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            if "login" in page.url or "creator-micro" not in page.url:
                raise NotLoggedIn("抖音创作者中心没有登录，请在发布台登录一次")
            works = _works(page)
            metrics = _metrics(page, [str(w["aweme_id"]) for w in works])
        finally:
            ctx.close()
    items = []
    for w in works:
        s = w.get("statistics") or {}
        aid = str(w["aweme_id"])
        items.append({
            "id": aid, "title": (w.get("item_title") or w.get("desc") or "").strip(),
            "desc": w.get("desc") or "", "create_time": int(w.get("create_time") or 0),
            "duration": round((w.get("duration") or (w.get("video") or {}).get("duration") or 0) / 1000, 1),
            "play": s.get("play_count", 0), "like": s.get("digg_count", 0), "comment": s.get("comment_count", 0),
            "share": s.get("share_count", 0), "collect": s.get("collect_count", 0),
            "metrics": metrics.get(aid, {}),
        })
    return {"time": datetime.now().isoformat(timespec="seconds"), "items": items}


def save(snap: dict) -> Path:
    try:
        studioDb.save_creator_snapshot(snap)
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def snapshots() -> list[Path]:
    return sorted(OUT.glob("*.json")) if OUT.is_dir() else []


if __name__ == "__main__":
    t0 = time.time()
    snap = fetch()
    path = save(snap)
    if "--quiet" not in sys.argv:
        for it in snap["items"]:
            m = it["metrics"]
            print(f"{it['play']:>6} 播放  完播 {m.get('completion_rate', 0) * 100:5.1f}%  "
                  f"2s跳出 {m.get('bounce_rate_2s', 0) * 100:4.1f}%  {it['title'][:24]}")
    print(f"{len(snap['items'])} 条作品 → {path} ({time.time() - t0:.0f}s)")
