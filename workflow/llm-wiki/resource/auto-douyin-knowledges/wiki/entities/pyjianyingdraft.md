---
type: entity
title: pyJianYingDraft
created: 2026-10-24
updated: 2026-10-24
tags: [剪映, 草稿, python库, 视频编辑]
related: [cc-piano, 剪映草稿生成]
sources: ["cc-piano-软件流程与底层逻辑.md"]
---

# pyJianYingDraft

pyJianYingDraft 是一个用于生成剪映（JianYing）草稿文件的 Python 库，让程序化生成的视频工程可以在剪映中继续编辑。cc-piano 通过它输出可编辑的剪映草稿。

## 在 cc-piano 中的用法

- 调用位置：`piano/jianying.py`。
- 轨道从下到上：背景、音符（滤色）、琴键、蒙版、片头、标题、副标题、水印、钢琴、背景音。
- 草稿先写到 `output/<曲名>/draft/`，再用 robocopy 镜像进剪映草稿目录（商店版 Python 不能直接写 AppData）。
- 详细流程见 [[剪映草稿生成]]，主体见 [[cc-piano]]。