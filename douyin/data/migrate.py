"""一次性迁移脚本：把现有 JSON 文件导入 studio.db。

用法（在 D:\\cc-engine 下）:
  douyin\\.venv\\Scripts\\python douyin\\data\\migrate.py --all
  douyin\\.venv\\Scripts\\python douyin\\data\\migrate.py --step inbox
  douyin\\.venv\\Scripts\\python douyin\\data\\migrate.py --verify
  douyin\\.venv\\Scripts\\python douyin\\data\\migrate.py --init   # 只建库建表
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(r"D:\cc-engine")
sys.path.insert(0, str(ROOT / "douyin" / "data"))
import db  # noqa: E402

WF = ROOT / "workflow"
DOUYIN = ROOT / "douyin"

STEPS = [
    "inbox", "creator", "publish", "reports", "story_costs",
    "comments", "screenplays", "song_history", "templates",
    "anim_variants", "wiki_index",
]


def _read(p: Path) -> str:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return p.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return p.read_text(encoding="utf-8", errors="replace")


def _json(p: Path):
    return json.loads(_read(p))


# ── frontmatter parser ──────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    """Extract YAML-ish frontmatter between --- delimiters."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    end = -1
    for i, ln in enumerate(lines[1:], 1):
        if ln.strip() == "---":
            end = i
            break
    if end < 0:
        return {}
    try:
        import yaml
        return yaml.safe_load("\n".join(lines[1:end])) or {}
    except ImportError:
        pass
    fm = {}
    for ln in lines[1:end]:
        m = re.match(r"^(\w[\w-]*):\s*(.*)", ln)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            items = [s.strip().strip('"').strip("'") for s in val[1:-1].split(",") if s.strip()]
            fm[key] = items
        elif val.lower() in ("true", "false"):
            fm[key] = val.lower() == "true"
        elif re.match(r"^\d+$", val):
            fm[key] = int(val)
        else:
            fm[key] = val.strip('"').strip("'")
    return fm


# ── steps ────────────────────────────────────────────────────────────

def step_inbox():
    src = WF / "data" / "inbox.json"
    if not src.exists():
        print("[inbox] 源文件不存在，跳过")
        return
    data = _json(src)
    conn = db.get_db()
    with conn:
        for mid in data.get("seen", []):
            conn.execute("INSERT OR IGNORE INTO inbox_seen(message_id) VALUES(?)", (mid,))
        for it in data.get("items", []):
            conn.execute("""INSERT OR REPLACE INTO inbox_items(
                message_id, file, status, received, title, artist, song, folder, video,
                publish_day, published_at, note, story_cost_usd, story_fix,
                lyrics, cover_shot, previous_folder, extra)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                it["message_id"], it.get("file"), it.get("status", "new"),
                it.get("received"), it.get("title"), it.get("artist"),
                it.get("song"), it.get("folder"), it.get("video"),
                it.get("publish_day"), it.get("published_at"), it.get("note"),
                it.get("story_cost_usd"), int(it.get("story_fix") or 0),
                it.get("lyrics"), it.get("cover_shot"), it.get("previous_folder"),
                None))
    ni = conn.execute("SELECT count(*) FROM inbox_items").fetchone()[0]
    ns = conn.execute("SELECT count(*) FROM inbox_seen").fetchone()[0]
    si, ss = len(data.get("items", [])), len(data.get("seen", []))
    print(f"[inbox] {si} items, {ss} seen → inbox_items: {ni}, inbox_seen: {ns}")


def step_creator():
    src_dir = WF / "data" / "creator"
    files = sorted(src_dir.glob("*.json")) if src_dir.is_dir() else []
    conn = db.get_db()
    total_items = 0
    for f in files:
        snap = _json(f)
        snap_time = snap.get("time", f.stem)
        with conn:
            cur = conn.execute(
                "SELECT id FROM creator_snapshots WHERE snapshot_at=?", (snap_time,))
            row = cur.fetchone()
            if row:
                sid = row[0]
            else:
                cur = conn.execute(
                    "INSERT INTO creator_snapshots(snapshot_at) VALUES(?)", (snap_time,))
                sid = cur.lastrowid
            for it in snap.get("items", []):
                conn.execute("""INSERT OR REPLACE INTO creator_items(
                    snapshot_id, video_id, title, description, create_time, duration,
                    play, "like", comment, share, collect, metrics)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    sid, str(it["id"]), it.get("title"), it.get("desc"),
                    it.get("create_time"), it.get("duration"),
                    it.get("play", 0), it.get("like", 0), it.get("comment", 0),
                    it.get("share", 0), it.get("collect", 0),
                    json.dumps(it.get("metrics", {}), ensure_ascii=False)))
                total_items += 1
    ns = conn.execute("SELECT count(*) FROM creator_snapshots").fetchone()[0]
    ni = conn.execute("SELECT count(*) FROM creator_items").fetchone()[0]
    print(f"[creator] {len(files)} files → creator_snapshots: {ns}, creator_items: {ni}")


def step_publish():
    src_dir = WF / "data" / "publish"
    if not src_dir.is_dir():
        print("[publish] 目录不存在，跳过")
        return
    conn = db.get_db()
    plans, jobs = 0, 0
    for f in sorted(src_dir.glob("*.json")):
        if f.name.startswith("job_"):
            data = _json(f)
            day = f.stem.replace("job_", "")
            day = f"{day[:4]}-{day[4:6]}-{day[6:8]}" if len(day) == 8 else day
            with conn:
                conn.execute("INSERT OR REPLACE INTO publish_jobs(day, spec) VALUES(?,?)",
                             (day, json.dumps(data, ensure_ascii=False)))
            jobs += 1
        else:
            data = _json(f)
            day = data.get("day", f.stem)
            with conn:
                conn.execute("""INSERT OR REPLACE INTO publish_plans(
                    day, at_time, status, video, fields) VALUES(?,?,?,?,?)""", (
                    day, data.get("at"), data.get("status", "planned"),
                    data.get("video"),
                    json.dumps(data.get("fields", {}), ensure_ascii=False) if data.get("fields") else None))
            plans += 1
    np = conn.execute("SELECT count(*) FROM publish_plans").fetchone()[0]
    nj = conn.execute("SELECT count(*) FROM publish_jobs").fetchone()[0]
    print(f"[publish] {plans} plans, {jobs} jobs → publish_plans: {np}, publish_jobs: {nj}")


def step_reports():
    src_dir = WF / "reports" / "daily"
    if not src_dir.is_dir():
        print("[reports] 目录不存在，跳过")
        return
    conn = db.get_db()
    count = 0
    for f in sorted(src_dir.glob("*.json")):
        day = f.stem
        data_text = _read(f)
        md_path = f.with_suffix(".md")
        md_text = _read(md_path) if md_path.exists() else None
        with conn:
            conn.execute("""INSERT OR REPLACE INTO daily_reports(day, data, markdown)
                VALUES(?,?,?)""", (day, data_text, md_text))
        count += 1
    nr = conn.execute("SELECT count(*) FROM daily_reports").fetchone()[0]
    print(f"[reports] {count} files → daily_reports: {nr}")


def step_story_costs():
    src_dir = WF / "data" / "story"
    if not src_dir.is_dir():
        print("[story_costs] 目录不存在，跳过")
        return
    conn = db.get_db()
    count = 0
    for f in sorted(src_dir.rglob("cost.json")):
        stem = f.parent.name
        cost = _json(f)
        with conn:
            conn.execute("""INSERT OR REPLACE INTO story_costs(
                stem, cost_usd, duration_ms, turns, input_tokens, output_tokens, calls, fix)
                VALUES(?,?,?,?,?,?,?,?)""", (
                stem, cost.get("cost_usd", 0), cost.get("duration_ms", 0),
                cost.get("turns", 0), cost.get("input_tokens", 0),
                cost.get("output_tokens", 0), cost.get("calls", 1),
                int(cost.get("fix") or 0)))
        count += 1
    nr = conn.execute("SELECT count(*) FROM story_costs").fetchone()[0]
    print(f"[story_costs] {count} files → story_costs: {nr}")


def step_comments():
    src_dir = DOUYIN / "output" / "writer"
    if not src_dir.is_dir():
        print("[comments] 目录不存在，跳过")
        return
    conn = db.get_db()
    total = 0
    for f in sorted(src_dir.rglob("comments.json")):
        stem = f.parent.name
        rows = _json(f)
        with conn:
            conn.execute("DELETE FROM comments WHERE stem=?", (stem,))
            for i, r in enumerate(rows):
                conn.execute("""INSERT INTO comments(
                    stem, text, "user", likes, use, ocr, sort_order)
                    VALUES(?,?,?,?,?,?,?)""", (
                    stem, str(r.get("text", "")), str(r.get("user", "")),
                    str(r.get("likes", "")), int(r.get("use", 1)),
                    int(r.get("ocr") or 0), i))
                total += 1
    _rebuild_comments_fts(conn)
    nr = conn.execute("SELECT count(*) FROM comments").fetchone()[0]
    print(f"[comments] {total} rows → comments: {nr}")


def _rebuild_comments_fts(conn):
    with conn:
        conn.execute("DELETE FROM comments_fts")
        conn.execute("INSERT INTO comments_fts(rowid, text, stem) SELECT id, text, stem FROM comments")


def step_screenplays():
    src_dir = DOUYIN / "output" / "writer"
    if not src_dir.is_dir():
        print("[screenplays] 目录不存在，跳过")
        return
    conn = db.get_db()
    count = 0
    for song_dir in sorted(d for d in src_dir.iterdir() if d.is_dir()):
        stem = song_dir.name
        for f in sorted(song_dir.glob("*.json")):
            name = f.stem
            if name == "comments":
                continue
            kind, ver = _parse_screenplay_filename(name)
            if ver is None:
                continue
            data = _json(f)
            with conn:
                conn.execute("""INSERT OR REPLACE INTO screenplays(
                    stem, kind, version, theme, logline, content, applied, usage, time)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (
                    stem, kind, ver,
                    data.get("theme"), data.get("logline"),
                    json.dumps(data, ensure_ascii=False),
                    int(data.get("applied") or 0),
                    json.dumps(data.get("usage", {}), ensure_ascii=False) if data.get("usage") else None,
                    data.get("time")))
            count += 1

    history_file = src_dir / "history.jsonl"
    hcount = 0
    if history_file.exists():
        for line in _read(history_file).splitlines():
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            with conn:
                conn.execute("""INSERT INTO screenplay_history(
                    stem, title, date, theme, logline, used, applied_at)
                    VALUES(?,?,?,?,?,?,?)""", (
                    entry.get("stem"), entry.get("title"), entry.get("date"),
                    entry.get("theme"), entry.get("logline"),
                    json.dumps(entry.get("used", {}), ensure_ascii=False),
                    entry.get("date")))
            hcount += 1

    ns = conn.execute("SELECT count(*) FROM screenplays").fetchone()[0]
    nh = conn.execute("SELECT count(*) FROM screenplay_history").fetchone()[0]
    print(f"[screenplays] {count} versions, {hcount} history → screenplays: {ns}, screenplay_history: {nh}")


def _parse_screenplay_filename(name: str):
    if name.startswith("mv_v") and name[4:].isdigit():
        return "mv", int(name[4:])
    if name.startswith("lyric_v") and name[7:].isdigit():
        return "lyric", int(name[7:])
    if name.startswith("v") and name[1:].isdigit():
        return "standard", int(name[1:])
    return None, None


def step_song_history():
    hist_dir = DOUYIN / "tracks" / "songs" / "history"
    if not hist_dir.is_dir():
        print("[song_history] 目录不存在，跳过")
        return
    conn = db.get_db()
    count = 0
    for song_dir in sorted(d for d in hist_dir.iterdir() if d.is_dir()):
        stem = song_dir.name
        log_entries = {}
        log_file = song_dir / "log.jsonl"
        if log_file.exists():
            for line in _read(log_file).splitlines():
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                v = entry.get("saved_before")
                if v is not None:
                    log_entries[v] = entry.get("note", "")

        for f in sorted(song_dir.glob("v*.json")):
            vstr = f.stem[1:]
            if not vstr.isdigit():
                continue
            ver = int(vstr)
            content = _read(f)
            note = log_entries.get(ver, "")
            with conn:
                conn.execute("""INSERT OR REPLACE INTO song_history(
                    stem, version, content, note) VALUES(?,?,?,?)""",
                    (stem, ver, content, note))
            count += 1
    nr = conn.execute("SELECT count(*) FROM song_history").fetchone()[0]
    print(f"[song_history] {count} files → song_history: {nr}")


def step_templates():
    tpl_dir = DOUYIN / "tracks" / "templates"
    if not tpl_dir.is_dir():
        print("[templates] 目录不存在，跳过")
        return
    conn = db.get_db()
    count = 0

    def _import(base: Path, prefix: str = ""):
        nonlocal count
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            if d.name in ("opening", "ending"):
                _import(d, d.name + "/")
                continue
            name = prefix + d.name
            for f in sorted(d.glob("v*.json")):
                vstr = f.stem[1:]
                if not vstr.isdigit():
                    continue
                ver = int(vstr)
                data = _json(f)
                note = data.get("note", "")
                with conn:
                    conn.execute("""INSERT OR REPLACE INTO render_templates(
                        name, version, content, note) VALUES(?,?,?,?)""",
                        (name, ver, json.dumps(data, ensure_ascii=False), note))
                count += 1

    _import(tpl_dir)
    nr = conn.execute("SELECT count(*) FROM render_templates").fetchone()[0]
    print(f"[templates] {count} files → render_templates: {nr}")


def step_anim_variants():
    variants_dir = DOUYIN / "assets" / "clawd" / "variants"
    conn = db.get_db()
    count = 0

    if variants_dir.is_dir():
        for who_dir in sorted(d for d in variants_dir.iterdir() if d.is_dir()):
            who = who_dir.name
            for clip_dir in sorted(d for d in who_dir.iterdir() if d.is_dir()):
                name = clip_dir.name
                for f in sorted(clip_dir.glob("v*.json")):
                    vstr = f.stem[1:]
                    if not vstr.isdigit():
                        continue
                    ver = int(vstr)
                    data = _json(f)
                    with conn:
                        conn.execute("""INSERT OR REPLACE INTO anim_variants(
                            kind, name, who, version, content) VALUES(?,?,?,?,?)""",
                            ("clip", name, who, ver,
                             json.dumps(data, ensure_ascii=False)))
                    count += 1

    nr = conn.execute("SELECT count(*) FROM anim_variants").fetchone()[0]
    print(f"[anim_variants] {count} files → anim_variants: {nr}")


def step_wiki_index():
    wiki_dir = WF / "llm-wiki" / "resource" / "auto-douyin-knowledges" / "wiki"
    if not wiki_dir.is_dir():
        print("[wiki_index] wiki 目录不存在，跳过")
        return
    conn = db.get_db()
    count = 0

    for f in sorted(wiki_dir.rglob("*.md")):
        rel = f.relative_to(wiki_dir).as_posix()
        rel = rel.rsplit(".", 1)[0]  # drop .md extension
        text = _read(f)
        fm = _parse_frontmatter(text)
        mtime = f.stat().st_mtime
        with conn:
            conn.execute("""INSERT OR REPLACE INTO wiki_pages(
                path, title, type, category, tags, related, sources,
                created, updated, file_mtime) VALUES(?,?,?,?,?,?,?,?,?,?)""", (
                rel, fm.get("title", ""), fm.get("type", ""),
                None,  # category filled by taxonomy import below
                json.dumps(fm.get("tags", []), ensure_ascii=False),
                json.dumps(fm.get("related", []), ensure_ascii=False),
                json.dumps(fm.get("sources", []), ensure_ascii=False),
                str(fm.get("created", "")), str(fm.get("updated", "")),
                mtime))
        count += 1

    # taxonomy
    tax_file = WF / "kb" / "taxonomy.json"
    tax_count = 0
    if tax_file.exists():
        tax = _json(tax_file)
        pages = tax.get("pages", {})
        merged = tax.get("merged", {})
        with conn:
            conn.execute("DELETE FROM wiki_taxonomy")
            for page, cat in pages.items():
                conn.execute("INSERT OR REPLACE INTO wiki_taxonomy(page, category) VALUES(?,?)",
                             (page, cat))
                conn.execute("UPDATE wiki_pages SET category=? WHERE path=?", (cat, page))
                tax_count += 1
            for src_page, dst_page in merged.items():
                conn.execute("INSERT OR REPLACE INTO wiki_taxonomy(page, category, merged_into) VALUES(?,?,?)",
                             (src_page, "merged", dst_page))

    # reviews
    review_file = WF / "llm-wiki" / "resource" / "auto-douyin-knowledges" / ".llm-wiki" / "review.json"
    rev_count = 0
    if review_file.exists():
        reviews = _json(review_file)
        if isinstance(reviews, list):
            with conn:
                conn.execute("DELETE FROM wiki_reviews")
                for r in reviews:
                    conn.execute("""INSERT INTO wiki_reviews(
                        review_id, kind, title, description, source_path, affected,
                        resolved, resolved_action) VALUES(?,?,?,?,?,?,?,?)""", (
                        r.get("id", ""), r.get("type", "suggestion"),
                        r.get("title"), r.get("description"),
                        r.get("sourcePath"),
                        json.dumps(r.get("affectedPages", []), ensure_ascii=False),
                        int(r.get("resolved") or 0),
                        r.get("resolvedAction")))
                    rev_count += 1

    _rebuild_wiki_fts(conn)
    np = conn.execute("SELECT count(*) FROM wiki_pages").fetchone()[0]
    nt = conn.execute("SELECT count(*) FROM wiki_taxonomy").fetchone()[0]
    nrev = conn.execute("SELECT count(*) FROM wiki_reviews").fetchone()[0]
    print(f"[wiki_index] {count} pages, {tax_count} taxonomy, {rev_count} reviews → "
          f"wiki_pages: {np}, wiki_taxonomy: {nt}, wiki_reviews: {nrev}")


def _rebuild_wiki_fts(conn):
    with conn:
        conn.execute("DELETE FROM wiki_fts")
        conn.execute("""INSERT INTO wiki_fts(rowid, path, title, tags)
            SELECT rowid, path, title, tags FROM wiki_pages""")


# ── verify ───────────────────────────────────────────────────────────

def verify():
    conn = db.get_db()
    ok = True

    def _check(label, db_count, src_count):
        nonlocal ok
        tag = "[OK]" if db_count == src_count else "[MISMATCH]"
        if db_count != src_count:
            ok = False
        print(f"  {tag} {label}: DB={db_count}, source={src_count}")

    print("=== 验证 ===")

    # inbox
    src = WF / "data" / "inbox.json"
    if src.exists():
        data = _json(src)
        ni = conn.execute("SELECT count(*) FROM inbox_items").fetchone()[0]
        ns = conn.execute("SELECT count(*) FROM inbox_seen").fetchone()[0]
        _check("inbox_items", ni, len(data.get("items", [])))
        _check("inbox_seen", ns, len(data.get("seen", [])))
        if data.get("items"):
            first = data["items"][0]
            row = conn.execute("SELECT status FROM inbox_items WHERE message_id=?",
                               (first["message_id"],)).fetchone()
            if row and row[0] == first.get("status"):
                print(f"  [OK] inbox spot-check: {first['message_id'][:30]}... status={row[0]}")
            else:
                print(f"  [MISMATCH] inbox spot-check: expected {first.get('status')}, got {row}")
                ok = False

    # creator
    src_dir = WF / "data" / "creator"
    src_files = list(src_dir.glob("*.json")) if src_dir.is_dir() else []
    ns = conn.execute("SELECT count(*) FROM creator_snapshots").fetchone()[0]
    _check("creator_snapshots", ns, len(src_files))

    # publish
    src_dir = WF / "data" / "publish"
    if src_dir.is_dir():
        plans = [f for f in src_dir.glob("*.json") if not f.name.startswith("job_")]
        jobs = list(src_dir.glob("job_*.json"))
        np = conn.execute("SELECT count(*) FROM publish_plans").fetchone()[0]
        nj = conn.execute("SELECT count(*) FROM publish_jobs").fetchone()[0]
        _check("publish_plans", np, len(plans))
        _check("publish_jobs", nj, len(jobs))

    # reports
    src_dir = WF / "reports" / "daily"
    src_count = len(list(src_dir.glob("*.json"))) if src_dir.is_dir() else 0
    nr = conn.execute("SELECT count(*) FROM daily_reports").fetchone()[0]
    _check("daily_reports", nr, src_count)

    # screenplays
    src_dir = DOUYIN / "output" / "writer"
    src_count = 0
    if src_dir.is_dir():
        for sd in src_dir.iterdir():
            if not sd.is_dir():
                continue
            for f in sd.glob("*.json"):
                kind, ver = _parse_screenplay_filename(f.stem)
                if ver is not None:
                    src_count += 1
    ns = conn.execute("SELECT count(*) FROM screenplays").fetchone()[0]
    _check("screenplays", ns, src_count)

    # comments
    src_count = 0
    if src_dir.is_dir():
        for f in src_dir.rglob("comments.json"):
            src_count += len(_json(f))
    nc = conn.execute("SELECT count(*) FROM comments").fetchone()[0]
    _check("comments", nc, src_count)

    # song_history
    hist_dir = DOUYIN / "tracks" / "songs" / "history"
    src_count = 0
    if hist_dir.is_dir():
        for sd in hist_dir.iterdir():
            if sd.is_dir():
                src_count += len([f for f in sd.glob("v*.json") if f.stem[1:].isdigit()])
    nh = conn.execute("SELECT count(*) FROM song_history").fetchone()[0]
    _check("song_history", nh, src_count)

    # templates
    tpl_dir = DOUYIN / "tracks" / "templates"
    src_count = 0
    if tpl_dir.is_dir():
        for f in tpl_dir.rglob("v*.json"):
            if f.stem[1:].isdigit():
                src_count += 1
    nt = conn.execute("SELECT count(*) FROM render_templates").fetchone()[0]
    _check("render_templates", nt, src_count)

    # wiki
    wiki_dir = WF / "llm-wiki" / "resource" / "auto-douyin-knowledges" / "wiki"
    src_count = len(list(wiki_dir.rglob("*.md"))) if wiki_dir.is_dir() else 0
    nw = conn.execute("SELECT count(*) FROM wiki_pages").fetchone()[0]
    _check("wiki_pages", nw, src_count)

    print()
    print("=== 全部通过 ===" if ok else "=== 有不一致 ===")
    return ok


# ── main ─────────────────────────────────────────────────────────────

STEP_FNS = {
    "inbox": step_inbox,
    "creator": step_creator,
    "publish": step_publish,
    "reports": step_reports,
    "story_costs": step_story_costs,
    "comments": step_comments,
    "screenplays": step_screenplays,
    "song_history": step_song_history,
    "templates": step_templates,
    "anim_variants": step_anim_variants,
    "wiki_index": step_wiki_index,
}


def main():
    ap = argparse.ArgumentParser(description="JSON → SQLite 迁移")
    ap.add_argument("--all", action="store_true", help="执行所有迁移步骤")
    ap.add_argument("--step", choices=STEPS, help="执行单个迁移步骤")
    ap.add_argument("--verify", action="store_true", help="验证迁移结果")
    ap.add_argument("--init", action="store_true", help="只建库建表")
    args = ap.parse_args()

    if not any([args.all, args.step, args.verify, args.init]):
        ap.print_help()
        return

    db.get_db()
    print(f"数据库: {db.DB_PATH}")

    if args.init:
        print("建库建表完成")
        return

    if args.all:
        for name in STEPS:
            STEP_FNS[name]()
        print()
        verify()

    if args.step:
        STEP_FNS[args.step]()

    if args.verify:
        verify()

    db.close()


if __name__ == "__main__":
    main()
