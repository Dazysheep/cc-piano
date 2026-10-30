---
name: claude-video-cases
description: Reference library of 424 videos/animations made with Claude 5.5 (Opus, Sonnet, Haiku, Fable), with research on which model, style and production path fits which kind of video, costs, prompt templates and reusable open-source bases (athemeroy/awesome-claude-5-5-videos). Use when choosing which Claude model or agent split (e.g. Opus director + Sonnet/Haiku workers) to use for a video job, picking a production path or visual style for a topic, writing a video brief or prompt, or looking for example cases (模型选用、制作路径、案例参考).
---

# Claude 5.5 视频案例库

资料在 `D:\cc-engine\filmlab\awesome-claude-videos`（截至 2026-10-11，只读）。中文入口 `README.zh-CN.md`。按问题找文档：

| 要回答的问题 | 读 |
|---|---|
| 这类片子用哪个模型 / 怎么分工、整项任务花多少 | `docs/workflow-analysis.zh-CN.md`、`docs/prompt-matrix.zh-CN.md` |
| 这类内容常配什么画风、什么配色 | `docs/domain-style-atlas.zh-CN.md`、`docs/color-modes.zh-CN.md` |
| 按制作路径找案例（代码动画 / 讲解 / 3D / 改编素材 / 外部视频模型 / 交互） | `docs/cases-index.zh-CN.md`、`docs/library.zh-CN.md`（按模型分组） |
| 写制作任务单、提示模板 | `docs/production-brief.zh-CN.md`、`docs/prompt-playbook.zh-CN.md` |
| 可复用的开源底座 | `docs/production-resources.zh-CN.md`（lemo-opuscar、ClaudeAnimationBase、Papermotion…） |
| 数据本身 | `data/collection-index.csv` |

用法：

- 给出建议时引用具体案例和文档里的数字，并说明它们的限制：九帧取样，不是同提示的模型排名，费用是作者自报。
- 本机已部署的底座：手绘 → `film-handdrawn`，电影感 → `film-cinematic`，59 种风格 → `lemo-opuscar`。
- 案例链接多在 X（x.com），只给用户链接，不要替用户登录或抓取。
- 视频版权归原作者；本仓库文字和图表是 CC BY 4.0，引用时注明出处。
