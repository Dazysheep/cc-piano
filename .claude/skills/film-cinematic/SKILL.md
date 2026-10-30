---
name: film-cinematic
description: "Cinematic code-rendered music video engine (three.js + post-processing with bloom, halation, film grain, motion blur; word-synced karaoke typography; scenes anchored to lyric lines and snapped to the beat grid), based on mexicat/pdoom-video. Use when the user wants 电影风格 / 电影感 / cinematic MV, lyric typography, glow-and-grain looks, or 3D shader scenes for a song video."
---

# 电影风格（pdoom-video 引擎）

工程在 `D:\cc-engine\filmlab\pdoom-cinematic`（只读参考）。先读 `docs/ENGINE.md`（场景 API、歌词 / 音频数据、渲染命令）和 `docs/TREATMENT.md`（风格圣经和逐场处理的写法）。

## 做法

1. **每首歌一个项目**：`D:\cc-engine\douyin\cinematic\<歌名>\`，把 `app/` 拷过去（不拷 `node_modules`、`public/plates`），`src/scenes/` 和 `src/timeline.ts` 按这首歌重写；每首歌的画面都重新设计（用户要求不套统一模板）。
2. **数据**：引擎要 `data/lyrics.json`（逐词时间）和 `data/audio.json`（beats / downbeats / sections / onsets / 包络）。不要跑它的 `analysis/`（要 torch、demucs、mlx-whisper，约 4GB，mlx 只能在 Mac 上跑）；用 douyin 已有的结果转换：`output/tracks_<歌>/work/` 里的 `whisper_words.json` / `lyrics.json`（逐词）、`beats.json`、`analysis.json`、`env_*.npy`、`stems/`。
3. **运行时**：需要 bun。第一次用时装进项目目录：`npm i -D bun`（缓存走 `. /d/cc-engine/filmlab/env.sh` 设的 D 盘目录），再 `npx bun install`、`npx bunx vite`。它的渲染脚本用 playwright-core 的 `channel: 'chrome'`，本机没有 Chrome：改成 `channel: 'msedge'`，或用 `$PLAYWRIGHT_BROWSERS_PATH` 里的 headless shell。
4. **自查**：`stills` / `sheet` 出图后用 Read 看（ENGINE.md 的 Running things）。douyin 竖屏 1080×1920：场景按竖屏重新布局，不是把横屏裁一刀。
5. **吃资源**：4K 一首歌要 ~23GB 内存，本机做不了；1080p、`--samples 4` 先出草稿，`--workers 1`，拿 douyin 的渲染锁（`output/.render.lock`）。

## 注意

代码 MIT；字体各自许可（OFL）；它自带的歌曲 / 歌词不属于代码许可，不要拿来出片。
