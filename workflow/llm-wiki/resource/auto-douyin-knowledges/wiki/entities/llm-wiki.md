---
type: entity
title: LLM Wiki（nashsu/llm_wiki）
created: 2026-10-24
updated: 2026-10-24
tags: [llm-wiki, 桌面应用, tauri, 知识库, gpl-3.0, mcp]
related: [lark-openapi-mcp, mcp-server, stage-A-environment]
sources: ["stage-A-environment.md"]
---

# LLM Wiki（nashsu/llm_wiki）

LLM Wiki（仓库 `nashsu/llm_wiki`）是一个桌面应用，用于把多种格式的资料导入并借助 LLM 生成互相链接的 wiki 知识库。它基于 Tauri v2（Rust 后端 + React 前端），另带 Chrome 扩展、本地 HTTP API 和 MCP 服务器；约 2 万 star，处于活跃开发中。

## 许可证

**GPL-3.0**：自用没有问题；若将来修改代码再分发，需要同样开源。

## 安装

Windows 提供 `.msi` 安装包，不需要从源码构建。仅从源码构建时才需要 Rust、protoc。

## 功能

- 导入 PDF / DOCX / PPTX / XLSX / EPUB / 图片 / 音视频 / 网页剪藏等格式；
- 由 LLM 分两步生成互相链接的 wiki 页面；
- 每页 frontmatter 里有 `sources[]` 用于来源追溯；
- 关键词 + 知识图谱 + 可选向量（LanceDB）混合检索。

## 数据布局

每个知识库是一个文件夹，可直接用文件备份：

- `raw/sources/` — 原始资料
- `wiki/` — 生成页面
- `.llm-wiki/` — 配置与聊天记录

## MCP 服务器

MCP 服务器位于 `mcp-server/`，工具包括列出项目、读文件、混合检索、查看图谱、触发重新扫描、调用 Agent 对话等。MCP 通过本地 HTTP API（127.0.0.1:19828，带 token）访问桌面应用，因此**使用 MCP 时桌面应用需要开着**。详见 [[mcp-server]]。

## 成本

需要 LLM API（OpenAI / Anthropic / Google / Ollama / 自定义均可）。导入和生成页面都要调用模型，**会产生 API 费用**（Ollama 本地模型除外，但效果较弱）。

## 评估结论

功能与方案要求基本吻合（导入、检索、来源追踪、MCP 都有），没有发现需要换项目的硬伤。该结论基于 README，尚未实测。
