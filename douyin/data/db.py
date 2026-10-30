"""cc-engine SQLite 数据库后端。

用法：
    from data import db
    db.get_db()                    # 首次调用时自动建库建表
    db.save_inbox_state(state)     # 写入
    state = db.load_inbox_state()  # 读取
    db.close()                     # 关闭（一般不需要手动调用）

数据库文件：douyin/data/studio.db
"""
import json
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent / "studio.db"

DUAL_WRITE = True
JSON_READ_FALLBACK = True

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()

SCHEMA_VERSION = 1

# ======================================================================
# 连接管理
# ======================================================================

def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _create_tables(conn)
        _conn = conn
    return _conn


def close():
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


# ======================================================================
# 建表
# ======================================================================

_TABLES_SQL = """
-- 元数据
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT DEFAULT (datetime('now','localtime')),
    description TEXT
);

-- ========================== 运营域 ==========================

CREATE TABLE IF NOT EXISTS inbox_items (
    message_id      TEXT PRIMARY KEY,
    file            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'new',
    received        TEXT,
    title           TEXT,
    artist          TEXT,
    song            TEXT,
    folder          TEXT,
    video           TEXT,
    publish_day     TEXT,
    published_at    TEXT,
    note            TEXT,
    story_cost_usd  REAL,
    story_fix       INTEGER DEFAULT 0,
    lyrics          TEXT,
    cover_shot      TEXT,
    previous_folder TEXT,
    extra           TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_inbox_status ON inbox_items(status);

CREATE TABLE IF NOT EXISTS inbox_seen (
    message_id TEXT PRIMARY KEY,
    seen_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS creator_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    fetched_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_snap_at ON creator_snapshots(snapshot_at);

CREATE TABLE IF NOT EXISTS creator_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES creator_snapshots(id),
    video_id    TEXT NOT NULL,
    title       TEXT,
    description TEXT,
    create_time INTEGER,
    duration    REAL,
    play        INTEGER DEFAULT 0,
    "like"      INTEGER DEFAULT 0,
    comment     INTEGER DEFAULT 0,
    share       INTEGER DEFAULT 0,
    collect     INTEGER DEFAULT 0,
    metrics     TEXT
);
CREATE INDEX IF NOT EXISTS idx_ci_snap ON creator_items(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_ci_video ON creator_items(video_id);

CREATE TABLE IF NOT EXISTS publish_plans (
    day        TEXT PRIMARY KEY,
    at_time    TEXT,
    status     TEXT DEFAULT 'planned',
    video      TEXT,
    fields     TEXT,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS publish_jobs (
    day  TEXT PRIMARY KEY,
    spec TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_costs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stem          TEXT NOT NULL,
    cost_usd      REAL DEFAULT 0,
    duration_ms   INTEGER DEFAULT 0,
    turns         INTEGER DEFAULT 0,
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    calls         INTEGER DEFAULT 1,
    fix           INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sc_stem ON story_costs(stem);

CREATE TABLE IF NOT EXISTS daily_reports (
    day        TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    markdown   TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- ========================== 内容域 ==========================

CREATE TABLE IF NOT EXISTS screenplays (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stem       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'standard',
    version    INTEGER NOT NULL,
    theme      TEXT,
    logline    TEXT,
    content    TEXT NOT NULL,
    applied    INTEGER DEFAULT 0,
    usage      TEXT,
    time       TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(stem, kind, version)
);
CREATE INDEX IF NOT EXISTS idx_sp_stem ON screenplays(stem);

CREATE TABLE IF NOT EXISTS screenplay_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stem       TEXT NOT NULL,
    title      TEXT,
    date       TEXT,
    theme      TEXT,
    logline    TEXT,
    used       TEXT,
    applied_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_sh_date ON screenplay_history(date);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stem       TEXT NOT NULL,
    text       TEXT NOT NULL,
    "user"     TEXT DEFAULT '',
    likes      TEXT DEFAULT '',
    use        INTEGER DEFAULT 1,
    ocr        INTEGER DEFAULT 0,
    checked    TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_com_stem ON comments(stem);

CREATE TABLE IF NOT EXISTS song_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stem       TEXT NOT NULL,
    version    INTEGER NOT NULL,
    content    TEXT NOT NULL,
    note       TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(stem, version)
);
CREATE INDEX IF NOT EXISTS idx_songh_stem ON song_history(stem);

CREATE TABLE IF NOT EXISTS render_templates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    version    INTEGER NOT NULL,
    content    TEXT NOT NULL,
    note       TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(name, version)
);
CREATE INDEX IF NOT EXISTS idx_rt_name ON render_templates(name);

CREATE TABLE IF NOT EXISTS anim_variants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    name       TEXT NOT NULL,
    who        TEXT DEFAULT 'male',
    version    INTEGER NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(kind, name, who, version)
);
CREATE INDEX IF NOT EXISTS idx_av_kind_name ON anim_variants(kind, name);

-- ========================== Wiki 索引域 ==========================

CREATE TABLE IF NOT EXISTS wiki_pages (
    path       TEXT PRIMARY KEY,
    title      TEXT,
    type       TEXT,
    category   TEXT,
    tags       TEXT,
    related    TEXT,
    sources    TEXT,
    created    TEXT,
    updated    TEXT,
    file_mtime REAL,
    indexed_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_wp_category ON wiki_pages(category);
CREATE INDEX IF NOT EXISTS idx_wp_type ON wiki_pages(type);

CREATE TABLE IF NOT EXISTS wiki_reviews (
    review_id  TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    title      TEXT,
    description TEXT,
    source_path TEXT,
    affected   TEXT,
    resolved   INTEGER DEFAULT 0,
    resolved_action TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS wiki_taxonomy (
    page        TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    merged_into TEXT
);
"""

_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS comments_fts USING fts5(
    text, stem,
    content=comments, content_rowid=id,
    tokenize='unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    path, title, tags,
    content=wiki_pages, content_rowid=rowid,
    tokenize='unicode61'
);
"""

_FTS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS comments_ai AFTER INSERT ON comments BEGIN
    INSERT INTO comments_fts(rowid, text, stem) VALUES (new.id, new.text, new.stem);
END;
CREATE TRIGGER IF NOT EXISTS comments_ad AFTER DELETE ON comments BEGIN
    INSERT INTO comments_fts(comments_fts, rowid, text, stem) VALUES ('delete', old.id, old.text, old.stem);
END;
CREATE TRIGGER IF NOT EXISTS comments_au AFTER UPDATE ON comments BEGIN
    INSERT INTO comments_fts(comments_fts, rowid, text, stem) VALUES ('delete', old.id, old.text, old.stem);
    INSERT INTO comments_fts(rowid, text, stem) VALUES (new.id, new.text, new.stem);
END;

CREATE TRIGGER IF NOT EXISTS wiki_ai AFTER INSERT ON wiki_pages BEGIN
    INSERT INTO wiki_fts(rowid, path, title, tags) VALUES (new.rowid, new.path, new.title, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS wiki_ad AFTER DELETE ON wiki_pages BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, path, title, tags) VALUES ('delete', old.rowid, old.path, old.title, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS wiki_au AFTER UPDATE ON wiki_pages BEGIN
    INSERT INTO wiki_fts(wiki_fts, rowid, path, title, tags) VALUES ('delete', old.rowid, old.path, old.title, old.tags);
    INSERT INTO wiki_fts(rowid, path, title, tags) VALUES (new.rowid, new.path, new.title, new.tags);
END;
"""


def _create_tables(conn: sqlite3.Connection):
    conn.executescript(_TABLES_SQL)
    conn.executescript(_FTS_SQL)
    conn.executescript(_FTS_TRIGGERS_SQL)
    existing = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    if not existing:
        conn.execute("INSERT OR IGNORE INTO schema_version(version, description) VALUES (?, ?)",
                     (SCHEMA_VERSION, "初始版本：运营/内容/Wiki 三域"))
        conn.commit()


# ======================================================================
# 运营域
# ======================================================================

_INBOX_COLS = ("message_id", "file", "status", "received", "title", "artist", "song",
               "folder", "video", "publish_day", "published_at", "note",
               "story_cost_usd", "story_fix", "lyrics", "cover_shot", "previous_folder")


def load_inbox_state() -> dict:
    db = get_db()
    items = []
    for row in db.execute("SELECT * FROM inbox_items ORDER BY rowid"):
        d = {k: row[k] for k in _INBOX_COLS if row[k] is not None}
        if row["story_fix"]:
            d["story_fix"] = bool(row["story_fix"])
        if row["extra"]:
            d.update(json.loads(row["extra"]))
        items.append(d)
    seen = [r[0] for r in db.execute("SELECT message_id FROM inbox_seen ORDER BY rowid")]
    return {"seen": seen, "items": items}


def save_inbox_state(state: dict):
    db = get_db()
    with db:
        db.execute("DELETE FROM inbox_items")
        db.execute("DELETE FROM inbox_seen")
        for mid in state.get("seen", []):
            db.execute("INSERT OR IGNORE INTO inbox_seen(message_id) VALUES (?)", (mid,))
        for it in state.get("items", []):
            known = {k: it.get(k) for k in _INBOX_COLS}
            extra_keys = set(it) - set(_INBOX_COLS)
            if extra_keys:
                known["extra"] = json.dumps({k: it[k] for k in extra_keys}, ensure_ascii=False)
            if isinstance(known.get("story_fix"), bool):
                known["story_fix"] = int(known["story_fix"])
            cols = [k for k, v in known.items() if v is not None]
            cols.append("extra") if "extra" not in cols and known.get("extra") else None
            placeholders = ", ".join("?" for _ in cols)
            db.execute(f"INSERT INTO inbox_items({', '.join(cols)}) VALUES ({placeholders})",
                       [known.get(c) for c in cols])


def update_inbox_item(message_id: str, **fields):
    db = get_db()
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [message_id]
    with db:
        db.execute(f"UPDATE inbox_items SET {sets}, updated_at = datetime('now','localtime') WHERE message_id = ?", vals)


# ------ creator snapshots ------

def save_creator_snapshot(snap: dict) -> int:
    db = get_db()
    with db:
        cur = db.execute("INSERT INTO creator_snapshots(snapshot_at) VALUES (?)", (snap["time"],))
        sid = cur.lastrowid
        for it in snap.get("items", []):
            db.execute("""INSERT INTO creator_items(
                snapshot_id, video_id, title, description, create_time, duration,
                play, "like", comment, share, collect, metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                sid, str(it["id"]), it.get("title"), it.get("desc"),
                it.get("create_time"), it.get("duration"),
                it.get("play", 0), it.get("like", 0), it.get("comment", 0),
                it.get("share", 0), it.get("collect", 0),
                json.dumps(it.get("metrics", {}), ensure_ascii=False) if it.get("metrics") else None
            ))
    return sid


def list_creator_snapshots() -> list[dict]:
    db = get_db()
    return [dict(r) for r in db.execute("SELECT id, snapshot_at, fetched_at FROM creator_snapshots ORDER BY snapshot_at")]


def load_creator_snapshot(snapshot_id: int) -> dict:
    db = get_db()
    snap = db.execute("SELECT * FROM creator_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    if not snap:
        return {}
    items = []
    for r in db.execute("SELECT * FROM creator_items WHERE snapshot_id = ? ORDER BY play DESC", (snapshot_id,)):
        d = {"id": r["video_id"], "title": r["title"], "desc": r["description"],
             "create_time": r["create_time"], "duration": r["duration"],
             "play": r["play"], "like": r["like"], "comment": r["comment"],
             "share": r["share"], "collect": r["collect"]}
        if r["metrics"]:
            d["metrics"] = json.loads(r["metrics"])
        items.append(d)
    return {"time": snap["snapshot_at"], "items": items}


def query_video_trend(video_id: str, limit: int = 30) -> list[dict]:
    db = get_db()
    rows = db.execute("""
        SELECT cs.snapshot_at, ci.play, ci."like", ci.comment, ci.share, ci.collect
        FROM creator_items ci JOIN creator_snapshots cs ON ci.snapshot_id = cs.id
        WHERE ci.video_id = ? ORDER BY cs.snapshot_at DESC LIMIT ?
    """, (video_id, limit))
    return [dict(r) for r in rows]


# ------ publish ------

def save_publish_plan(day: str, plan: dict):
    db = get_db()
    with db:
        db.execute("""INSERT OR REPLACE INTO publish_plans(day, at_time, status, video, fields)
                      VALUES (?, ?, ?, ?, ?)""",
                   (day, plan.get("at"), plan.get("status", "planned"), plan.get("video"),
                    json.dumps(plan.get("fields", {}), ensure_ascii=False) if plan.get("fields") else None))


def load_publish_plan(day: str) -> dict | None:
    db = get_db()
    r = db.execute("SELECT * FROM publish_plans WHERE day = ?", (day,)).fetchone()
    if not r:
        return None
    d = {"day": r["day"], "at": r["at_time"], "status": r["status"]}
    if r["video"]:
        d["video"] = r["video"]
    if r["fields"]:
        d["fields"] = json.loads(r["fields"])
    return d


def save_publish_job(day: str, spec: dict):
    db = get_db()
    with db:
        db.execute("INSERT OR REPLACE INTO publish_jobs(day, spec) VALUES (?, ?)",
                   (day, json.dumps(spec, ensure_ascii=False)))


# ------ costs ------

def save_story_cost(stem: str, cost: dict):
    db = get_db()
    with db:
        db.execute("""INSERT INTO story_costs(stem, cost_usd, duration_ms, turns, input_tokens, output_tokens, calls, fix)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (stem, cost.get("cost_usd", 0), cost.get("duration_ms", 0), cost.get("turns", 0),
                    cost.get("input_tokens", 0), cost.get("output_tokens", 0),
                    cost.get("calls", 1), int(cost.get("fix", False))))


def total_cost(since: str | None = None) -> dict:
    db = get_db()
    where = "WHERE created_at >= ?" if since else ""
    params = (since,) if since else ()
    r = db.execute(f"""SELECT COUNT(*) as n, SUM(cost_usd) as total, AVG(cost_usd) as avg,
                       SUM(CASE WHEN fix THEN 1 ELSE 0 END) as fixes
                       FROM story_costs {where}""", params).fetchone()
    return dict(r) if r else {}


# ------ daily reports ------

def save_daily_report(day: str, data: dict, markdown: str = ""):
    db = get_db()
    with db:
        db.execute("INSERT OR REPLACE INTO daily_reports(day, data, markdown) VALUES (?, ?, ?)",
                   (day, json.dumps(data, ensure_ascii=False), markdown))


def load_daily_report(day: str) -> dict | None:
    db = get_db()
    r = db.execute("SELECT * FROM daily_reports WHERE day = ?", (day,)).fetchone()
    if not r:
        return None
    return {"day": r["day"], "data": json.loads(r["data"]), "markdown": r["markdown"]}


# ======================================================================
# 内容域
# ======================================================================

# ------ screenplays ------

def save_screenplay(stem: str, kind: str, version: int, data: dict):
    db = get_db()
    with db:
        db.execute("""INSERT OR REPLACE INTO screenplays(stem, kind, version, theme, logline, content, usage, time)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (stem, kind, version, data.get("theme"), data.get("logline"),
                    json.dumps(data, ensure_ascii=False),
                    json.dumps(data["usage"], ensure_ascii=False) if data.get("usage") else None,
                    data.get("time")))


def load_screenplay(stem: str, kind: str, version: int) -> dict | None:
    db = get_db()
    r = db.execute("SELECT content FROM screenplays WHERE stem = ? AND kind = ? AND version = ?",
                   (stem, kind, version)).fetchone()
    return json.loads(r["content"]) if r else None


def list_screenplay_versions(stem: str) -> list[dict]:
    db = get_db()
    rows = db.execute("""SELECT kind, version, theme, logline, time, applied
                         FROM screenplays WHERE stem = ? ORDER BY kind, version""", (stem,))
    return [dict(r) for r in rows]


def mark_screenplay_applied(stem: str, kind: str, version: int):
    db = get_db()
    with db:
        db.execute("UPDATE screenplays SET applied = 1 WHERE stem = ? AND kind = ? AND version = ?",
                   (stem, kind, version))


def append_screenplay_history(entry: dict):
    db = get_db()
    with db:
        db.execute("""INSERT INTO screenplay_history(stem, title, date, theme, logline, used)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   (entry.get("stem"), entry.get("title"), entry.get("date"),
                    entry.get("theme"), entry.get("logline"),
                    json.dumps(entry.get("used", {}), ensure_ascii=False)))


def load_screenplay_history(limit: int = 50) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT * FROM screenplay_history ORDER BY applied_at DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        d = dict(r)
        if d.get("used"):
            d["used"] = json.loads(d["used"])
        out.append(d)
    return out


# ------ comments ------

def save_comments(stem: str, rows: list[dict]):
    db = get_db()
    with db:
        db.execute("DELETE FROM comments WHERE stem = ?", (stem,))
        for i, r in enumerate(rows):
            db.execute("""INSERT INTO comments(stem, text, "user", likes, use, ocr, checked, sort_order)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (stem, r.get("text", ""), r.get("user", ""), str(r.get("likes", "")),
                        int(r.get("use", True)), int(r.get("ocr", False)),
                        r.get("checked"), i))


def load_comments(stem: str) -> list[dict]:
    db = get_db()
    rows = db.execute('SELECT * FROM comments WHERE stem = ? ORDER BY sort_order', (stem,))
    out = []
    for r in rows:
        d = {"text": r["text"], "user": r["user"], "likes": r["likes"],
             "use": bool(r["use"]), "ocr": bool(r["ocr"])}
        if r["checked"]:
            d["checked"] = r["checked"]
        out.append(d)
    return out


def search_comments(query: str, limit: int = 50) -> list[dict]:
    db = get_db()
    rows = db.execute("""SELECT c.stem, c.text, c."user", c.likes
                         FROM comments_fts fts JOIN comments c ON fts.rowid = c.id
                         WHERE comments_fts MATCH ? ORDER BY rank LIMIT ?""", (query, limit))
    return [dict(r) for r in rows]


# ------ song history ------

def save_song_snapshot(stem: str, version: int, content: dict, note: str = ""):
    db = get_db()
    with db:
        db.execute("INSERT OR REPLACE INTO song_history(stem, version, content, note) VALUES (?, ?, ?, ?)",
                   (stem, version, json.dumps(content, ensure_ascii=False), note))


def load_song_snapshot(stem: str, version: int) -> dict | None:
    db = get_db()
    r = db.execute("SELECT content FROM song_history WHERE stem = ? AND version = ?", (stem, version)).fetchone()
    return json.loads(r["content"]) if r else None


def list_song_versions(stem: str) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT version, note, created_at FROM song_history WHERE stem = ? ORDER BY version", (stem,))
    return [dict(r) for r in rows]


# ------ templates ------

def save_template(name: str, version: int, data: dict, note: str = ""):
    db = get_db()
    with db:
        db.execute("INSERT OR REPLACE INTO render_templates(name, version, content, note) VALUES (?, ?, ?, ?)",
                   (name, version, json.dumps(data, ensure_ascii=False), note))


def load_template(name: str, version: int) -> dict | None:
    db = get_db()
    r = db.execute("SELECT content FROM render_templates WHERE name = ? AND version = ?", (name, version)).fetchone()
    return json.loads(r["content"]) if r else None


def list_template_versions(name: str) -> list[int]:
    db = get_db()
    return [r[0] for r in db.execute("SELECT version FROM render_templates WHERE name = ? ORDER BY version", (name,))]


# ------ anim variants ------

def save_anim_variant(kind: str, name: str, who: str, version: int, data: dict):
    db = get_db()
    with db:
        db.execute("INSERT OR REPLACE INTO anim_variants(kind, name, who, version, content) VALUES (?, ?, ?, ?, ?)",
                   (kind, name, who, version, json.dumps(data, ensure_ascii=False)))


def load_anim_variant(kind: str, name: str, who: str, version: int) -> dict | None:
    db = get_db()
    r = db.execute("SELECT content FROM anim_variants WHERE kind=? AND name=? AND who=? AND version=?",
                   (kind, name, who, version)).fetchone()
    return json.loads(r["content"]) if r else None


# ======================================================================
# Wiki 索引域
# ======================================================================

def index_wiki_page(path: str, frontmatter: dict, mtime: float = 0.0):
    db = get_db()
    with db:
        db.execute("""INSERT OR REPLACE INTO wiki_pages(path, title, type, category, tags, related, sources, created, updated, file_mtime)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   (path, frontmatter.get("title"), frontmatter.get("type"),
                    frontmatter.get("category"),
                    json.dumps(frontmatter.get("tags", []), ensure_ascii=False),
                    json.dumps(frontmatter.get("related", []), ensure_ascii=False),
                    json.dumps(frontmatter.get("sources", []), ensure_ascii=False),
                    frontmatter.get("created"), frontmatter.get("updated"), mtime))


def search_wiki(query: str, limit: int = 20) -> list[dict]:
    db = get_db()
    rows = db.execute("""SELECT wp.path, wp.title, wp.type, wp.category, wp.tags
                         FROM wiki_fts fts JOIN wiki_pages wp ON fts.rowid = wp.rowid
                         WHERE wiki_fts MATCH ? ORDER BY rank LIMIT ?""", (query, limit))
    out = []
    for r in rows:
        d = dict(r)
        if d.get("tags"):
            d["tags"] = json.loads(d["tags"])
        out.append(d)
    return out


def wiki_pages_by_category(category: str) -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT path, title, type, tags FROM wiki_pages WHERE category = ? ORDER BY title", (category,))
    out = []
    for r in rows:
        d = dict(r)
        if d.get("tags"):
            d["tags"] = json.loads(d["tags"])
        out.append(d)
    return out


def wiki_pages_all() -> list[dict]:
    db = get_db()
    rows = db.execute("SELECT path, title, type, category FROM wiki_pages ORDER BY path")
    return [dict(r) for r in rows]


# ------ taxonomy ------

def save_taxonomy(pages: dict, merged: dict | None = None):
    db = get_db()
    with db:
        db.execute("DELETE FROM wiki_taxonomy")
        for page, cat in pages.items():
            db.execute("INSERT INTO wiki_taxonomy(page, category) VALUES (?, ?)", (page, cat))
        if merged:
            for src, dst in merged.items():
                db.execute("INSERT OR REPLACE INTO wiki_taxonomy(page, category, merged_into) VALUES (?, ?, ?)",
                           (src, "merged", dst))


def load_taxonomy() -> dict:
    db = get_db()
    pages = {}
    merged = {}
    for r in db.execute("SELECT page, category, merged_into FROM wiki_taxonomy"):
        if r["merged_into"]:
            merged[r["page"]] = r["merged_into"]
        else:
            pages[r["page"]] = r["category"]
    return {"pages": pages, "merged": merged}


# ------ wiki reviews ------

def save_wiki_review(review: dict):
    db = get_db()
    with db:
        db.execute("""INSERT OR REPLACE INTO wiki_reviews(review_id, kind, title, description, source_path, affected, resolved, resolved_action)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (review["id"], review["type"], review.get("title"), review.get("description"),
                    review.get("sourcePath"),
                    json.dumps(review.get("affectedPages", []), ensure_ascii=False),
                    int(review.get("resolved", False)), review.get("resolvedAction")))


def load_wiki_reviews(resolved: bool | None = None) -> list[dict]:
    db = get_db()
    if resolved is None:
        rows = db.execute("SELECT * FROM wiki_reviews ORDER BY created_at")
    else:
        rows = db.execute("SELECT * FROM wiki_reviews WHERE resolved = ? ORDER BY created_at", (int(resolved),))
    return [dict(r) for r in rows]


# ======================================================================
# 便捷聚合查询
# ======================================================================

def stats() -> dict:
    db = get_db()
    tables = ["inbox_items", "inbox_seen", "creator_snapshots", "creator_items",
              "publish_plans", "story_costs", "daily_reports",
              "screenplays", "screenplay_history", "comments", "song_history",
              "render_templates", "anim_variants", "wiki_pages", "wiki_reviews", "wiki_taxonomy"]
    out = {}
    for t in tables:
        r = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()
        out[t] = r[0]
    return out
