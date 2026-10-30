---
type: finding
title: cc-piano 前 3 秒无人声
created: 2026-10-24
updated: 2026-10-24
tags: [cc-piano, 钩子, 时间线, 代码可验证]
related: [前3秒钩子设计, cc-piano琴房-studio, 抖音运营自动化方案-2026-10-24]
source: "[[抖音运营自动化方案-2026-10-24]]"
confidence: high
replicated: false
sources: ["抖音运营自动化方案-2026-10-24.md"]
---
# cc-piano 前 3 秒无人声

## 观察

cc-piano 音轨视频开头的时间线为：

- 4 秒拨片动画；
- 再接 1.8 秒水墨转场（`daw.ENTRY`）；
- 音乐还要淡入 1 秒（`build.py:274`）。

因此人声最早在第 5 秒左右才出现，**前 3 秒没有钩子**。

## 证据强度

证据为代码与时间线推算，可直接从代码验证，故 confidence 标为 high。replicated 为 false（尚未做对照实验）。

## 后续

改造方案见 [[前3秒钩子设计]]：`cold_open`、`intro` 时长可调、`fade_in=0`、`hook_text` 大字文案、水墨转场时长可调。