---
type: concept
title: Playwright profile 互斥
created: 2026-10-24
updated: 2026-10-24
tags: [playwright, 浏览器, 并发, 工作流]
related: [playwright, 发布台人工把关, 抖音创作者中心, 抖音运营自动化方案-2026-10-24]
sources: ["抖音运营自动化方案-2026-10-24.md"]
---
# Playwright profile 互斥

Playwright profile 互斥是方案为避免浏览器登录态冲突而设定的调度约束：同一个 Playwright profile 同一时间只能被一个浏览器窗口占用。

## 涉及的 profile

- `publish/profile`：发布台与创作者中心抓数共用（已登录）。
- `workflow/learn/profile`：学习用独立 profile（不登录）。

## 调度安排

- 12:00 的日报抓数与 22:00 的发布都要用 `publish/profile`，两者**时间错开**，不会同时占用。
- 学习任务使用另一个独立 profile，与发布台互不干扰。

## 相关约束

- 发布需要弹出**可见的 Edge 窗口**，因此这些时段电脑必须开机并已登录 Windows。
- 学习用不登录 profile 时，抖音网页版可能弹登录框或验证码，遇到就停下记录、退回搜索引擎，属降级而非解决。

详见 [[playwright]]、[[发布台人工把关]]、[[抖音创作者中心]]。