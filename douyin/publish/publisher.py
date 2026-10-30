"""一键发布：用 Edge 打开各平台上传页，上传视频、填写标题/文案/话题，停在「发布」按钮前等你确认。

由琴房网页调用：python publish/publisher.py --job job.json
job = {"folder": 成片文件夹, "platforms": {"douyin": {"title": .., "desc": .., "tags": [..]}, ...}}

登录状态保存在 publish/profile（只在本机），第一次每个平台扫码一次即可。
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from platforms import PLATFORMS, Platform  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "publish" / "profile"
LOGIN_WAIT = 300       # 等待扫码登录的秒数
UPLOAD_WAIT = 1800     # 等待视频上传完成的秒数
LOGIN_WORDS = ["扫码登录", "验证码登录", "短信登录", "密码登录"]


def emit(stage: str, msg: str, **extra) -> None:
    print("@@" + json.dumps({"stage": stage, "msg": msg, **extra}, ensure_ascii=False), flush=True)


def status(key: str, state: str, msg: str, **extra) -> None:
    """state: open / login / uploading / ready / error"""
    emit("platform", msg, platform=key, state=state, **extra)


# ---------------------------------------------------------------- 竖屏版
def ensure_vertical(folder: Path) -> Path:
    video = folder / "video_vertical.mp4"
    if video.exists():
        return video
    job_file = folder / "job.json"
    if not job_file.exists():
        emit("vertical", "这条成片缺少生成参数，竖屏平台改用横屏版", pct=1)
        return folder / "video.mp4"
    job = json.loads(job_file.read_text(encoding="utf-8"))
    if job.get("kind") == "tracks":                # 音轨剪辑作品只有横屏版
        emit("vertical", "音轨作品只有横屏版，竖屏平台也发横屏版", pct=1)
        return folder / "video.mp4"
    job.update(vertical=True, deliver_dir=str(folder), preview=None)
    tmp = folder / "_vertical_job.json"
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    emit("vertical", "正在生成竖屏版", pct=0)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "piano" / "render.py"), "--job", str(tmp), "--json-progress"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    )
    tail = []
    for line in proc.stdout:
        if line.startswith("@@"):
            ev = json.loads(line[2:])
            if ev["stage"] == "frames" and ev.get("pct") is not None:
                emit("vertical", "正在生成竖屏版", pct=round(ev["pct"] * 0.9, 3))
            elif ev["stage"] == "compose":
                emit("vertical", "正在合成竖屏版", pct=0.95)
        elif line.strip():
            tail = (tail + [line.rstrip()])[-8:]
    proc.wait()
    tmp.unlink(missing_ok=True)
    if proc.returncode != 0 or not video.exists():
        raise RuntimeError("竖屏版生成失败：" + " / ".join(tail[-3:]))
    emit("vertical", "竖屏版已生成", pct=1)
    return video


# ---------------------------------------------------------------- 页面工具（会搜索所有 iframe）
def _frames(page):
    try:
        return page.frames
    except PWError:
        return []


def find(page, selectors: list[str], timeout: float = 0, visible: bool = True):
    deadline = time.time() + timeout
    while True:
        for fr in _frames(page):
            for sel in selectors:
                try:
                    loc = fr.locator(sel)
                    for i in range(min(loc.count(), 6)):
                        el = loc.nth(i)
                        if not visible or el.is_visible():
                            return el
                except PWError:
                    pass
        if time.time() >= deadline:
            return None
        page.wait_for_timeout(500)


def find_file_input(page):
    fallback = None
    for fr in _frames(page):
        try:
            loc = fr.locator("input[type=file]")
            for i in range(loc.count()):
                accept = (loc.nth(i).get_attribute("accept") or "").lower()
                if "video" in accept or ".mp4" in accept:
                    return loc.nth(i)
                fallback = fallback or loc.nth(i)
        except PWError:
            pass
    return fallback


def page_text(page) -> str:
    parts = []
    for fr in _frames(page):
        try:
            parts.append(fr.inner_text("body", timeout=2000))
        except PWError:
            pass
    return "\n".join(parts)


def goto(page, url: str) -> None:
    for attempt in range(3):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return
        except PWError as e:
            if attempt == 2:
                host = url.split("/")[2]
                if "ERR_" in str(e):
                    raise RuntimeError(f"网络连不上 {host}，请先确认能在浏览器里打开这个网站") from None
                raise
            page.wait_for_timeout(3000)


# ---------------------------------------------------------------- 每个平台
def open_upload(page, p: Platform):
    goto(page, p.url)
    deadline = time.time() + 10
    while time.time() < deadline:
        fi = find_file_input(page)
        if fi:
            return fi
        page.wait_for_timeout(700)

    status(p.key, "login", f"请在 Edge 窗口的「{p.name}」标签页里登录（扫码即可），登录后会自动继续")
    page.bring_to_front()
    deadline = time.time() + LOGIN_WAIT
    while time.time() < deadline:
        page.wait_for_timeout(3000)
        fi = find_file_input(page)
        if fi:
            return fi
        on_login = any(k in page.url for k in ("login", "passport")) or any(w in page_text(page) for w in LOGIN_WORDS)
        if not on_login and p.url.split("?")[0] not in page.url:
            try:   # 登录后跳到了首页，回到上传页
                goto(page, p.url)
            except PWError:
                pass
    raise RuntimeError("5 分钟内没有完成登录")


def fill_input(el, text: str) -> None:
    el.click()
    el.fill("")
    el.fill(text)


def fill_editor(page, el, text: str) -> None:
    el.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.keyboard.insert_text(text)


def _first_visible(page, make):
    """在所有 iframe 里找第一个可见元素；make(frame) 返回 locator。"""
    for fr in _frames(page):
        try:
            loc = make(fr)
            for i in range(min(loc.count(), 6)):
                if loc.nth(i).is_visible():
                    return loc.nth(i)
        except PWError:
            pass
    return None


def declare_ai(page, p: Platform, shot: Path | None) -> bool:
    """在「自主声明」里选「内容由AI生成」，成功返回 True，并截图留证。"""
    trigger = None
    for t in p.declare_open:
        trigger = _first_visible(page, lambda fr, t=t: fr.get_by_text(t, exact=True))
        if trigger and t == "自主声明":   # 找到的是左边的标签，点它右边的选择框
            nxt = trigger.locator("xpath=following-sibling::*[1]")
            trigger = nxt if nxt.count() else trigger
        if trigger:
            break
    if not trigger:
        return False
    trigger.scroll_into_view_if_needed()
    trigger.click()
    page.wait_for_timeout(900)
    option = None
    for t in p.declare_ai:
        option = _first_visible(page, lambda fr, t=t: fr.get_by_text(t, exact=False))
        if option:
            break
    if not option:
        page.keyboard.press("Escape")
        return False
    option.click()
    page.wait_for_timeout(600)
    ok_btn = _first_visible(page, lambda fr: fr.get_by_role("button", name=re.compile("^(确定|确认|完成)$")))
    if ok_btn:
        ok_btn.click()
        page.wait_for_timeout(600)
    text = page_text(page)
    done = "请选择自主声明" not in text and any(t.replace(" ", "") in text.replace(" ", "") for t in p.declare_ai)
    if shot:   # 选完后占位文字已变，按左边固定的「自主声明」标签滚动到可见再截图
        label = _first_visible(page, lambda fr: fr.get_by_text("自主声明", exact=True))
        try:
            if label:
                label.scroll_into_view_if_needed(timeout=3000)
            page.screenshot(path=str(shot))
        except PWError:
            pass
    return done


def start_platform(page, p: Platform, data: dict, video: Path) -> dict:
    """上传视频并填写内容，返回 {filled, missing}。"""
    status(p.key, "open", "正在打开上传页")
    fi = open_upload(page, p)
    status(p.key, "uploading", "正在上传视频")
    fi.set_input_files(str(video))

    filled, missing = [], []
    title, desc, tags = data.get("title", ""), data.get("desc", ""), data.get("tags", [])[: p.tag_max]

    if p.title_max and title:
        el = find(page, p.title_sel, timeout=120)
        try:
            if not el:
                raise RuntimeError
            fill_input(el, title[: p.title_max])
            filled.append("标题")
        except Exception:
            missing.append("标题")

    el = find(page, p.desc_sel, timeout=120 if not p.title_max else 30)
    if el and (desc or (tags and p.tag_mode == "inline")):
        try:
            fill_editor(page, el, desc)
            filled.append("文案")
            if tags and p.tag_mode == "inline":
                for t in tags:   # 逐个输入 #话题，等联想出来再确认
                    page.keyboard.type(" #" + t, delay=60)
                    page.wait_for_timeout(1200)
                    page.keyboard.press(p.tag_confirm)
                    page.wait_for_timeout(300)
                filled.append("话题")
        except Exception:
            missing.append("文案")
    elif desc:
        missing.append("文案")

    if tags and p.tag_mode == "input":
        el = find(page, p.tag_sel, timeout=20)
        try:
            if not el:
                raise RuntimeError
            for t in tags:
                el.click()
                el.fill(t)
                page.keyboard.press("Enter")
                page.wait_for_timeout(400)
            filled.append("标签")
        except Exception:
            missing.append("标签")

    if data.get("ai_declare") and p.declare_open:
        shot = Path(data["shot_dir"]) / f"declare_{p.key}.png" if data.get("shot_dir") else None
        try:
            ok = declare_ai(page, p, shot)
        except Exception:
            ok = False
        (filled if ok else missing).append("自主声明·AI生成")

    status(p.key, "uploading", "内容已填写，等待视频上传完成", filled=filled, missing=missing)
    return {"filled": filled, "missing": missing}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    job = json.loads(Path(ap.parse_args().job).read_text(encoding="utf-8"))
    folder = Path(job["folder"])
    chosen = [k for k in PLATFORMS if k in job["platforms"]]

    edited = folder / "video_edited.mp4"            # 在「剪辑」页里选用了剪辑器导出的版本时，优先发它
    videos = {False: edited if edited.exists() else folder / "video.mp4"}
    if edited.exists():
        emit("video", "发布剪辑器里导出的版本（video_edited.mp4）")
    horizontal = job.get("orientation") == "horizontal"   # 所有平台都发横屏版
    try:
        if horizontal:
            videos[True] = videos[False]
        elif any(PLATFORMS[k].vertical for k in chosen):
            videos[True] = ensure_vertical(folder)
    except Exception as e:
        emit("error", str(e))
        return 1

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(
                str(PROFILE), channel="msedge", headless=False, no_viewport=True,
                args=["--start-maximized"],
            )
        except PWError as e:
            msg = "发布用的 Edge 窗口已经开着，请先关掉它再试" if "in use" in str(e).lower() or "exist" in str(e).lower() \
                else f"无法启动 Edge：{e}"
            emit("error", msg)
            return 1

        pages, results = {}, {}
        for i, key in enumerate(chosen):   # 阶段一：逐个打开、登录、开始上传、填写
            p = PLATFORMS[key]
            page = ctx.pages[0] if i == 0 and ctx.pages else ctx.new_page()
            pages[key] = page
            try:
                results[key] = start_platform(page, p, {"shot_dir": str(folder), **job["platforms"][key]},
                                              videos[p.vertical])
            except Exception as e:
                status(key, "error", f"{p.name}：{e}")
                pages.pop(key)

        deadline = time.time() + UPLOAD_WAIT   # 阶段二：等各标签页的视频上传完
        pending = set(pages)
        while pending and time.time() < deadline:
            for key in list(pending):
                p = PLATFORMS[key]
                try:
                    if any(w in page_text(pages[key]) for w in p.done_text):
                        r = results[key]
                        tip = "已填好，请在浏览器里检查后点「发布」"
                        note = p.note.replace("cover_vertical.jpg", "cover.jpg") if horizontal else p.note
                        status(key, "ready", tip, filled=r["filled"], missing=r["missing"], note=note)
                        pending.discard(key)
                except PWError:   # 标签页被关掉了
                    status(key, "error", f"{p.name} 的标签页已关闭")
                    pending.discard(key)
            if pending:
                time.sleep(3)
        for key in pending:
            status(key, "ready", "视频可能仍在上传，请在浏览器里确认后点「发布」",
                   filled=results[key]["filled"], missing=results[key]["missing"], note=PLATFORMS[key].note)

        if pages:
            emit("waiting", "在 Edge 里逐个检查并点「发布」，完成后关闭窗口即可")
        else:
            emit("waiting", "没有平台完成填写。可以先在 Edge 里登录各平台，关闭窗口后再点「开始发布」重试")
        while True:   # 等你关掉浏览器窗口
            try:
                if not ctx.pages:
                    break
                ctx.pages[0].wait_for_timeout(2000)
            except PWError:
                break
        try:
            ctx.close()
        except PWError:
            pass
    emit("done", "发布窗口已关闭")
    return 0


if __name__ == "__main__":
    sys.exit(main())
