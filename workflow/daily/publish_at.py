"""每晚 22:00 启动：等到 22:00–22:30 之间的随机时刻 → 打开填好的抖音发布页 → 飞书通知你检查后点「发布」。

不会替你点发布：发布台（douyin/publish/publisher.py）本来就停在「发布」按钮前。
用法（在 D:\\cc-engine 下）:
  douyin\\.venv\\Scripts\\python workflow\\daily\\publish_at.py          正常运行（计划任务 22:00 调用）
  douyin\\.venv\\Scripts\\python workflow\\daily\\publish_at.py --now    不等随机时间，立刻打开（测试用）
当天的随机时间只生成一次，记在 workflow\\data\\publish\\<日期>.json，重跑不会换时间、不会重复打开。
要发的是收件箱里最近一条「已做好」（ready）的视频；标题和话题来自歌曲 json，
有 workflow\\learn\\hotwords.json 时补进热词话题（最多 5 个）。
"""
import argparse
import json
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\cc-engine")
DOUYIN = ROOT / "douyin"
WF = ROOT / "workflow"
sys.path.insert(0, str(WF))
sys.path.insert(0, str(DOUYIN / "data"))
import notify  # noqa: E402
import db as studioDb  # noqa: E402

PY = DOUYIN / ".venv" / "Scripts" / "python.exe"
STATE = WF / "data" / "inbox.json"
HOTWORDS = WF / "learn" / "hotwords.json"
LOGS = WF / "logs"


def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOGS / f"publish_{datetime.now():%Y-%m}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def plan_for(day: str) -> tuple[Path, dict]:
    path = WF / "data" / "publish" / f"{day}.json"
    if path.exists():
        return path, json.loads(path.read_text(encoding="utf-8"))
    minute = random.randint(0, 29)
    plan = {"day": day, "at": f"22:{minute:02d}:{random.randint(0, 59):02d}", "status": "planned"}
    try:
        studioDb.save_publish_plan(day, plan)
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return path, plan


def pick_video() -> dict | None:
    if not STATE.exists():
        return None
    items = json.loads(STATE.read_text(encoding="utf-8"))["items"]
    ready = [it for it in items if it.get("status") == "ready" and Path(it.get("folder", "")).is_dir()]
    return ready[-1] if ready else None


def mark(message_id: str, **fields) -> None:
    st = json.loads(STATE.read_text(encoding="utf-8"))
    for it in st["items"]:
        if it["message_id"] == message_id:
            it.update(fields)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        studioDb.update_inbox_item(message_id, **fields)
    except Exception:
        pass


def douyin_fields(item: dict) -> dict:
    song_path = item.get("song")
    if not song_path:                          # 手动登记的条目可能没写 song：从成片文件夹的 job.json 找（2026-10-27 漏写导致定时发布中断）
        song_path = json.loads((Path(item["folder"]) / "job.json").read_text(encoding="utf-8")).get("song")
    song = json.loads(Path(song_path).read_text(encoding="utf-8-sig"))
    tags = list(song.get("tags") or [])
    if HOTWORDS.exists():                      # 学习环节整理出的热词，挑还没用上的补进来
        hot = json.loads(HOTWORDS.read_text(encoding="utf-8")).get("tags", [])
        tags += [t for t in hot if t not in tags]
    return {"title": (song.get("douyin_title") or song["title"])[:30], "desc": song.get("description", ""),
            "tags": tags[:5], "ai_declare": True}


def run_publisher(item: dict, fields: dict) -> None:
    made = json.loads((Path(item["folder"]) / "job.json").read_text(encoding="utf-8"))
    # 按成片自己的方向发：横屏作品抖音也发横屏版（发布台不会再去生成竖屏版）
    job = {"folder": item["folder"], "platforms": {"douyin": fields},
           "orientation": made.get("orientation", "horizontal")}
    job_file = WF / "data" / "publish" / f"job_{datetime.now():%Y%m%d}.json"
    job_file.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.Popen([str(PY), str(DOUYIN / "publish" / "publisher.py"), "--job", str(job_file)],
                            cwd=DOUYIN, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace",
                            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    told = set()
    for line in proc.stdout:
        if not line.startswith("@@"):
            continue
        ev = json.loads(line[2:])
        log(f"  {ev.get('stage')} {ev.get('state', '')} {ev.get('msg', '')}")
        state = ev.get("state")
        if ev.get("stage") == "platform" and state in ("login", "ready", "error") and state not in told:
            told.add(state)
            text = {"login": "⚠️ 抖音需要重新扫码登录，请到电脑上的 Edge 窗口扫码",
                    "ready": "**✅ 抖音发布页已填好**\n\n请到电脑上检查视频、标题、话题和封面，确认无误后点「发布」。"
                             + (f"\n\n需要手动处理：{'、'.join(ev['missing'])}" if ev.get("missing") else "")
                             + (f"\n\n提示：{ev['note']}" if ev.get("note") else ""),
                    "error": f"⚠️ 发布页出错：{ev.get('msg')}"}[state]
            notify.send_markdown(text, key=f"pub-{state}-{datetime.now():%Y%m%d}")
        elif ev.get("stage") == "error":
            notify.send_markdown(f"⚠️ 发布台出错：{ev.get('msg')}", key=f"pub-err-{datetime.now():%Y%m%d}")
    proc.wait()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true", help="不等随机时间，立刻打开（测试用）")
    a = ap.parse_args()
    day = datetime.now().strftime("%Y-%m-%d")
    path, plan = plan_for(day)
    if plan["status"] != "planned" and not a.now:
        log(f"{day} 已经处理过（{plan['status']}），不再重复")
        return 0
    if not a.now:
        at = datetime.strptime(f"{day} {plan['at']}", "%Y-%m-%d %H:%M:%S")
        wait = (at - datetime.now()).total_seconds()
        log(f"今天的发布时间：{plan['at']}（还有 {max(wait, 0) / 60:.0f} 分钟）")
        if wait > 0:
            time.sleep(wait)
    item = pick_video()
    if not item:
        log("没有做好待发布的视频")
        notify.send_markdown("⚠️ 到发布时间了，但今天没有做好的视频。请把录屏发到群里，明天会补上。",
                             key=f"pub-none-{day}")
        plan["status"] = "no_video"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    fields = douyin_fields(item)
    log(f"发布：{item.get('title')} → {fields}")
    notify.send_markdown(f"**⏰ 到发布时间了（{plan['at'][:5]}）**\n\n正在打开抖音发布页并上传《{item.get('title')}》，"
                         f"填好后会再提醒你。\n\n- 标题：{fields['title']}\n- 话题："
                         + " ".join("#" + t for t in fields["tags"]), key=f"pub-start-{day}")
    plan.update(status="opened", video=item["folder"], fields=fields)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    mark(item["message_id"], status="publish_opened", publish_day=day)
    run_publisher(item, fields)
    log("发布窗口已关闭")
    return 0


if __name__ == "__main__":
    sys.exit(main())
