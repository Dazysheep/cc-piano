---
type: source
title: "阶段 A：环境检查与 README 审查"
created: 2026-10-24
updated: 2026-10-24
tags: [环境检查, 依赖审查, 飞书, llm-wiki, mcp, 工作流]
related: [lark-openapi-mcp, llm-wiki, mcp-server, feishu-app-vs-user-identity, environment-dependency-audit, can-feishu-mcp-write-docs]
sources: ["stage-A-environment.md"]
authors: []
year: 2026
url: ""
venue: ""
---

# 阶段 A：环境检查与 README 审查

## 概述

本文件是一份**只读的环境检查与依赖审查记录**（检查日期 2026-10-16），为一条分阶段工作流（阶段 A–E）做前置可行性评估。检查期间未安装任何软件、未修改任何配置。内容涵盖：本机环境清单、飞书官方 OpenAPI MCP 的能力与限制、LLM Wiki 桌面应用的能力与许可、阶段 D 的现有脚本基础，以及进入下一阶段前需用户决策的事项。

该文档属于工作流内部产物，但其中关于两个外部工具（[[lark-openapi-mcp]]、[[llm-wiki]]）的能力边界与限制具有可复用的知识价值。

## 环境清单

| 项目 | 结果 |
|---|---|
| 工作目录 | `D:\cc-engine`（本工作流的文件放在 `D:\cc-engine\workflow\`） |
| 系统 | Windows 11 专业版 10.0.26100 |
| 磁盘 | C: 剩 16.2 GB（偏紧，安装内容一律放 D:）；D: 剩 170 GB；E: 剩 119 GB |
| 网络 | github.com、registry.npmjs.org 可访问；open.feishu.cn 可连通（HEAD 请求返回 404，属正常） |
| git | 2.56.0 |
| Node.js / npm | v24.21.0 / 11.19.0（满足飞书 MCP 的 Node LTS 要求、LLM Wiki 源码构建的 Node 20+ 要求） |
| Python | 3.13.14（另有 `douyin\.venv` 项目环境） |
| Claude Code | 2.1.296 |
| 现有 MCP | 本机没有配置任何本地 MCP 服务器（用户级、项目级 `.mcp.json` 均为空）；会话里的 Claude Docs 是 claude.ai 账号连接器。新增飞书 MCP 不会与现有配置冲突 |

缺少的依赖：无。Rust、protoc 只有在从源码构建 LLM Wiki 时才需要；用官方 Windows 安装包则不需要。

## 飞书官方 OpenAPI MCP 要点

详见 [[lark-openapi-mcp]]。核心事实：

- 状态 **Beta**，许可证 MIT，npm 包 `@larksuiteoapi/lark-mcp`。
- 运行命令：

  ```
  npx -y @larksuiteoapi/lark-mcp mcp -a <App ID> -s <App Secret>
  ```

- 用户身份登录命令：

  ```
  npx -y @larksuiteoapi/lark-mcp login -a … -s …
  ```

  运行时加 `--oauth --token-mode user_access_token`；国际版 Lark 加 `--domain https://open.larksuite.com`。
- 工具范围通过 `-t` 选择具体接口或预设，例如 `im.v1.message.create`（发消息）。
- **与本方案相关的限制（README 原文）**：
  - 不支持直接编辑飞书云文档，只支持导入和读取；
  - 暂不支持文件上传/下载；
  - 非预设接口未做兼容性测试。
- 推论：「每天发报告摘要到飞书会话」可行；「把完整报告写成飞书文档」需要实测，可能只能退回到发 Markdown 摘要或改用导入接口（见 [[can-feishu-mcp-write-docs]]）。
- 安全提醒：README 示例把 App Secret 直接写在命令参数里；实施时应改为从环境变量读取，不写进任何项目文件。

## LLM Wiki 要点

详见 [[llm-wiki]]。核心事实：

- 桌面应用（Tauri v2：Rust 后端 + React 前端），另带 Chrome 扩展、本地 HTTP API 和 MCP 服务器；约 2 万 star，活跃开发中。
- 许可证 **GPL-3.0**：自用没有问题；若将来修改代码再分发，需同样开源。
- Windows 提供 `.msi` 安装包，不需要从源码构建。
- 功能：导入 PDF / DOCX / PPTX / XLSX / EPUB / 图片 / 音视频 / 网页剪藏等；由 LLM 分两步生成互相链接的 wiki 页面；每页 frontmatter 里有 `sources[]` 用于来源追溯；关键词 + 知识图谱 + 可选向量（LanceDB）混合检索。
- 数据存储：每个知识库是一个文件夹（`raw/sources/` 原始资料、`wiki/` 生成页面、`.llm-wiki/` 配置与聊天记录），可直接用文件备份。
- MCP 位于 `mcp-server/`，通过本地 HTTP API（127.0.0.1:19828，带 token）访问桌面应用，因此**使用 MCP 时桌面应用需要开着**（见 [[mcp-server]]）。
- 需要 LLM API（OpenAI / Anthropic / Google / Ollama / 自定义均可）；导入和生成页面都要调用模型，**会产生 API 费用**（Ollama 本地模型除外）。
- 结论：功能与方案要求基本吻合（导入、检索、来源追踪、MCP 都有），没有发现需要换项目的硬伤。

## 阶段 D 的现有基础

`D:\cc-engine\douyin\analytics\report.py` 已能读取创作者中心导出的作品数据（xlsx/csv），计算点赞率、互动率并生成 HTML 报表，可作为阶段 D、E 的起点。

抖音创作者中心目前没有面向个人的数据接口，建议每天手动导出一次作品数据表（或确认可用的其他官方方式），放进固定文件夹，由脚本自动读取。

## 进入下一阶段前需决策的事项

1. **阶段 B（飞书）**：在 <https://open.feishu.cn/> 创建企业自建应用，开通发消息权限（`im:message` 相关），拿到 App ID 和 App Secret；确定用应用身份还是个人身份发消息（见 [[feishu-app-vs-user-identity]]）；指定一个**测试会话**。Secret 请设为环境变量，不要贴到聊天或文件里。
2. **阶段 C（LLM Wiki）**：确认接受 GPL-3.0；选择模型提供商（会产生费用；或用本地 Ollama 免费但效果较弱）；确认安装位置（建议 `D:\Apps\LLM-Wiki`，知识库数据放 `D:\cc-engine\workflow\wiki`）。
3. **阶段 D（数据）**：抖音创作者中心目前没有面向个人的数据接口，建议每天手动导出一次作品数据表，放进固定文件夹，由脚本自动读取。

## 主要结论与证据强度

- 本机环境满足两个外部依赖的前置要求，无缺失依赖（证据强度：中，单次只读检查，未实测安装）。
- C: 盘仅剩 16.2 GB，偏紧，安装内容一律放 D:（证据强度：高，直接观测）。
- 本机无任何本地 MCP 配置，新增飞书 MCP 不会冲突（证据强度：高）。
- 飞书 MCP 处于 Beta，作为阶段 B 核心组件存在稳定性风险（张力，非矛盾）。
- LLM Wiki 功能与方案要求基本吻合（证据强度：中，基于 README，未实测）。

## 审查方法

本记录采用只读检查、不改配置、逐项核对 README 限制的审查方法，详见 [[environment-dependency-audit]]。
