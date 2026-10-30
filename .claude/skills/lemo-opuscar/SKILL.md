---
name: lemo-opuscar
description: Direct and produce a short film made entirely in code, in one of the 59 styles of the Lemo-Opuscar library (e.g. 水彩笔刷 Watercolor Brush, 蜡笔儿童绘本 Crayon Picture Book, 油画厚涂, 浮世绘, 16-bit 像素 RPG, 皮影戏, 卫星简报). Use when the user asks for a video, film, short, promo, explainer or animation (视频、短片、动画、宣传片) in a named style, wants help choosing a style, wants to make or change their own style, or asks which film styles there are; also as a technique reference when drawing new hand-drawn scenes for the douyin videos. Not for plain editing or converting existing video files.
---

# Lemo-Opuscar（本机部署版）

库已经装在 `D:\cc-engine\filmlab\lemo-opuscar`（github.com/lemomo-ai/lemo-opuscar，含全部 demo 源码）。不要再按官方 setup.sh 去 clone 到 `~/lemo-opuscar`（那是 C 盘）。

1. **环境**：每个 shell 先 `. /d/cc-engine/filmlab/env.sh`。它设好 `LIB`、ffmpeg（douyin 自带）、无头浏览器 / npm / pip / uv / Hugging Face 缓存（全在 D 盘）。
2. **依赖**：`sh /d/cc-engine/filmlab/setup-deps.sh` 已装核心层；片子要旁白再加 `voice`，要拨弦合成再加 `music`（第一次要下载几百 MB，先告诉用户）。官方的 `plugin/skills/lemo-opuscar/scripts/setup.sh` 在 Windows 上不能用（写死 `.venv/bin/python`），不要跑它。
3. **按库走**：读 `$LIB/AGENTS.md`，照它的 Start → 选风格 → 一轮提问 → TREATMENT.md → 出片 → 交付（`$LIB/DIRECTOR.md` §11）。

本机和指南不一样的地方：

| 指南里写的 | 本机 |
|---|---|
| `films/<name>/` | `D:\cc-engine\filmlab\films\<name>\`（抖音项目的片段可以直接放该首歌的 `douyin/output/...` 目录） |
| `.venv/bin/python …` | `"$LPY" …`（`$LIB/.venv/Scripts/python.exe`） |
| `~/lemo-my-styles/` | `$LEMO_MY_STYLES` = `D:\cc-engine\filmlab\my-styles\` |
| 运行工具 | `cd "$LIB" && node core/render/still.mjs "<项目绝对路径>" 1.5 3` |
| 页面里引用库文件 | 绝对 URL：`/core/lib.js`、`/node_modules/three/…`（项目挂在 `/@film/`） |
| demo 源码 | 已在 `$LIB/styles/<slug>/demo/`；照指南，写完 TREATMENT.md 之后才看，只学技法不抄故事 |
| 中文旁白 | 默认 Kokoro 离线中文；edge-tts 会把文字发给微软，先问用户 |

- 渲染很吃内存和显卡：和 douyin 的整片渲染不要同时跑（douyin 用 `output/.render.lock`）。
- 不改 `$LIB/core/` 和 `$LIB/styles/`；不留后台进程。
- 交付时告诉用户成片在哪。
