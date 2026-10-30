---
type: entity
title: Playwright
created: 2026-10-24
updated: 2026-10-24
tags: [浏览器自动化, 抖音, 数据抓取, 发布]
related: [抖音运营自动化方案-2026-10-24, 创作者中心只读抓取, 竖屏短视频改造]
sources: ["抖音运营自动化方案-2026-10-24.md"]
---

# Playwright

Playwright 是一个浏览器自动化框架（独立可验证的公开背景：由 Microsoft 维护，支持 Chromium、Firefox、WebKit 的脚本化控制）。在本方案中，它是发布台、数据抓取与学习浏览三项能力的共同技术基础。

## 在本方案中的用途

- **发布台**（`publish/publisher.py`）：用 Playwright 打开 Edge（登录信息在 `publish/profile`），自动填标题、文案、最多 5 个话题与 AI 声明，停在「发布」按钮前，由用户最终点击。
- **数据抓取**（`workflow/data/fetch_creator.py`）：用同一 `publish/profile` 只读访问创作者中心，抓取播放量、完播率、平均播放时长、2 秒跳出率、点赞、评论、分享、收藏、涨粉等指标。
- **学习浏览**（`workflow/learn/session.py`）：使用独立的不登录 profile `workflow/learn/profile`，限时 2 小时慢节奏访问，搜索同类视频并记录数据。

## 约束

- 同一 profile 同一时间只能被一个窗口占用，因此 12:00 与 22:00 两个任务需错开时间。
- 发布需弹出可见的 Edge 窗口，依赖电脑开机且已登录 Windows。
- 不登录的学习 profile 可能遇到登录框或验证码，需退回搜索引擎。