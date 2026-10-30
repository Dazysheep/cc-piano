---
type: entity
title: faster-whisper
created: 2026-10-24
updated: 2026-10-24
tags: [语音识别, whisper, 歌词, 工具]
related: [cc-piano, demucs]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---

# faster-whisper

faster-whisper 是 Whisper 语音识别模型的高效推理实现，支持 CPU int8 量化推理。cc-piano 用它做歌词识别。

## 在 cc-piano 中的用法

- 模型：`whisper-medium`，位于 `tools/models/whisper-medium`，CPU int8 推理。
- 输入：[[demucs]] 分离出的人声轨。
- 后处理：以 LRC 文本为准对识别结果纠错。
- 输出用于音轨剪辑中的逐词高亮歌词与唱歌像素小人等效果，见 [[cc-piano]]。