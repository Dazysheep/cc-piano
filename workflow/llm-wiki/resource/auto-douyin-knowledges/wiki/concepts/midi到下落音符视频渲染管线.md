---
type: concept
title: MIDI 到下落音符视频渲染管线
created: 2026-10-24
updated: 2026-10-24
tags: [渲染管线, midi, 钢琴视频, ffmpeg, 多进程]
related: [cc-piano, 逐帧绘制坐标与特效模型, 任务队列与子进程进度协议, 剪映草稿生成, fluidsynth, pyjianyingdraft]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---

# MIDI 到下落音符视频渲染管线

MIDI 到下落音符视频渲染管线是 [[cc-piano]] 的核心链路：从 MIDI 解析、音频合成、多进程分段渲染到 ffmpeg 合成的完整流程。入口为 `piano/render.py` 的 `render()`，按顺序执行 10 步。

## 触发与调度

网页 `POST /api/render` → 任务进队列 → 参数写成 `uploads/jobs/<id>.json` → 子进程 `piano/render.py --job <json> --json-progress` → 子进程每行输出 `@@{json}` 进度，server 解析后供网页轮询 `/api/jobs/<id>`。调度细节见 [[任务队列与子进程进度协议]]。

## 10 步流程

1. **读配置和元数据**：`piano/config.yaml`（画面、布局、音符颜色、特效、音频、剪映默认值）+ 曲子同名 `.yaml`（标题、副标题、水印、背景、发布标题/话题等），命令行和网页参数优先。
2. **解析 MIDI**（`piano/midi_notes.py`）：建立速度变化表把 tick 换算成秒；多轨时平均音高最高的轨算右手，单轨按中央 C（60）分左右手；每个音符最短 0.05 秒。
3. **合成钢琴音频**（`piano/audio.py`）：[[fluidsynth]] 2.6.1 + GeneralUser GS 音色库渲染 wav，再用 ffmpeg loudnorm **两遍**归一化到 -14 LUFS（短曲单遍不准），48kHz。
4. **（可选）爆款开头**（`piano/intro.py`）：头像唱片 × 曲子封面唱片，配全曲 12%~80% 里音符最密最响的 4 秒。当前 `intro.enabled: false` 关闭，代码保留。
5. **多进程渲染画面**：按 10 秒一段切片，`multiprocessing.Pool`（默认 4 进程）并行；每段同时输出 `notes`（黑底下落音符）与 `keys`（琴键条）两个图层视频，每层通过 imageio-ffmpeg 管道送进 libx264；失败片段自动重试一次（多为内存紧张）；片段用 ffmpeg concat 无损拼接成 `notes.mp4`、`keys.mp4`。
6. **背景与文字**：没指定背景时生成深色渐变；文字层 `text.png`（标题小型大写字母风格 + 中文微软雅黑）和蒙版 `scrim.png`。
7. **ffmpeg 一次合成成片**（`audio.compose`）：背景（缩放裁切、按 `bg_dim` 压暗）→ 音符层用 **screen（滤色）混合** → 叠琴键条 → 叠文字 → 首 0.8 秒淡入、尾 1.5 秒淡出；音频：钢琴声延后 `lead_in` 3 秒，有背景音时循环铺满、淡入淡出后混音再限幅；有开头时开头和正片在同一次编码里拼接。
8. **封面**：取全曲约 1/3 处的一帧（有开头时用开头画面）。
9. **剪映草稿**（`piano/jianying.py`，[[pyjianyingdraft]]）：见 [[剪映草稿生成]]。
10. **交付**：`待上传/<日期时间>_<标题>/` 下 `video.mp4`、`cover.jpg`、`publish.md`（标题+文案+话题）和 `job.json`（生成参数，发布时据此补渲染竖屏版）。预览模式只写 `output/<曲名>/preview.mp4`，不进待上传、不生成草稿。

## 关键技术点

- **screen（滤色）混合**：音符层与背景的合成方式，是黑底音符叠加到背景上的关键。
- **loudnorm 两遍归一化**：短曲单遍不准，故两遍归一化到 -14 LUFS、48kHz。
- **多进程分段渲染 + concat 无损拼接**：10 秒切片、Pool 默认 4 进程、失败重试一次。
- **竖屏适配**：1080×1920，琴键底边上移 0.82 避开抖音文案区，`key_range: auto`。

## 性能

1080p60 约 35–40 帧/秒（4 进程），5 分钟曲子约 8 分钟；每进程连同 x264 编码约占 400–600MB 内存；`--fps 30` 渲染时间减半。该数据未说明硬件配置与曲目。

## 相关页面

逐帧绘制细节见 [[逐帧绘制坐标与特效模型]]；主体见 [[cc-piano]]。