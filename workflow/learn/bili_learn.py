"""学习环节：用未登录的独立浏览器资料（workflow/learn/profile）在 B 站看同类视频，收集数据和截图，给运营分析用。

- 按关键词搜索（综合排序 + 最多播放），记下每条视频的标题、播放、弹幕、时长、UP 主、发布时间、链接；
- 播放量最高的若干条打开详情页：简介、标签、点赞 / 投币 / 收藏 / 分享 / 评论数、热门评论，
  并在 1s / 3s / 8s / 中间 / 结尾前截播放器画面（看开头怎么抓人、画面什么风格）；
- 结果写 workflow/learn/<日期>/：videos.json、details.json、frames/<BV号>_<秒>.jpg。
只读，不登录、不点赞不评论。抖音网页版未登录会出滑块验证码，不自动绕过。
用法: douyin\\.venv\\Scripts\\python workflow\\learn\\bili_learn.py [--top 25]
"""
import argparse
import json
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "profile"
QUERIES = ["claude 音乐", "claude 小曲", "claude 写歌", "claude code 音乐", "claude 作曲", "AI 作曲 编程",
           "音轨拆解", "分轨 人声 吉他 贝斯", "编曲 拆解", "网易云评论 歌曲", "像素 小人 音乐", "claude code 做视频"]


def num(s: str) -> float:
    s = (s or "").strip()
    m = re.match(r"([\d.]+)\s*(万|亿)?", s)
    if not m:
        return 0.0
    v = float(m.group(1))
    return v * (1e4 if m.group(2) == "万" else 1e8 if m.group(2) == "亿" else 1)


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def search(page, q: str, order: str) -> list[dict]:
    url = "https://search.bilibili.com/video?keyword=" + urllib.parse.quote(q) + (f"&order={order}" if order else "")
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(4500)
    for _ in range(3):
        page.mouse.wheel(0, 1600)
        page.wait_for_timeout(700)
    cards = page.evaluate("""() => [...document.querySelectorAll('.bili-video-card')].map(c => {
        const a = c.querySelector('a[href*="/video/BV"]');
        const st = [...c.querySelectorAll('.bili-video-card__stats--item span')].map(x => x.textContent.trim());
        const q = (s) => (c.querySelector(s) || {}).textContent || '';
        return { href: a ? a.href : '', title: (c.querySelector('.bili-video-card__info--tit') || {}).title || q('h3'),
                 play: st[0] || '', danmaku: st[1] || '', duration: q('.bili-video-card__stats__duration').trim(),
                 author: q('.bili-video-card__info--author').trim(), date: q('.bili-video-card__info--date').replace('·', '').trim() };
    })""")
    out = []
    for c in cards:
        m = re.search(r"(BV\w{10})", c["href"])
        if m:
            out.append({**c, "bv": m.group(1), "play_n": num(c["play"]), "query": q, "order": order or "综合"})
    return out


def detail(page, bv: str, frames_dir: Path) -> dict:
    replies = []

    def on_resp(r):
        if "/x/v2/reply" in r.url:
            try:
                d = r.json().get("data") or {}
                for x in (d.get("replies") or [])[:15]:
                    replies.append({"like": x.get("like"), "text": (x.get("content") or {}).get("message", "")[:200]})
            except Exception:
                pass
    page.on("response", on_resp)
    page.goto(f"https://www.bilibili.com/video/{bv}", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    info = page.evaluate("""() => { const s = window.__INITIAL_STATE__ || {}; const v = s.videoData || {};
        return { title: v.title, desc: v.desc, duration: v.duration, pubdate: v.pubdate, owner: (v.owner || {}).name,
                 stat: v.stat, tags: (s.tags || []).map(t => t.tag_name) }; }""")
    page.mouse.wheel(0, 1400)                    # 往下滚，触发评论加载
    page.wait_for_timeout(3500)
    page.mouse.wheel(0, -1400)
    page.wait_for_timeout(800)
    dur = float(info.get("duration") or 0)
    shots = []
    for t in sorted({1.0, 3.0, 8.0, round(dur * 0.5, 1), round(max(dur - 6, 1), 1)}):
        if dur and t >= dur:
            continue
        try:
            page.evaluate("""(t) => { const v = document.querySelector('video'); if (v) { v.muted = true; v.currentTime = t; v.pause(); } }""", t)
            page.wait_for_timeout(1800)
            el = page.query_selector(".bpx-player-video-wrap") or page.query_selector("video")
            if el:
                p = frames_dir / f"{bv}_{int(t):04d}.jpg"
                el.screenshot(path=str(p), type="jpeg", quality=80)
                shots.append(p.name)
        except Exception as e:
            log(f"  截图失败 {bv} {t}s：{e}")
    page.remove_listener("response", on_resp)
    return {**info, "bv": bv, "top_comments": sorted(replies, key=lambda x: -(x.get("like") or 0))[:10], "frames": shots}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    day = ROOT / f"{datetime.now():%Y-%m-%d}"
    (day / "frames").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=True,
                                                    viewport={"width": 1400, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        allv = {}
        for q in QUERIES:
            for order in ("", "click"):
                try:
                    res = search(page, q, order)
                except Exception as e:
                    log(f"搜索失败 {q} {order}：{e}")
                    continue
                for v in res:
                    allv.setdefault(v["bv"], {**v, "queries": []})["queries"].append(f"{q}/{v['order']}")
                log(f"搜索「{q}」{order or '综合'}：{len(res)} 条（累计 {len(allv)}）")
        (day / "videos.json").write_text(json.dumps(list(allv.values()), ensure_ascii=False, indent=1), encoding="utf-8")
        top = sorted(allv.values(), key=lambda v: -v["play_n"])[: a.top]
        details = []
        for i, v in enumerate(top, 1):
            try:
                details.append({**detail(page, v["bv"], day / "frames"), "queries": v["queries"]})
                log(f"[{i}/{len(top)}] {v['play']} {v['title'][:40]}")
            except Exception as e:
                log(f"[{i}] 详情失败 {v['bv']}：{e}")
            (day / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=1), encoding="utf-8")
        ctx.close()
    log(f"完成：{len(allv)} 条视频，{len(details)} 条详情（{(time.time() - t0) / 60:.0f} 分钟）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
