"""每日数据报表（每天 12:00）：读创作者中心 → 和前一天的快照比 → 找问题、给改进建议 → 发飞书群 + 存档 + 写进知识库。

所有数字都来自创作者中心的快照（fetch_creator.py），不估算、不编；建议是按下面写明的规则从数字推出来的，
标注「待验证」，由下周的实验来验证。
用法: douyin\\.venv\\Scripts\\python workflow\\daily\\report.py [--no-fetch] [--no-send]
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_creator  # noqa: E402
import notify  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "workflow" / "reports" / "daily"
KB = ROOT / "workflow" / "llm-wiki" / "resource" / "auto-douyin-knowledges" / "raw" / "sources"

# 判断规则（阈值写在这里，改规则只改这里）
BOUNCE_HIGH = 0.40        # 2 秒跳出率高于这个：开头留不住人
FIVE_LOW = 0.30           # 5 秒完播率低于这个：前 5 秒没有让人想继续看的东西
VIEW_SHARE_LOW = 0.15     # 平均只看了全片的这个比例以下：中段没有钩子


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def previous(snaps: list[Path], now: datetime) -> dict | None:
    """前一天的快照：最接近 24 小时前、且至少 12 小时前的一份。"""
    best = None
    for p in snaps:
        t = datetime.fromisoformat(load(p)["time"])
        if now - t >= timedelta(hours=12):
            if best is None or abs((now - t) - timedelta(hours=24)) < abs((now - best[0]) - timedelta(hours=24)):
                best = (t, p)
    return load(best[1]) if best else None


def analyse(snap: dict, prev: dict | None) -> dict:
    items = sorted(snap["items"], key=lambda i: i["create_time"], reverse=True)
    old = {i["id"]: i for i in (prev or {}).get("items", [])}
    rows = []
    for it in items:
        m = it["metrics"]
        o = old.get(it["id"])
        rows.append({**it, "m": m, "d_play": it["play"] - o["play"] if o else None,
                     "d_like": it["like"] - o["like"] if o else None,
                     "fans": m.get("subscribe_count", 0)})
    n = len(rows) or 1
    avg = lambda k: sum(r["m"].get(k, 0) for r in rows) / n     # noqa: E731
    return {"rows": rows, "total_play": sum(r["play"] for r in rows),
            "d_total": sum(r["d_play"] for r in rows if r["d_play"] is not None) if prev else None,
            "fans": sum(r["fans"] for r in rows), "completion": avg("completion_rate"),
            "five": avg("completion_rate_5s"), "bounce": avg("bounce_rate_2s"),
            "share": avg("avg_view_proportion"), "prev_time": prev["time"] if prev else None}


def template_desc() -> str:
    """默认模板和它的时长（从 workflow/config.json 和模板库读，不写死）。"""
    try:
        ref = json.loads((ROOT / "workflow" / "config.json").read_text(encoding="utf-8")).get("template", "")
        sys.path.insert(0, str(ROOT / "douyin" / "tracks"))
        import template_lib
        return f"{ref} 约 {float(template_lib.load(ref).get('duration', 0)):.0f} 秒"
    except Exception:                                  # 读不到模板时只说名字
        return "（没读到模板）"


def findings(a: dict) -> tuple[list[str], list[str]]:
    """问题 + 建议。每条都写明依据的数字。"""
    rows, probs, tips = a["rows"], [], []
    if not rows:
        return ["还没有作品数据"], []
    hi = [r for r in rows if r["m"].get("bounce_rate_2s", 0) > BOUNCE_HIGH]
    if hi:
        top = max(hi, key=lambda r: r["m"]["bounce_rate_2s"])
        probs.append(f"{len(hi)}/{len(rows)} 条的 2 秒跳出率超过 {pct(BOUNCE_HIGH, 0)}"
                     f"（最高：《{top['title'][:14]}》{pct(top['m']['bounce_rate_2s'])}）：开头 2 秒没留住人。")
        tips.append("开头 2 秒（待验证）：第一帧就出现「最戳人的那条评论」或歌曲最炸的一拍，拨片开头缩到 1 小节以内；"
                    "下周实验 A 组保持原样，B 组改冷开场，比 2 秒跳出率。")
    if a["five"] < FIVE_LOW:
        probs.append(f"条均 5 秒完播 {pct(a['five'])}（低于 {pct(FIVE_LOW, 0)}）：前 5 秒没有让人想继续看的悬念。")
        tips.append("前 5 秒（待验证）：小人第一次抽评论放到 3 秒内，评论只露一半、读完再全显示，制造「想看完这句」的悬念。")
    view = [(r["m"].get("avg_view_second", 0), r["duration"]) for r in rows if r["duration"]]
    if view and a["share"] < VIEW_SHARE_LOW:
        s = sum(v for v, _ in view) / len(view)
        d = sum(t for _, t in view) / len(view)
        probs.append(f"平均每人只看 {s:.1f} 秒（作品平均 {d:.0f} 秒，看了 {pct(a['share'], 0)}）：完播率 {pct(a['completion'])} 主要卡在这里。")
        tips.append(f"时长（待验证）：现在默认模板 {template_desc()}，平均观看只有 {s:.0f} 秒；可以试 30–40 秒的短版，"
                    "以及每 8–10 秒一个新评论或画面变化，不让中段平。")
    if len(rows) >= 3:
        by_c = sorted(rows, key=lambda r: r["m"].get("completion_rate", 0), reverse=True)
        best, worst = by_c[0], by_c[-1]
        probs.append(f"完播最好的是《{best['title'][:16]}》{pct(best['m'].get('completion_rate', 0))}（{best['duration']:.0f} 秒），"
                     f"最差的是《{worst['title'][:16]}》{pct(worst['m'].get('completion_rate', 0))}（{worst['duration']:.0f} 秒）。")
        by_l = max(rows, key=lambda r: r["m"].get("like_rate", 0))
        tips.append(f"选题（待验证）：点赞率最高的是《{by_l['title'][:16]}》{pct(by_l['m'].get('like_rate', 0))}，"
                    "可以多做同类情绪的歌，文案沿用它的写法。")
    return probs, tips


def markdown(a: dict, day: str) -> str:
    L = [f"## 📊 抖音日报 {day}", ""]
    d = f"（比昨天 +{a['d_total']}）" if a["d_total"] is not None else "（第一次记录，明天开始有变化量）"
    L += [f"- 作品 {len(a['rows'])} 条，总播放 **{a['total_play']}**{d}，累计涨粉 {a['fans']}",
          f"- 条均：完播 **{pct(a['completion'])}** · 5 秒完播 {pct(a['five'])} · 2 秒跳出 {pct(a['bounce'])} · "
          f"平均看完全片的 {pct(a['share'], 0)}", "", "**每条作品**"]
    for r in a["rows"]:
        m = r["m"]
        dp = f"（+{r['d_play']}）" if r["d_play"] is not None else ""
        L.append(f"- {datetime.fromtimestamp(r['create_time']):%m-%d} 《{r['title'][:20]}》{r['duration']:.0f}s：播放 {r['play']}{dp} · "
                 f"完播 {pct(m.get('completion_rate', 0))} · 5s {pct(m.get('completion_rate_5s', 0), 0)} · "
                 f"2s跳出 {pct(m.get('bounce_rate_2s', 0), 0)} · 平均看 {m.get('avg_view_second', 0):.1f}s · "
                 f"点赞率 {pct(m.get('like_rate', 0))} · 收藏 {r['collect']} · 涨粉 {r['fans']}")
    probs, tips = findings(a)
    L += ["", "**看出来的问题**"] + [f"- {p}" for p in probs]
    L += ["", "**改进建议**（从上面的数字推出来的，标「待验证」的放进下周实验）"] + [f"- {t}" for t in tips]
    return "\n".join(L)


def main() -> int:
    now = datetime.now()
    day = f"{now:%Y-%m-%d}"
    if "--no-fetch" not in sys.argv:
        try:
            fetch_creator.save(fetch_creator.fetch())
        except Exception as e:                               # 读不到时用最近一份快照，并在群里说明
            if "--no-send" not in sys.argv:
                notify.send_markdown(f"⚠️ 日报：创作者中心数据没读到（{e}），用最近一份快照。", key=f"report-warn-{day}")
    snaps = fetch_creator.snapshots()
    if not snaps:
        print("没有快照")
        return 1
    snap = load(snaps[-1])
    a = analyse(snap, previous(snaps[:-1], datetime.fromisoformat(snap["time"])))
    text = markdown(a, day) + f"\n\n数据时间：{snap['time'].replace('T', ' ')}"
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{day}.md").write_text(text, encoding="utf-8")
    (REPORTS / f"{day}.json").write_text(json.dumps(a, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    try:
        sys.path.insert(0, str(ROOT / "douyin" / "data"))
        import db as studioDb
        studioDb.save_daily_report(day, a, text)
    except Exception:
        pass
    if KB.is_dir():
        (KB / f"抖音日报-{day}.md").write_text(text.replace("## 📊 ", "# "), encoding="utf-8")
    if "--no-send" not in sys.argv:
        notify.send_markdown(text, key=f"daily-report-{day}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
