---
name: film-handdrawn
description: Hand-drawn watercolour animation in code (p5.js + p5.brush, picture-book look, the Clawd/CC character with full pose, face, hats, emotes and dance rig), based on JohnHeibel/PDoomVideo. Use when the user wants 手绘风格 / 水彩 / 绘本 animation, new hand-drawn scenes, expressions or animations for a douyin song video (每首歌重新手绘画面、丰富表情库和动画库), or a lyric-synced music video drawn in code.
---

# 手绘风格（PDoomVideo 底座）

工程在 `D:\cc-engine\filmlab\pdoom-handdrawn`（只读参考，不在里面做新片）。先读它的 `ANIMATION_GUIDE.md`（画法 API、Clawd 角色、风格规则、自查方法）和 `STORYBOARD.md`（一支 MV 的分镜写法）。

## 做法

1. **每首歌一个项目文件夹**：`D:\cc-engine\douyin\handdrawn\<歌名>\`。把底座的 `studio.html`、`render.mjs`、`src/core.js`、`src/clawd.js`、`src/cast.js`、`src/props.js` 拷进去，再按这首歌写自己的 `src/timeline.js`、`src/lyrics.js`、`src/ch/*.js`（一段歌词 / 一条评论一个章节）。`node_modules` 用 junction 指向底座的（`cmd /c mklink /J node_modules D:\cc-engine\filmlab\pdoom-handdrawn\node_modules`），不用每首歌再装。
2. **画面每首歌重新画**（用户 2026-10-28 的要求）：不要套旧的像素表情库和统一模板。按这首歌的歌词意象和评论里的具体往事，设计新的场景、道具、表情和动作；能复用的是画法和角色骨架，不是画面。
3. **CC 小人**：用 `clawd()` 画（body 10u×6u，见指南 Characters）。douyin 的男女两位主角：男生 = 原版 Clawd 配色，读评论；女生 = 加蝴蝶结、睫毛、蓝眼睛，唱歌（用 `draw` 钩子加蝴蝶结，`col/dk/lt` 改色）。
4. **帧必须是时间的纯函数**：不用 `Math.random()`，用 `hash(i)` / `jit()`；节拍函数 `bpOf/pulse` 里的 BPM 和首拍偏移按这首歌改（douyin 的分析在 `output/tracks_<歌>/work/analysis.json`、`beats.json`）。
5. **渲染**：本机没有 Chrome，用 Edge：`. /d/cc-engine/filmlab/env.sh` 后 `node render.mjs --sheet=... --chrome="$EDGE"`。先出 contact sheet 用 Read 看图自查（指南 Checking your work），满意再 `--clip` / `--frames` + `--encode`。`DUR` 和音频路径改成这首歌的片段。
6. **进动画库**：每个新画的场景导出一张预览图（和一段透明或带底的短片）到 `douyin/assets/handdrawn/<歌名>/<场景名>.webp|.mp4`，登记进动画库，让编剧页、分段修改页能挑到；同时在知识库（`workflow/kb/kb.py`）记一笔这首歌新画了什么。
7. 渲染很吃显卡和内存：先拿 douyin 的渲染锁（`output/.render.lock`），不要和整片渲染同时跑。

## 注意

- 底座 README：工程由 Claude Opus 5.5 生成，代码 ISC；歌曲 / 歌词版权属原作者，不要拿它的音频和歌词出片。
- 卡拉 OK 条在底部 y 975–1070；douyin 竖屏的字幕、评论卡位置按 douyin 的版式重新留空。
