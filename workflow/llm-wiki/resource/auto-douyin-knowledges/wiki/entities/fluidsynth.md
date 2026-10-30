---
type: entity
title: FluidSynth
created: 2026-10-24
updated: 2026-10-24
tags: [音频合成, soundfont, midi, 工具]
related: [cc-piano, midi到下落音符视频渲染管线]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---

# FluidSynth

FluidSynth 是一个软件 MIDI 合成器，通过 SoundFont 音色库把 MIDI 事件实时渲染成音频。它是 cc-piano 钢琴音频合成的引擎。

## 在 cc-piano 中的用法

- 版本：2.6.1，位于 `tools/` 目录。
- 音色库：GeneralUser GS。
- 调用位置：`piano/audio.py`，把解析后的 MIDI 渲染成 wav，随后交给 ffmpeg loudnorm 做两遍归一化到 -14 LUFS、48kHz。
- 该步骤是 [[midi到下落音符视频渲染管线]] 的第 3 步，也是 [[cc-piano]] 成片音轨的来源。