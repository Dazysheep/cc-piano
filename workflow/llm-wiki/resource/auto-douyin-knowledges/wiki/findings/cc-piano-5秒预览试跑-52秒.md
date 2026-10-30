---
type: finding
title: cc-piano 5 秒预览试跑总耗时 52 秒
created: 2026-10-24
updated: 2026-10-24
tags: [性能, 试跑, 渲染, cc-piano]
related: [cc-piano琴房-studio, midi到下落音符视频渲染管线]
sources: ["cc-piano-软件流程与底层逻辑.md"]
source: "cc-piano-软件流程与底层逻辑"
confidence: medium
replicated: false
---
# cc-piano 5 秒预览试跑总耗时 52 秒

## 观察

2026-10-24 在 [[cc-piano琴房-studio]] 上用命令行渲染 5 秒预览：

```
.venv\Scripts\python piano\render.py songs\TRASH_Patience.mid --preview 5 --no-draft --workers 2
```

- 曲目含 535 个音符，加前后留白共 11 秒、660 帧。
- 钢琴音频合成 9 秒完成，画面渲染 36 秒完成，总耗时 52 秒（**2 进程**）。
- 产物 `output/TRASH_Patience/preview.mp4`：1920×1080、60fps、H.264 + AAC 48kHz 立体声，11.00 秒，约 1.1MB。
- 中间素材：notes.mp4、keys.mp4、piano.wav、text.png、scrim.png、background_default.jpg。
- 抽帧检查：标题「Patience / TRA$H」、下落音符发光、琴键高亮、击键光点、右下角水印「@谬紫克！」均正常。

## 证据强度与限制

- 直接证据：单次实测，属直接观察。
- 限制：仅一个样本、仅 2 进程；画面 660 帧 / 36 秒 ≈ 18 帧/秒，与文档第 7 节「1080p60 约 35–40 帧/秒（4 进程）」口径不同，**进程数不同不可直接比较**。
- 未复现（replicated: false）。
