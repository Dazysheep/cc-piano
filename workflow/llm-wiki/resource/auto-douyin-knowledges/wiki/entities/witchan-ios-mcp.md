---
type: entity
title: witchan/ios-mcp
created: 2026-10-24
updated: 2026-10-24
tags: [iPhone, MCP, 越狱, 被否决方案]
related: [抖音运营自动化方案-2026-10-24, 飞书官方-openapi-mcplark-openapi-mcp]
sources: ["抖音运营自动化方案-2026-10-24.md"]
---

# witchan/ios-mcp

witchan/ios-mcp 是一个用于控制 iPhone 的 MCP 项目，在本方案中被调研并最终否决。

## 被否决的原因

- 必须越狱（支持 iOS 13–18）。
- 通过局域网 8090 端口连接，没有认证。
- 能执行任意 Shell 命令。
- 越狱有安全风险，还可能触发抖音风控、危及账号。

## 同批被否决的方案

- `Lakr233/iphone-mcp`（基于 Appium）：需要 Mac。
- `mirroir-mcp`：需要 Mac。

## 结论

通知、收文件、学习都走飞书群与电脑端，不控制手机。该结论也写入知识库。