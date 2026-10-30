"""飞书「抖音运营」群的收发：发通知 / 文件 / 视频，读取群里新发的录屏并下载。

调用 lark-cli 的 exe（不用 .cmd，参数里有 & 会被 cmd 拆坏）；它的文件参数只认当前目录下的相对路径，
所以发文件、下载时先切到文件所在目录。群 ID 等配置在 workflow/config.json。
发通知用机器人身份；读群消息用用户身份（机器人没有读群消息的权限）。
"""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
LARK = Path(r"D:\cc-engine\feishu\node_modules\@larksuite\cli\bin\lark-cli.exe")
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
CHAT = CFG["feishu"]["ops_chat_id"]
MEDIA_TYPES = ("media", "file")      # 视频消息是 media；以文件形式发的录屏是 file（audio 是语音消息，不是素材：2026-10-28 误收过一条语音）


class LarkError(RuntimeError):
    pass


def lark(*args: str, cwd: Path | None = None) -> dict:
    r = subprocess.run([str(LARK), *args, "--format", "json"], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout.strip()
    try:
        data = json.loads(out[out.index("{"):]) if "{" in out else {}
    except ValueError:
        data = {}
    if not data.get("ok"):
        err = data.get("error") or {"message": (r.stderr or out)[-300:]}
        raise LarkError(f"lark-cli {args[0]} {args[1] if len(args) > 1 else ''}: {err.get('code', '')} "
                        f"{err.get('message', '')}".strip())
    return data.get("data") or {}


def send_markdown(text: str, key: str | None = None) -> str:
    """发一条 Markdown 消息到群里；key 用于去重（同一个 key 只会发一次）。返回 message_id。"""
    args = ["im", "+messages-send", "--as", "bot", "--chat-id", CHAT, "--markdown", text]
    if key:
        args += ["--idempotency-key", key[:50]]
    return lark(*args)["message_id"]


def send_file(path: Path, key: str | None = None) -> str:
    path = Path(path).resolve()
    args = ["im", "+messages-send", "--as", "bot", "--chat-id", CHAT, "--file", path.name]
    if key:
        args += ["--idempotency-key", key[:50]]
    return lark(*args, cwd=path.parent)["message_id"]


UPLOAD_LIMIT = 25 * 1024 * 1024        # 飞书消息文件上传上限 30MB，留点余量
PREVIEW_DIR = Path(r"D:\cc-engine\.tmp\feishu_upload")


def preview_copy(video: Path, cover: Path) -> tuple[Path, Path]:
    """太大的视频压一份 720p 预览（只用于发到飞书看，成片本身不动），和封面放在同一个临时文件夹。"""
    import shutil
    import imageio_ffmpeg
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = PREVIEW_DIR / f"{video.parent.name}_preview.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(video),
                    "-vf", "scale=-2:1280", "-c:v", "libx264", "-crf", "27", "-preset", "fast",
                    "-maxrate", "2500k", "-bufsize", "5000k", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(out)], check=True)
    cov = PREVIEW_DIR / f"{video.parent.name}_cover.jpg"
    shutil.copy(cover, cov)
    return out, cov


def send_video(video: Path, cover: Path, key: str | None = None) -> str:
    """视频消息（iPhone 上能直接播放）。超过 25MB 时发一份 720p 预览。"""
    video, cover = Path(video).resolve(), Path(cover).resolve()
    if video.stat().st_size > UPLOAD_LIMIT or cover.parent != video.parent:
        video, cover = preview_copy(video, cover)
    args = ["im", "+messages-send", "--as", "bot", "--chat-id", CHAT, "--video", video.name,
            "--video-cover", cover.name]
    if key:
        args += ["--idempotency-key", key[:50]]
    return lark(*args, cwd=video.parent)["message_id"]


def messages(start: str | None = None, pages: int = 5) -> list[dict]:
    """群里的消息（用户身份），按时间从旧到新。start 如 "2026-10-24"。"""
    args = ["im", "+chat-messages-list", "--as", "user", "--chat-id", CHAT, "--order", "asc", "--page-size", "50"]
    if start:
        args += ["--start", start]
    out, token = [], None
    for _ in range(pages):
        data = lark(*args, *(["--page-token", token] if token else []))
        out += data.get("messages") or data.get("items") or []
        token = data.get("page_token")
        if not data.get("has_more") or not token:
            break
    return out


def media_items(msgs: list[dict]) -> list[dict]:
    """从消息里挑出视频、音频和文件：[{message_id, file_key, name, msg_type, create_time, sender}]。"""
    items = []
    for m in msgs:
        if m.get("msg_type") not in MEDIA_TYPES:
            continue
        c = m.get("content")
        if isinstance(c, str):
            try:
                c = json.loads(c)
            except ValueError:
                c = {"raw": c}
        key = (c or {}).get("file_key") if isinstance(c, dict) else None
        name = (c or {}).get("file_name") if isinstance(c, dict) else None
        if not key and isinstance(m.get("content"), str):     # 渲染后的文本形如 <video key="file_xxx" name="x.mov" .../>
            import re
            hit = re.search(r'\bkey="(file_[^"]+)"', m["content"])
            key = hit.group(1) if hit else None
            hit = re.search(r'\bname="([^"]+)"', m["content"])
            name = hit.group(1) if hit else None
        if key:
            items.append({"message_id": m.get("message_id"), "file_key": key, "msg_type": m.get("msg_type"),
                          "name": name, "create_time": m.get("create_time"), "sender": m.get("sender")})
    return items


def download(item: dict, out_dir: Path) -> Path:
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = item.get("name") or f"{item['message_id']}.mp4"
    data = lark("im", "+messages-resources-download", "--as", "user", "--message-id", item["message_id"],
                "--file-key", item["file_key"], "--type", "file", "--output", name, cwd=out_dir)
    return Path(data.get("saved_path") or out_dir / name)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "inbox":
        for it in media_items(messages()):
            print(it)
    elif len(sys.argv) > 2 and sys.argv[1] == "say":
        print(send_markdown(" ".join(sys.argv[2:])))
    else:
        print("用法: notify.py inbox | say <文字>")
