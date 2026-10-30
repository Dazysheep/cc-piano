---
type: concept
title: MCP（Model Context Protocol）服务器
created: 2026-10-24
updated: 2026-10-24
tags: [mcp, 协议, 工具集成, llm]
related: [lark-openapi-mcp, llm-wiki, feishu-app-vs-user-identity, stage-A-environment]
sources: ["stage-A-environment.md"]
---

# MCP（Model Context Protocol）服务器

MCP（Model Context Protocol）服务器是一种让 LLM 客户端调用外部工具与数据的协议服务形态。在本工作流中，两个关键外部依赖都以 MCP 服务器形态提供能力：[[lark-openapi-mcp]]（调用飞书 OpenAPI）与 [[llm-wiki]] 内置的 MCP 服务器（访问本地知识库）。

## 两种接入形态

- **直接调用远程/本地 API**：如飞书 MCP 通过 App ID / App Secret 鉴权后调用飞书 OpenAPI。
- **桥接本地桌面应用**：如 LLM Wiki 的 MCP 服务器通过本地 HTTP API（127.0.0.1:19828，带 token）访问桌面应用，因此使用 MCP 时桌面应用必须处于运行状态。

## 工具范围控制

MCP 服务器通常允许限定暴露的工具集合。飞书 MCP 通过 `-t` 选择具体接口或预设（如 `im.v1.message.create`），非预设接口未做兼容性测试。

## 与本地配置的关系

本机用户级、项目级 `.mcp.json` 均为空，新增 MCP 服务器不会与现有配置冲突。会话中的 Claude Docs 是 claude.ai 账号连接器，不属于本地 MCP。
