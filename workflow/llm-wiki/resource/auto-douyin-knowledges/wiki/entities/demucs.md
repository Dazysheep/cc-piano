---
type: entity
title: Demucs
created: 2026-10-24
updated: 2026-10-24
tags: [音源分离, 深度学习, 音频, 模型]
related: [cc-piano, faster-whisper]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---

# Demucs

Demucs 是 Meta 开源的音乐音源分离模型系列，可将混音拆分为人声、鼓、贝斯等独立音轨。cc-piano 使用其中的 `htdemucs_6s` 变体做 6 轨分离。

## 在 cc-piano 中的用法

- 模型：`htdemucs_6s`，6 轨音源分离。
- 用途：作为音轨剪辑（`tracks/`）的基础，分离结果供波形滚动画面与钢琴轨音符显示使用。
- 分离出的人声再交给 [[faster-whisper]] 做歌词识别。
- 相关流程见 [[cc-piano]] 的音轨剪辑模块。