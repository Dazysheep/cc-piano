---
type: entity
title: Audiveris
created: 2026-10-24
updated: 2026-10-24
tags: [工具, 光学乐谱识别, OMR, 五线谱, MIDI]
related: [cc-piano琴房-studio, midi到下落音符视频渲染管线]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---
# Audiveris

Audiveris 是一款开源的**光学乐谱识别（OMR，Optical Music Recognition）**工具，用于把五线谱图像或 PDF 转换成机器可读的乐谱结构（如 MusicXML），进而可导出为 MIDI 等格式。它属于独立可复用的工具，而非某个产品专属组件。

## 在 cc-piano 中的用途

在 [[cc-piano琴房-studio]] 中，Audiveris 是 `piano/score2midi.py` 的依赖之一：当用户手上只有五线谱 PDF 时，可用该脚本把 PDF 转成 MIDI，再进入 [[midi到下落音符视频渲染管线]]。脚本将 Audiveris 与 music21 配合使用——Audiveris 负责从谱面图像识别出乐谱结构，music21 负责后续的乐谱处理与 MIDI 导出。

## 相关说明

- 工具随项目放在 `tools/` 目录下（与 FluidSynth、音色库、模型并列）。
- 该路径属于「有 PDF 五线谱时的可选入口」，与「直接拖入 MIDI」和「拖入 mp3/wav 用钢琴转写模型转 MIDI」并列，是三条素材输入方式之一。
- 本文档未对 Audiveris 的识别准确率或版本做实测，相关结论仅来自源码阅读。
