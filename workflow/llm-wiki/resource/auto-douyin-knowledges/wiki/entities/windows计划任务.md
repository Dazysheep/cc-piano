---
type: entity
title: Windows 计划任务（schtasks）
created: 2026-10-24
updated: 2026-10-24
tags: [调度, Windows, 自动化, schtasks]
related: [抖音运营自动化方案-2026-10-24, 非交互claude-code调度]
sources: ["抖音运营自动化方案-2026-10-24.md"]
---

# Windows 计划任务（schtasks）

Windows 计划任务（通过 `schtasks` 命令行管理）是 Windows 操作系统内置的定时调度机制。在本方案中，它是整个抖音运营自动化流程的定时触发层。

## 在本方案中的角色

- 每个计划任务调用一个 Python 入口脚本（`workflow/daily/produce.py`、`report.py`、`publish_at.py`、`workflow/learn/session.py`、`workflow/weekly/deck.py`），全部用 `douyin\.venv` 运行，日志写在 `workflow\logs\`。
- 计划任务勾选「唤醒计算机运行」，以应对电脑休眠。
- 上线策略：每个任务先手动跑通 2–3 次，再用 `schtasks` 挂成计划任务；失败时飞书报警，日志记录开始、结束与结果，同一天同一账号不重复推送。

## 前提与限制

- 这些时段电脑需保持开机并已登录 Windows（发布要弹出可见的 Edge 窗口），因此并非真正无人值守。
- 当前代码库中尚无任何定时任务代码，调度层需从零搭建。