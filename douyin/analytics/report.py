"""读取抖音创作者中心导出的作品数据（xlsx/csv），生成 HTML 报表与 top_topics.json。

用法: python analytics/report.py <导出文件.xlsx> [--top 10]
"""
import argparse
import html
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent

# 标准字段 → 导出表中可能的列名关键字（按顺序匹配）
COLUMNS = {
    "title": ["作品名称", "作品标题", "标题", "描述"],
    "date": ["发布时间", "发布日期"],
    "plays": ["播放量", "播放"],
    "likes": ["点赞量", "点赞"],
    "comments": ["评论量", "评论"],
    "shares": ["分享量", "分享"],
    "favorites": ["收藏量", "收藏"],
    "completion": ["完播率"],
    "followers": ["涨粉量", "新增粉丝", "涨粉"],
}
REQUIRED = ["title", "plays", "likes"]


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for field, keys in COLUMNS.items():
        col = next((c for k in keys for c in df.columns if k in str(c)), None)
        if col is not None:
            out[field] = df[col]
    missing = [f for f in REQUIRED if f not in out]
    if missing:
        sys.exit(f"导出表缺少必要列 {missing}，实际列名: {list(df.columns)}")
    return pd.DataFrame(out)


def to_number(s: pd.Series) -> pd.Series:
    """兼容 '1.2w'、'35%'、'1,234' 等格式。"""
    def conv(v):
        if pd.isna(v):
            return 0.0
        t = str(v).strip().replace(",", "")
        mult = 1.0
        if t.endswith("%"):
            t, mult = t[:-1], 0.01
        elif t[-1:] in ("w", "W", "万"):
            t, mult = t[:-1], 10000.0
        try:
            return float(t) * mult
        except ValueError:
            return 0.0
    return s.map(conv)


def analyze(df: pd.DataFrame) -> pd.DataFrame:
    for f in COLUMNS:
        if f not in ("title", "date") and f in df:
            df[f] = to_number(df[f])
    plays = df["plays"].clip(lower=1)
    df["like_rate"] = df["likes"] / plays
    engagement = df["likes"] + 2 * df.get("comments", 0) + 3 * df.get("shares", 0) + 2 * df.get("favorites", 0)
    df["engage_rate"] = engagement / plays
    # 综合分：互动率、播放量、完播率按排名百分位加权，播放量参与计分避免小样本高比率霸榜
    score = df["engage_rate"].rank(pct=True) * 0.5 + df["plays"].rank(pct=True) * 0.3
    if "completion" in df:
        score += df["completion"].rank(pct=True) * 0.2
    df["score"] = score
    return df.sort_values("score", ascending=False)


def render_html(df: pd.DataFrame, path: Path) -> None:
    cols = [("title", "作品"), ("plays", "播放"), ("likes", "点赞"), ("like_rate", "点赞率"),
            ("engage_rate", "互动率"), ("completion", "完播率"), ("followers", "涨粉"), ("score", "综合分")]
    cols = [(k, n) for k, n in cols if k in df]

    def fmt(k, v):
        if k in ("like_rate", "engage_rate", "completion"):
            return f"{v:.1%}"
        if k == "score":
            return f"{v:.2f}"
        if isinstance(v, float):
            return f"{v:,.0f}"
        return html.escape(str(v))

    rows = "".join(
        "<tr>" + "".join(f"<td>{fmt(k, r[k])}</td>" for k, _ in cols) + "</tr>" for _, r in df.iterrows()
    )
    summary = (f"作品 {len(df)} 条 · 总播放 {df['plays'].sum():,.0f} · "
               f"平均点赞率 {df['like_rate'].mean():.1%} · 平均互动率 {df['engage_rate'].mean():.1%}")
    path.write_text(f"""<!doctype html><html lang="zh"><meta charset="utf-8">
<title>抖音作品数据报表</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;margin:24px;background:#fafafa;color:#222}}
table{{border-collapse:collapse;width:100%;background:#fff}}
th,td{{padding:8px 10px;border-bottom:1px solid #eee;text-align:right}}
th:first-child,td:first-child{{text-align:left;max-width:420px}}
th{{background:#222;color:#fff;position:sticky;top:0}}
tr:nth-child(-n+4) td{{background:#fff7d6}}
</style>
<h1>抖音作品数据报表</h1><p>{summary}</p>
<table><tr>{"".join(f"<th>{n}</th>" for _, n in cols)}</tr>{rows}</table></html>""", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    raw = pd.read_csv(args.file) if args.file.suffix.lower() == ".csv" else pd.read_excel(args.file)
    df = analyze(map_columns(raw))

    report = HERE / "report.html"
    render_html(df, report)
    top = [{"title": r["title"], "plays": r["plays"], "engage_rate": round(r["engage_rate"], 4)}
           for _, r in df.head(args.top).iterrows()]
    (HERE / "top_topics.json").write_text(json.dumps(top, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报表: {report}\nTop 选题: {HERE / 'top_topics.json'}")
    for t in top[:5]:
        print(f"  {t['engage_rate']:.1%}  {t['title']}")


if __name__ == "__main__":
    main()
