---
type: entity
title: 飞书官方 OpenAPI MCP（lark-openapi-mcp）
created: 2026-10-24
updated: 2026-10-24
tags: [飞书, mcp, 工具, openapi, beta]
related: [llm-wiki, mcp-server, feishu-app-vs-user-identity, can-feishu-mcp-write-docs, stage-A-environment]
sources: ["stage-A-environment.md"]
---

# 飞书官方 OpenAPI MCP（lark-openapi-mcp）

飞书官方 OpenAPI MCP（仓库 `larksuite/lark-openapi-mcp`）是飞书开放平台提供的 MCP 服务器，让 LLM 客户端通过 [[mcp-server]] 协议调用飞书 OpenAPI（如发送消息）。它以 npm 包 `@larksuiteoapi/lark-mcp` 发布，许可证为 MIT，README 明确标注状态为 **Beta**，功能与接口可能变化。

## 运行方式

```
npx -y @larksuiteoapi/lark-mcp mcp -a <App ID> -s <App Secret>
```

需要先在飞书开放平台创建企业自建应用，开通发消息权限（`im:message` 相关），取得 App ID 与 App Secret。

## 身份模式

详见 [[feishu-app-vs-user-identity]]。

- 默认使用**应用身份**（`tenant_access_token`）。
- 用户身份需先执行登录命令走 OAuth：

  ```
  npx -y @larksuiteoapi/lark-mcp login -a … -s …
  ```

  回调地址为 `http://localhost:3000/callback`；运行时需加 `--oauth --token-mode user_access_token`。

## 域名区分

默认连接飞书中国版；国际版 Lark 需加 `--domain https://open.larksuite.com`，两边的应用不通用。

## 工具范围

通过 `-t` 选择具体接口或预设，例如 `im.v1.message.create`（发消息）。

## 关键限制（README 原文）

- **不支持直接编辑飞书云文档**，只支持导入和读取；
- **暂不支持文件上传/下载**；
- 非预设接口未做兼容性测试。

推论：「每天发报告摘要到飞书会话」可行；「把完整报告写成飞书文档」需要实测，可能只能退回到发 Markdown 摘要或改用导入接口。该未决问题由 [[can-feishu-mcp-write-docs]] 跟踪。

## 安全实践

README 示例把 App Secret 直接写在命令参数里。实施时应改为从环境变量读取，不写进任何项目文件，也不要贴到聊天中。

## 风险

Beta 状态意味着接口可能变化，而它被选为阶段 B 的核心组件，稳定性风险与方案确定性之间存在张力。
