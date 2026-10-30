"""每周六 18:00 的周报 PPT：读创作者中心（最新快照）→ 本周数据 + 问题 + 下周实验 → ppt/weekly.js 生成 PPT → 发飞书群 + 写进知识库。

数字全部来自快照；「问题」和「建议」沿用日报的规则（report.findings）。
用法: douyin\\.venv\\Scripts\\python workflow\\daily\\weekly.py [--no-fetch] [--no-send]
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_creator  # noqa: E402
import notify  # noqa: E402
import report  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PPT = ROOT / "ppt"

# 下周实验（在现有模板上改一处，A/B 对比；不照抄别人的视频，主题始终是音轨）
EXPERIMENTS = [
    {"name": "冷开场", "change": "拨片开头缩到 1 小节，第一帧就是最戳人的那条评论", "metric": "2 秒跳出率", "why": "bounce"},
    {"name": "短版", "change": "同一首歌出 35 秒版和 60 秒版，隔天各发一条", "metric": "完播率、平均观看秒数", "why": "share"},
    {"name": "3 秒内抽评论", "change": "小人第一次抽评论提前到 3 秒内，评论读完才完整显示", "metric": "5 秒完播率", "why": "five"},
]
DONE = [
    "模板库：daw v3 横屏 60 秒卡点、v4 拨片开头去字（版本都保留，可随时调用）",
    "CC 小人读评论：网易云评论文件夹 + 17 段立体动画（单独保存）",
    "剪辑页：OpenFilm 剪辑器接进 cc-piano，每一步剪辑都自动保存、可回退",
    "评论层单独输出透明视频，剪辑器里能单独调整",
    "每日流程：飞书群收录屏 → 自动识别歌曲出片 → 22 点发布提醒；12 点数据日报",
]


def week_range(now: datetime) -> tuple[datetime, datetime]:
    """本周 = 上周日 0 点 到 本周六 24 点（周六晚上出周报）。"""
    start = (now - timedelta(days=(now.weekday() + 1) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def collect(snap: dict, prev: dict | None, now: datetime) -> dict:
    a = report.analyse(snap, prev)
    probs, tips = report.findings(a)
    start, end = week_range(now)
    rows = []
    for r in a["rows"]:
        m = r["m"]
        t = datetime.fromtimestamp(r["create_time"])
        rows.append({"title": r["title"][:18], "date": f"{t:%m-%d}", "this_week": start <= t < end,
                     "duration": r["duration"], "play": r["play"], "like": r["like"], "collect": r["collect"],
                     "share": r["share"], "comment": r["comment"], "fans": r["fans"],
                     "completion": m.get("completion_rate", 0), "five": m.get("completion_rate_5s", 0),
                     "bounce": m.get("bounce_rate_2s", 0), "view_sec": m.get("avg_view_second", 0),
                     "like_rate": m.get("like_rate", 0)})
    return {"title": f"抖音周报 {start:%m.%d}–{(end - timedelta(days=1)):%m.%d}", "generated": f"{now:%Y-%m-%d %H:%M}",
            "data_time": snap["time"].replace("T", " "), "account": "cc的音乐引擎",
            "rows": rows, "week_count": sum(r["this_week"] for r in rows),
            "total_play": a["total_play"], "fans": a["fans"], "completion": a["completion"], "five": a["five"],
            "bounce": a["bounce"], "share": a["share"], "problems": probs, "tips": tips,
            "experiments": EXPERIMENTS, "done": DONE,
            "has_prev": prev is not None, "d_total": a["d_total"]}


def main() -> int:
    now = datetime.now()
    if "--no-fetch" not in sys.argv:
        try:
            fetch_creator.save(fetch_creator.fetch())
        except Exception as e:
            print("创作者中心没读到，用最近一份快照：", e)
    snaps = fetch_creator.snapshots()
    if not snaps:
        print("没有快照")
        return 1
    snap = report.load(snaps[-1])
    data = collect(snap, report.previous(snaps[:-1], datetime.fromisoformat(snap["time"])), now)
    out_dir = PPT / "output"
    data_dir = PPT / "data"
    data_dir.mkdir(exist_ok=True)
    js = data_dir / f"weekly-{now:%Y-%m-%d}.json"
    js.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    pptx = out_dir / f"抖音周报_{now:%Y-%m-%d}.pptx"
    r = subprocess.run(["node", "weekly.js", str(js), str(pptx)], cwd=PPT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stdout, r.stderr)
        return 1
    md = [f"# {data['title']}", "", f"数据时间：{data['data_time']}", "",
          f"- 作品 {len(data['rows'])} 条（本周发布 {data['week_count']} 条），总播放 {data['total_play']}，涨粉 {data['fans']}",
          f"- 条均完播 {report.pct(data['completion'])}，5 秒完播 {report.pct(data['five'])}，2 秒跳出 {report.pct(data['bounce'])}",
          "", "## 问题"] + [f"- {p}" for p in data["problems"]] + ["", "## 下周实验"] + \
         [f"- {e['name']}：{e['change']}（看{e['metric']}）" for e in data["experiments"]]
    if report.KB.is_dir():
        (report.KB / f"抖音周报-{now:%Y-%m-%d}.md").write_text("\n".join(md), encoding="utf-8")
    if "--no-send" not in sys.argv:
        notify.send_markdown("\n".join(md).replace("# ", "## 📈 ", 1) + "\n\nPPT 在下面 👇", key=f"weekly-{now:%Y-%m-%d}")
        notify.send_file(pptx, key=f"weekly-ppt-{now:%Y-%m-%d}")
    print(pptx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
