"""盯飞书群「抖音运营」里用户的新消息：每 30 秒查一次，每条新消息打印一行（给 Claude 的 Monitor 当事件流）。
只看用户发的（不含机器人自己的消息），从启动时刻往后算。
用法: douyin\\.venv\\Scripts\\python workflow\\feishu_watch.py
"""
import json
import sys
import time
from datetime import datetime

sys.path.insert(0, r"D:\cc-engine\workflow")
import notify  # noqa: E402

seen: set[str] = set()
start = datetime.now().strftime("%Y-%m-%d %H:%M")
first = True
while True:
    try:
        msgs = notify.messages(start=datetime.now().strftime("%Y-%m-%d"))
        for m in msgs:
            mid = m.get("message_id")
            if mid in seen:
                continue
            seen.add(mid)
            sender = m.get("sender") or {}
            if first or sender.get("sender_type") != "user" or (m.get("create_time") or "") < start:
                continue
            content = m.get("content") or ""
            if content.startswith("{"):
                try:
                    content = json.loads(content).get("text", content)
                except ValueError:
                    pass
            # 多行消息压成一行（监听只看以 [飞书] 开头的行，换行后的内容会被漏掉：2026-10-28 整首歌词只显示了第一句）
            flat = " ⏎ ".join(ln.strip() for ln in content.splitlines() if ln.strip())
            more = f" …（共 {len(flat)} 字，完整内容用 notify.messages 读）" if len(flat) > 600 else ""
            print(f"[飞书] {m.get('create_time')} {m.get('msg_type')}: {flat[:600]}{more}", flush=True)
        first = False
    except Exception as e:                      # 网络抖动：下一轮再试
        print(f"[watch-error] {e}"[:200], file=sys.stderr, flush=True)
    time.sleep(30)
