"""抖音运营知识库（LLM Wiki：workflow/llm-wiki/resource/auto-douyin-knowledges）的整理与续写（用户 2026-10-28 要求）。

体系：所有页面分进下面 11 类（TAXONOMY），index.md 按类重建；每首歌一页「歌曲档案」（DeepSeek 执笔），
两本台账（故事线台账、动画使用台账）由程序统计，编剧时读它们避免重复。
- classify：把页面标题 + 标签发给 DeepSeek，归类、找重复（结果存 kb/taxonomy.json，下次只给新页面归类）
- merge：重复页合并进保留的那页（正文追加、标签合并），全库的 [[链接]] 改指过去，删掉重复页
- write_song：编剧（screenwriter）的某一版剧本 + 歌词 / 旋律 / 评论 → 歌曲档案（评论用编号，程序填回原文）
- ledgers：故事线台账（编剧历史 + 剧本版本）、动画使用台账（所有歌曲 json 里用过的画面 / 小动画 / 开头结尾）
- rebuild_index、log
用法：python workflow/kb/kb.py organize          # 归类、合并重复、重建台账和索引
      python workflow/kb/kb.py song <歌曲名> <版本>  # 写这首歌的歌曲档案（并更新台账、索引）
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent.parent
BASE = ENGINE / "workflow" / "llm-wiki" / "resource" / "auto-douyin-knowledges"
WIKI = BASE / "wiki"
RAW = BASE / "raw" / "sources"
TAX = HERE / "taxonomy.json"
TRACKS = ENGINE / "douyin" / "tracks"
sys.path.insert(0, str(TRACKS))
sys.path.insert(0, str(ENGINE / "douyin" / "piano"))
sys.path.insert(0, str(ENGINE / "douyin" / "data"))
try:
    import db as _studioDb
except ImportError:
    _studioDb = None

TAXONOMY = [
    ("songs", "歌曲档案", "每首做过的歌一页：歌词主题、评论主题、故事线、用到的动画、数据。编剧和出片前先看这里"),
    ("works", "已发作品", "每条发到抖音的作品一页：标题、数据、复盘"),
    ("comments", "评论主题", "评论区里反复出现的情绪和题材、代表评论、哪些不能用"),
    ("story", "叙事与母题", "故事结构、母题、开头结尾小剧场、叙事规则和约束"),
    ("anim", "动画与画面", "两个小人、想象画面、小动画、场景、画法"),
    ("data", "运营数据", "日报周报里的指标、基线、已经验证的发现"),
    ("experiments", "实验与待验证", "还没验证的假设、要做的实验、实验方法"),
    ("pipeline", "制作流程", "录屏 → 编剧 → 出片 → 发布 的流程、规则和自动化"),
    ("tools", "工具与工程", "软件、库、平台、工程问题和解决办法"),
    ("sources", "资料来源", "会话记录、日报原文、学习笔记（wiki 页面都从这里来）"),
    ("ledgers", "台账", "故事线台账、动画使用台账：编剧会读，用来避免和以前重复"),
]
KEYS = [k for k, _, _ in TAXONOMY]
FOLDERS = ["entities", "concepts", "findings", "queries", "methodology", "sources", "synthesis", "comparisons", "thesis"]


# ====================================================================== 读写页面
def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def parse(path: Path) -> tuple[dict, str]:
    """(frontmatter 字典, 正文)。只解析本库用到的简单 YAML：key: value / key: [..] / key: "..."。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not mm:
            continue
        k, v = mm.group(1), mm.group(2).strip()
        if v.startswith("["):
            try:
                fm[k] = json.loads(v)
            except ValueError:
                fm[k] = [x.strip().strip("\"'") for x in v.strip("[]").split(",") if x.strip()]
        else:
            fm[k] = v.strip("\"'")
    return fm, m.group(2)


def dump(fm: dict, body: str) -> str:
    lines = []
    for k, v in fm.items():
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}" if isinstance(v, list) else f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body.lstrip("\n")


def pages() -> dict[str, Path]:
    """{"concepts/xxx": 路径}（不含 index / log / overview）。"""
    out = {}
    for f in FOLDERS:
        d = WIKI / f
        for p in sorted(d.glob("*.md")) if d.is_dir() else []:
            out[f"{f}/{p.stem}"] = p
    return out


def _tax() -> dict:
    try:
        return json.loads(TAX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pages": {}, "merged": {}}


def _save_tax(t: dict) -> None:
    TAX.write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    if _studioDb:
        try:
            _studioDb.save_taxonomy(t["pages"])
        except Exception:
            pass


# ====================================================================== 归类 + 查重（DeepSeek）
def _ask(system: str, user: str, max_tokens: int = 6000) -> dict:
    import screenwriter
    text, usage = screenwriter.llm(system, [{"role": "user", "content": user}], "deepseek", max_tokens=max_tokens)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise RuntimeError("DeepSeek 没有返回 JSON：" + text[:200])
    return json.loads(text[a:b + 1]) | {"_usage": usage}


def classify(only_new: bool = True) -> dict:
    """给页面归类、找重复页。返回 {"assign": {id: key}, "duplicates": [[保留, 重复…]]}。"""
    t = _tax()
    ps = pages()
    todo = {pid: p for pid, p in ps.items() if not (only_new and pid in t["pages"])}
    if not todo:
        return {"assign": {}, "duplicates": []}
    rows = []
    for pid, p in todo.items():
        fm, body = parse(p)
        first = next((ln.strip() for ln in body.splitlines() if ln.strip() and not ln.startswith("#")), "")[:60]
        rows.append(f"{pid}｜{fm.get('title', p.stem)}｜{','.join(fm.get('tags', []) if isinstance(fm.get('tags'), list) else [])}｜{first}")
    cats = "\n".join(f"- {k}：{zh}——{desc}" for k, zh, desc in TAXONOMY)
    system = ("你是一个知识库管理员，负责一个「抖音音轨拆解 + 网易云评论故事」像素小人视频账号的运营知识库。"
              "只输出一个 JSON，不要别的文字。")
    user = (f"把下面每个页面归进一个类别，并找出内容重复、应该合并的页面组。\n\n类别：\n{cats}\n\n"
            "规则：歌曲本身的页面（某首歌）归 songs；以抖音作品标题命名的页面归 works；sources/ 下的归 sources；"
            "同一件事换了个说法的页面算重复（比如「X 与 Y」和「Y 模式」讲的是同一个机制）；不同的事不要硬合并。"
            "每组重复里，第一个是保留的（选标题更准确、内容更全的那个）。\n\n"
            f"页面（id｜标题｜标签｜第一句）：\n" + "\n".join(rows) +
            '\n\n输出格式：{"assign": {"页面id": "类别key"}, "duplicates": [["保留的id", "重复的id"]]}')
    res = _ask(system, user)
    assign = {k: v for k, v in (res.get("assign") or {}).items() if k in todo and v in KEYS}
    dups = [[x for x in g if x in ps] for g in (res.get("duplicates") or []) if isinstance(g, list)]
    dups = [g for g in dups if len(g) >= 2 and len({x.split("/")[0] for x in g}) >= 1]
    t["pages"].update(assign)
    _save_tax(t)
    return {"assign": assign, "duplicates": dups, "usage": res.get("_usage")}


def _relink(old: str, new: str) -> int:
    """全库把 [[old]] / [[folder/old]] / [[old|别名]] 改指向 new（new 形如 folder/slug）。返回改了几处。"""
    old_slug = old.split("/")[-1]
    pat = re.compile(r"\[\[(?:[a-z]+/)?" + re.escape(old_slug) + r"(\|[^\]]*)?\]\]")
    n = 0
    for p in list(pages().values()) + [WIKI / "index.md", WIKI / "overview.md"]:
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        s2, k = pat.subn(lambda m: f"[[{new}{m.group(1) or ''}]]", s)
        if k:
            p.write_text(s2, encoding="utf-8")
            n += k
    return n


def merge(groups: list[list[str]]) -> list[str]:
    """合并重复页：正文追加到保留页、标签和相关页合并，链接改指，删掉重复页。返回日志。"""
    ps, t, notes = pages(), _tax(), []
    for g in groups:
        keep, dups = g[0], [d for d in g[1:] if d in ps and d != g[0]]
        if keep not in ps or not dups:
            continue
        fm, body = parse(ps[keep])
        for d in dups:
            dfm, dbody = parse(ps[d])
            body = body.rstrip() + f"\n\n## 合并自《{dfm.get('title', d)}》（{_today()} 整理知识库时合并）\n\n" + dbody.strip() + "\n"
            for k in ("tags", "related", "sources"):
                if isinstance(dfm.get(k), list):
                    fm[k] = list(dict.fromkeys((fm.get(k) if isinstance(fm.get(k), list) else []) + dfm[k]))
            ps[d].unlink()
            t["pages"].pop(d, None)
            t["merged"][d] = keep
            n = _relink(d, keep)
            notes.append(f"合并 {d} → {keep}（改了 {n} 处链接）")
        fm["updated"] = _today()
        ps[keep].write_text(dump(fm, body), encoding="utf-8")
    _save_tax(t)
    return notes


# ====================================================================== 台账（程序统计，不用模型）
def ledgers() -> list[Path]:
    import screenwriter
    songs_dir = TRACKS / "songs"
    rows, use = [], Counter()
    where: dict[str, list[str]] = {}
    for p in sorted(songs_dir.glob("*.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        title = s.get("title", p.stem)
        names = []
        for k in ("opening", "ending"):
            if s.get(k):
                names.append(f"{'开头' if k == 'opening' else '结尾'}·" + (s[k]["name"] if isinstance(s[k], dict) else s[k]))
        for act in s.get("story", {}).get("acts", []):
            for c in act.get("cards", []):
                if c.get("vision"):
                    names.append("想象画面·" + c["vision"])
        names += ["小动画·" + m.get("kind", "") for m in s.get("moments", [])]
        for n in names:
            use[n] += 1
            where.setdefault(n, []).append(title)
    # 故事线：编剧历史（套用过的）+ 还没套用的最新剧本
    for h in screenwriter.history(100):
        rows.append((h.get("date", ""), h.get("title", ""), h.get("theme", ""), h.get("logline", ""), "已套用"))
    out_dir = ENGINE / "douyin" / "output" / "writer"
    for d in sorted(p for p in out_dir.iterdir() if p.is_dir()) if out_dir.is_dir() else []:
        vs = sorted((int(p.stem[1:]), p) for p in d.glob("v*.json") if p.stem[1:].isdigit())
        if vs:
            v = json.loads(vs[-1][1].read_text(encoding="utf-8"))
            if not v.get("applied"):
                rows.append(((v.get("time") or "")[:10], d.name, v.get("theme", ""), v.get("logline", ""), f"剧本 v{vs[-1][0]}（未套用）"))
    (WIKI / "synthesis").mkdir(parents=True, exist_ok=True)
    story = WIKI / "synthesis" / "故事线台账.md"
    body = ("# 故事线台账\n\n每首歌编过的故事线（编剧页「套用」过的，和还没套用的最新剧本）。编剧时模型会读最近的几条，"
            "主题、开头结尾、画面尽量不和它们重复。由 `workflow/kb/kb.py` 自动生成，不要手改。\n\n"
            "| 日期 | 歌 | 主题 | 故事线 | 状态 |\n|---|---|---|---|---|\n" +
            "\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in sorted(rows, reverse=True)) + "\n")
    story.write_text(dump({"type": "synthesis", "title": "故事线台账", "tags": ["台账", "叙事"],
                           "related": ["叙事与母题", "动画使用台账"], "created": "2026-10-28", "updated": _today()}, body),
                     encoding="utf-8")
    anim = WIKI / "synthesis" / "动画使用台账.md"
    lines = [f"| {n} | {c} | {'、'.join(dict.fromkeys(where[n]))} |" for n, c in use.most_common()]
    body = ("# 动画使用台账\n\n每个开头 / 结尾小剧场、想象画面、小动画被哪些歌用过（统计所有歌曲配置）。"
            "用得多的少用，没用过的优先。由 `workflow/kb/kb.py` 自动生成，不要手改。\n\n"
            "| 动画 | 用过几次 | 用在 |\n|---|---|---|\n" + "\n".join(lines) + "\n")
    anim.write_text(dump({"type": "synthesis", "title": "动画使用台账", "tags": ["台账", "动画"],
                          "related": ["动画与画面", "故事线台账"], "created": "2026-10-28", "updated": _today()}, body),
                    encoding="utf-8")
    t = _tax()
    t["pages"].update({"synthesis/故事线台账": "ledgers", "synthesis/动画使用台账": "ledgers"})
    _save_tax(t)
    return [story, anim]


# ====================================================================== 歌曲档案（DeepSeek 执笔）
SONG_SYSTEM = """你是「抖音音轨拆解 + 网易云评论故事」像素小人视频账号的知识库编辑。给你一首歌的歌词、旋律、评论和这次编好的剧本，
写这首歌的「歌曲档案」，以后编剧、出片、复盘都会先读它。要求：
1. 只写事实和可复用的经验，不写空话；中文，短句。
2. 引用评论时只能写编号，格式 {{c3}}（程序会换成原文），不要自己抄评论、不要改写。
3. 涉及死亡、轻生、重病、暴力、具体真人隐私的评论，只在「不能用的评论」里列编号，不展开。
4. 歌词来自 AI 听写，可能有错字；引用歌词时注明「（听写）」。
5. 只输出 Markdown 正文（不要 frontmatter），用下面的小标题，顺序不变：
## 一句话
## 歌词主题与意象
## 旋律与段落
## 评论主题（每类：主题名、几条代表评论编号、在故事里怎么用）
## 本次故事线
## 用到的动画
## 可复用的母题
## 不能用的评论
## 待验证（可以放进实验的假设）"""


def write_song(stem: str, ver: int) -> Path:
    """某一版剧本 → 歌曲档案（entities/歌曲-<名>.md）+ 剧本原文放进 raw/sources，再更新台账和索引。"""
    import screenwriter as W
    sc = W.load_version(stem, ver)
    m = W.materials(stem)
    s = m["song"]
    use = [c for c in m["comments"] if c.get("use", True)][:60]
    ids = {f"c{i + 1}": c for i, c in enumerate(use)}
    lyr = "\n".join(f"{W._fmt(x['t'])} {x['text']}" for x in m["lyrics"]) or "（没有歌词）"
    p = sc.get("plan", {})
    user = (f"【歌】《{s['title']}》{s['artist']}\n\n【歌词（视频时间，AI 听写）】\n{lyr}\n\n"
            f"【旋律】速度 {m['melody']['tempo']} BPM\n" + "\n".join(m["melody"]["segments"]) +
            "\n\n【评论】\n" + "\n".join(f"{k}｜{c.get('likes') or '-'}｜{c['text'][:150]}" for k, c in ids.items()) +
            f"\n\n【本次剧本 v{ver}】主题：{sc.get('theme')}；故事线：{sc.get('logline')}\n节点：\n" +
            "\n".join(f"- {n['t']} {n['part']} {n['title']}：{n['text']}（{n['anim']['type']}·{n['anim']['name']}）" for n in sc.get("nodes", [])) +
            f"\n开头：{(p.get('opening') or {}).get('scene')}；结尾：{(p.get('ending') or {}).get('scene')}；"
            f"需新做的动画：{'、'.join(sc.get('new_animations', [])) or '无'}")
    text, usage = W.llm(SONG_SYSTEM, [{"role": "user", "content": user}], "deepseek", max_tokens=3500)
    body = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text.strip())
    body = re.sub(r"\{\{\s*(c\d+)\s*\}\}", lambda mm: f"「{ids[mm.group(1)]['text']}」（{ids[mm.group(1)].get('likes') or '?'} 赞）"
                  if mm.group(1) in ids else "", body)
    title = f"《{s['title']}》{s['artist']}"
    slug = "歌曲-" + re.sub(r"[\\/:*?\"<>|\s]+", "", s["title"])[:30]
    src_name = f"编剧-{re.sub(r'[\\/:*?<>|\s]+', '', s['title'])[:24]}-{_today()}.md"
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / src_name).write_text(f"# {title} 编剧剧本 v{ver}（DeepSeek，{_today()}）\n\n主题：{sc.get('theme')}\n\n故事线：{sc.get('logline')}\n\n" +
                                "\n".join(f"- {n['t']}｜{n['part']}｜{n['title']}：{n['text']}" + (f"\n  评论：「{n['comment']}」" if n.get("comment") else "")
                                          for n in sc.get("nodes", [])) + "\n", encoding="utf-8")
    fm = {"type": "entity", "title": title, "tags": ["歌曲", "歌曲档案", s["artist"]],
          "related": ["故事线台账", "动画使用台账", "评论区作为内容素材"], "created": _today(), "updated": _today(),
          "sources": [src_name]}
    page = WIKI / "entities" / f"{slug}.md"
    if page.exists():
        old, _ = parse(page)
        fm["created"] = old.get("created", fm["created"])
    footer = (f"\n\n---\n由 DeepSeek 根据剧本 v{ver}、歌词（AI 听写）和录屏评论（本地识别）整理，{_today()}；"
              f"用了 {usage.get('input_tokens', 0)} + {usage.get('output_tokens', 0)} tokens。剧本原文见 raw/sources/{src_name}。\n")
    page.write_text(dump(fm, f"# {title}\n\n" + body.strip() + footer), encoding="utf-8")
    t = _tax()
    t["pages"][f"entities/{slug}"] = "songs"
    _save_tax(t)
    ledgers()
    rebuild_index()
    log(f"写入歌曲档案 [[entities/{slug}|{title}]]（DeepSeek，剧本 v{ver}），更新故事线台账、动画使用台账")
    return page


# ====================================================================== 索引 + 日志 + 体系说明
def _desc(p: Path) -> str:
    _, body = parse(p)
    for ln in body.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith(("#", "|", "-", ">", "---")):
            return re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", ln)[:60]
    return ""


def default_cat(pid: str) -> str:
    folder = pid.split("/")[0]
    return {"sources": "sources", "findings": "data", "queries": "experiments", "methodology": "experiments",
            "synthesis": "ledgers", "thesis": "experiments", "comparisons": "data"}.get(folder, "tools")


def rebuild_index() -> Path:
    t = _tax()
    groups: dict[str, list[str]] = {k: [] for k in KEYS}
    for pid, p in pages().items():
        k = t["pages"].get(pid) or default_cat(pid)
        fm, _ = parse(p)
        groups[k].append(f"- [[{pid}|{fm.get('title', p.stem)}]] — {_desc(p)}")
    out = ["# 抖音运营知识库 · 索引", "",
           f"按用途分 {len(TAXONOMY)} 类（体系说明见 [[purpose]] 和 [[schema]]）。由 `workflow/kb/kb.py` 生成，{_today()}。", ""]
    for k, zh, desc in TAXONOMY:
        out += [f"## {zh}（{len(groups[k])}）", "", f"> {desc}", ""] + sorted(groups[k]) + [""]
    (WIKI / "index.md").write_text("\n".join(out), encoding="utf-8")
    if _studioDb:
        try:
            for pid, p in pages().items():
                fm, _ = parse(p)
                fm.setdefault("category", t["pages"].get(pid) or default_cat(pid))
                _studioDb.index_wiki_page(str(p.relative_to(WIKI)), fm, p.stat().st_mtime)
        except Exception:
            pass
    return WIKI / "index.md"


def log(line: str) -> None:
    p = WIKI / "log.md"
    s = p.read_text(encoding="utf-8") if p.exists() else "# Log\n"
    head, _, rest = s.partition("\n")
    today = f"## {_today()}"
    if today in rest[:400]:
        rest = rest.replace(today, f"{today}\n\n- {line}", 1)
    else:
        rest = f"\n{today}\n\n- {line}\n" + rest
    p.write_text(head + "\n" + rest, encoding="utf-8")


PURPOSE = """# 知识库用途 —— 抖音「cc的音乐引擎」运营

## 要回答的问题

> 怎样做「音轨拆解 + 网易云评论故事」的像素小人视频，才能让人留下来看完、愿意评论，而且每天的故事不重复？

## 谁在用

- **编剧（cc-piano「编剧」页，DeepSeek 等）**：编故事前读「歌曲档案」「评论主题」「叙事与母题」和两本台账，避免重复、避开不能用的评论。
- **出片和分段修改**：读「动画与画面」「制作流程」。
- **日报周报**：结论写进「运营数据」，假设写进「实验与待验证」。

## 分类（index.md 按这个顺序）

| 类别 | 放什么 |
|---|---|
| 歌曲档案 | 每首做过的歌一页（entities/歌曲-*.md）：歌词主题、评论主题、故事线、用到的动画、不能用的评论、待验证 |
| 已发作品 | 每条发到抖音的作品（以作品标题命名）：数据与复盘 |
| 评论主题 | 评论区反复出现的情绪和题材、代表评论 |
| 叙事与母题 | 故事结构、母题、开头结尾小剧场、叙事规则 |
| 动画与画面 | 小人、想象画面、小动画、场景、画法 |
| 运营数据 | 指标、基线、已验证的发现（findings/） |
| 实验与待验证 | 假设、实验、方法（queries/、methodology/） |
| 制作流程 | 录屏 → 编剧 → 出片 → 发布 的流程和规则 |
| 工具与工程 | 软件、库、平台、工程问题 |
| 资料来源 | 会话记录、日报原文、学习笔记（sources/，原文在 raw/sources/） |
| 台账 | 故事线台账、动画使用台账（synthesis/，程序自动生成） |

## 怎么延续

- 每首新歌：编剧页编好剧本后，`workflow/kb/kb.py song <歌> <版本>` 由 DeepSeek 写歌曲档案（编剧页「套用」时自动写），同时更新两本台账和索引。
- 新增的 wiki 页面：`kb.py organize` 让 DeepSeek 给新页面归类、找重复并合并，然后重建索引。
- 评论只按编号交给模型、由程序填回原文，档案里的评论都是原句。
"""

SCHEMA_ADD = """

## 本项目的分类与约定（2026-10-28 起，`workflow/kb/kb.py` 维护）

- 页面按用途分 11 类（见 [[purpose]]），归类结果存在 `workflow/kb/taxonomy.json`；index.md 由脚本按类重建，不要手改。
- **歌曲档案**：`wiki/entities/歌曲-<歌名>.md`，type: entity，tags 含「歌曲」「歌曲档案」。小标题固定：一句话 / 歌词主题与意象 / 旋律与段落 /
  评论主题 / 本次故事线 / 用到的动画 / 可复用的母题 / 不能用的评论 / 待验证。剧本原文放 `raw/sources/编剧-<歌名>-<日期>.md`。
- **台账**：`wiki/synthesis/故事线台账.md`、`wiki/synthesis/动画使用台账.md`，程序统计，不要手改。
- **合并重复页**：保留页正文末尾追加「## 合并自《…》」，全库链接改指保留页，记录在 taxonomy.json 的 merged。
- 引用评论必须是原句（编号回填），引用歌词注明「（听写）」。
"""


def write_docs() -> None:
    (BASE / "purpose.md").write_text(PURPOSE, encoding="utf-8")
    s = (BASE / "schema.md").read_text(encoding="utf-8")
    if "本项目的分类与约定" not in s:
        (BASE / "schema.md").write_text(s.rstrip() + SCHEMA_ADD, encoding="utf-8")


def organize() -> dict:
    """整理：体系说明 → 归类 + 查重（DeepSeek）→ 合并 → 台账 → 索引 → 日志。"""
    write_docs()
    c = classify(only_new=True)
    notes = merge(c["duplicates"])
    ledgers()
    rebuild_index()
    t = _tax()
    counts = Counter(t["pages"].get(pid) or default_cat(pid) for pid in pages())
    log(f"整理知识库：{len(c['assign'])} 页归类（DeepSeek），合并重复 {len(notes)} 组，重建台账和索引；"
        + "，".join(f"{zh} {counts.get(k, 0)}" for k, zh, _ in TAXONOMY))
    return {"classified": len(c["assign"]), "merged": notes, "counts": dict(counts), "usage": c.get("usage")}


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "organize":
        print(json.dumps(organize(), ensure_ascii=False, indent=1))
    elif len(sys.argv) >= 4 and sys.argv[1] == "song":
        print(write_song(sys.argv[2], int(sys.argv[3])))
    else:
        print(__doc__)
