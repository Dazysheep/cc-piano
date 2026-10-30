---
type: entity
title: cc-piano（琴房 Studio）
created: 2026-10-24
updated: 2026-10-24
tags: [cc-piano, 钢琴视频, 抖音短视频, 本地软件, 渲染]
related: [midi到下落音符视频渲染管线, 逐帧绘制坐标与特效模型, 任务队列与子进程进度协议, 剪映草稿生成, 半自动多平台发布, fluidsynth, demucs, faster-whisper, pyjianyingdraft, cc-piano-5秒预览试跑, cc-piano-网页接口冒烟测试, cc-piano未试跑模块是否可用]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---

# cc-piano（琴房 Studio）

cc-piano（中文名「琴房 Studio」）是一款本地运行的抖音短视频制作软件，主线功能是把 MIDI 渲染成 Synthesia 风格的钢琴下落音符视频（下落音符 + 琴键高亮 + FluidSynth 合成的钢琴声），并同时输出封面、发布文案与可在剪映中继续编辑的草稿。本文档记录的版本为 2.4.0（`douyin/app/VERSION`），项目位置 `D:\cc-engine\douyin\`。

## 功能模块

- **琴房**（`/studio`）：MIDI → 钢琴视频主流程，支持试听、试渲染 15 秒、生成视频。
- **音轨剪辑**（`/tracks`）：多轨 DAW 风格视频 + 歌词，基于 Demucs 6 轨分离。
- **拨片开头**（`/flick`）：图库 + 拨片下滑片头生成。
- **发布台**（`/tour`）：一键上传到 5 个平台，停在发布按钮前。
- **作品集**（`/works`）：半弧形胶片浏览成片。
- **设置**（`/settings`）：外观、存储位置、音效等。

## 架构要点

- `cc-piano.exe`（`app/launcher.py`，PyInstaller）用内置 Python 后台启动 `web/server.py`（标准库 ThreadingHTTPServer，仅监听 127.0.0.1:8765）。
- 前端为无构建的单文件 HTML，`web/app.html` 外壳 + 各页面。
- 任务队列 `job_queue` 串行执行渲染/转写/音轨/拨片开头任务，每个任务是一个子进程；发布队列 `publish_queue` 一次只开一个 Edge 发布窗口。
- 窗口由 `app/window.py`（pywebview / WebView2 无边框窗口）承载，失败时退回 Edge 应用模式窗口。
- 安装版 = 启动器 exe + `runtime\`（嵌入版 Python 3.13 + 全部依赖）+ `douyin\` 项目文件；打包脚本 `app/build_app.py`（Inno Setup 6），超过 2GB 分卷，绝不打包 `publish/profile`。

## 关键模块地图

| 模块 | 职责 |
|---|---|
| `web/server.py` | 793 行，全部 HTTP 接口与任务队列，架构中枢 |
| `piano/render.py` | 主渲染子进程入口，10 步渲染流程 |
| `piano/frames.py` | 逐帧绘制（坐标、发光、特效、标题保护） |
| `piano/midi_notes.py` | MIDI 解析、tick→秒换算、左右手判定 |
| `piano/audio.py` | FluidSynth 合成 + ffmpeg loudnorm 两遍归一化 |
| `piano/jianying.py` | 基于 pyJianYingDraft 生成剪映草稿 |
| `piano/intro.py` | 爆款开头生成（当前 `intro.enabled: false` 关闭） |
| `piano/score2midi.py` | 五线谱 PDF → MIDI（Audiveris + music21） |
| `piano/storage.py` | 成片保存位置统一决策 |
| `tracks/` | 音轨剪辑与拨片开头（build、flick_render、prepare、themes、cover_crop） |
| `publish/` | 五平台发布自动化（publisher、platforms） |
| `app/` | 启动器、窗口、打包、图标、VERSION |

## 外部依赖

- [[fluidsynth]]（2.6.1）+ GeneralUser GS 音色库：钢琴音频合成。
- [[demucs]]（`htdemucs_6s`）：6 轨音源分离。
- [[faster-whisper]]（whisper-medium，CPU int8）：歌词识别。
- [[pyjianyingdraft]]：剪映草稿生成。
- Audiveris + music21：乐谱 OMR 与处理。
- imageio-ffmpeg / libx264 / ffmpeg：编码与合成。
- pywebview / WebView2：无边框窗口；Inno Setup 6：安装包打包。

## 性能与限制

- 1080p60 约 35–40 帧/秒（4 进程），5 分钟曲子约 8 分钟；每进程连同 x264 编码约占 400–600MB 内存，内存紧时 `--workers 2`；`--fps 30` 渲染时间减半。该数据未说明硬件配置与曲目，跨环境复用需谨慎。
- 改编他人作品涉及音乐版权，发布前需确认 MIDI 来源与平台规则。

## 验证状态

2026-10-24 试跑覆盖了命令行 5 秒预览（见 [[cc-piano-5秒预览试跑]]）与网页接口冒烟测试（见 [[cc-piano-网页接口冒烟测试]]）。完整成片 + 剪映草稿、音轨剪辑、拨片开头、录音转写、发布台均未试跑，跟踪见 [[cc-piano未试跑模块是否可用]]。

## 相关页面

渲染链路见 [[midi到下落音符视频渲染管线]]，逐帧算法见 [[逐帧绘制坐标与特效模型]]，调度机制见 [[任务队列与子进程进度协议]]，剪映输出见 [[剪映草稿生成]]，发布见 [[半自动多平台发布]]。