# Wiki Schema — Research Deep-Dive

## Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| entity | wiki/entities/ | Named things (people, tools, organizations, datasets) |
| concept | wiki/concepts/ | Ideas, techniques, phenomena, frameworks |
| source | wiki/sources/ | Papers, articles, talks, books, blog posts |
| query | wiki/queries/ | Open questions under active investigation |
| comparison | wiki/comparisons/ | Side-by-side analysis of related entities |
| synthesis | wiki/synthesis/ | Cross-cutting summaries and conclusions |
| overview | wiki/ | High-level project summary (one per project) |
| thesis | wiki/thesis/ | Working hypothesis and its evolution over time |
| methodology | wiki/methodology/ | Research methods, protocols, and study designs |
| finding | wiki/findings/ | Individual empirical results or observations |

## Naming Conventions

- Files: `kebab-case.md`
- Entities: match official name where possible (e.g., `openai.md`, `gpt-4.md`)
- Concepts: descriptive noun phrases (e.g., `chain-of-thought.md`)
- Sources: `author-year-slug.md` (e.g., `wei-2022-cot.md`)
- Queries: question as slug (e.g., `does-scale-improve-reasoning.md`)
- Theses: hypothesis as slug (e.g., `scaling-improves-reasoning.md`)
- Methodologies: method name (e.g., `systematic-review.md`, `ablation-study.md`)
- Findings: descriptive slug (e.g., `larger-models-better-few-shot.md`)

## Frontmatter

All pages must include YAML frontmatter:

```yaml
---
type: entity | concept | source | query | comparison | synthesis | overview
title: Human-readable title
tags: []
related: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

Source pages also include:
```yaml
authors: []
year: YYYY
url: ""
venue: ""
```

Thesis pages also include:
```yaml
confidence: low | medium | high
status: speculative | supported | refuted | settled
```

Finding pages also include:
```yaml
source: "[[source-slug]]"
confidence: low | medium | high
replicated: true | false | null
```

## Index Format

`wiki/index.md` lists all pages grouped by type. Each entry:
```
- [[page-slug]] — one-line description
```

## Log Format

`wiki/log.md` records activity in reverse chronological order:
```
## YYYY-MM-DD

- Action taken / finding noted
```

## Cross-referencing Rules

- Use `[[page-slug]]` syntax to link between wiki pages
- Every entity and concept should appear in `wiki/index.md`
- Queries link to the sources and concepts they draw on
- Synthesis pages cite all contributing sources via `related:`
- Findings link back to their source via the `source:` frontmatter field
- Thesis pages reference supporting and refuting findings via `related:`
- Methodology pages are cited by the findings that used them

## Contradiction Handling

When sources contradict each other:
1. Note the contradiction in the relevant concept or entity page
2. Create or update a query page to track the open question
3. Link both sources from the query page
4. Resolve in a synthesis page once sufficient evidence exists

## Research-Specific Conventions

- Keep the thesis pages updated as evidence accumulates — they are living documents
- Every finding should assess replication status when known
- Methodology pages explain the *why* (rationale) not just the *how*
- Distinguish between direct evidence and inference in finding pages

## 本项目的分类与约定（2026-10-28 起，`workflow/kb/kb.py` 维护）

- 页面按用途分 11 类（见 [[purpose]]），归类结果存在 `workflow/kb/taxonomy.json`；index.md 由脚本按类重建，不要手改。
- **歌曲档案**：`wiki/entities/歌曲-<歌名>.md`，type: entity，tags 含「歌曲」「歌曲档案」。小标题固定：一句话 / 歌词主题与意象 / 旋律与段落 /
  评论主题 / 本次故事线 / 用到的动画 / 可复用的母题 / 不能用的评论 / 待验证。剧本原文放 `raw/sources/编剧-<歌名>-<日期>.md`。
- **台账**：`wiki/synthesis/故事线台账.md`、`wiki/synthesis/动画使用台账.md`，程序统计，不要手改。
- **合并重复页**：保留页正文末尾追加「## 合并自《…》」，全库链接改指保留页，记录在 taxonomy.json 的 merged。
- 引用评论必须是原句（编号回填），引用歌词注明「（听写）」。
