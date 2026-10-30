---
type: concept
title: 不控制 iPhone 的边界决策
created: 2026-10-24
updated: 2026-10-24
tags: [边界决策, iphone, 自动化, 风控]
related: [运营决策记录-2026-10-24, witchan-ios-mcp, 发布台人工把关]
sources: ["运营决策记录-2026-10-24.md"]
---

# 不控制 iPhone 的边界决策

不控制 iPhone 是本项目的一条自动化边界决策：自动化管线不直接操控 iPhone 设备，录屏采集与最终发布均由人工完成。

## 调研过的方案与否决理由

- **ios-mcp**（见 [[witchan-ios-mcp]]）：需越狱，越狱有安全风险并可能触发抖音风控，不采用。
- **iphone-mcp / mirroir-mcp**：需 Mac 环境，不采用。

## 保留的人工环节

- 录屏采集：用户手动 iPhone 录屏并发群。
- 发布：用户检查后自己点「发布」（见 [[发布台人工把关]]）。