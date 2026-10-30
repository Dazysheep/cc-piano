---
type: query
title: "Claude Code 无界面模式的成本与重试开销口径"
created: 2026-10-25
tags: []
related: []
---

# Claude Code 无界面模式的成本与重试开销口径

## 已解决（2026-10-26）

### 口径定义

每次 `daily_make.write_story` 的成本 = `run_claude` 首次调用 + 修正轮次调用（如有）。

- **首次调用**：`claude -p --output-format json` 写 story.json，输出存 `claude_out.json`
- **修正轮次**：`check_story` 校验不通过时再跑一次 `claude -p`，输出存 `claude_fix.json`
- 两次是独立的 subprocess 调用，各自计费

### 原始数据 n=2 的口径

0.48 / 0.51 美元均为**单次调用**成本（首次即通过，无修正轮次）。若触发修正，总成本翻倍（约 $1.0）。

### 已添加的追踪

`daily_make.py` 现在会：
1. 从 `claude -p --output-format json` 的输出解析 `cost_usd`、token 用量、轮次数
2. 每次调用后写日志（含首次/修正标记）
3. 修正轮次时汇总两次合计
4. 成本数据存入 `workflow/data/story/<名>/cost.json` 和 `inbox.json` 的 `story_cost_usd` 字段
5. 审核消息里展示成本，修正轮次时会标注

### 持续采样

后续每条视频都会自动记录成本，可从 `inbox.json` 的 `story_cost_usd` 和各 `cost.json` 汇总。
