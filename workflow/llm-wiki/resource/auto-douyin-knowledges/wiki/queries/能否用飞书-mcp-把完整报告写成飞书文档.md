---
type: query
title: 能否用飞书 MCP 把完整报告写成飞书文档？
created: 2026-10-24
updated: 2026-10-24
tags: [飞书, mcp, 未决问题, 文档写入]
related: [lark-openapi-mcp, stage-A-environment]
sources: ["stage-A-environment.md"]
---

# 能否用飞书 MCP 把完整报告写成飞书文档？

## 问题

方案期望把完整报告写成飞书云文档，但 [[lark-openapi-mcp]] 的 README 明确说明：不支持直接编辑飞书云文档，只支持导入和读取；暂不支持文件上传/下载。因此该路径的可行性尚未确定。

## 当前证据

- 限制为 README 原文，证据强度高。
- 「每天发报告摘要到飞书会话」可行（`im.v1.message.create`）。
- 「把完整报告写成飞书文档」需实测，可能只能退回到发 Markdown 摘要或改用导入接口。

## 待验证

1. 导入接口能否覆盖完整报告的写入需求。
2. 非预设接口是否可用（README 称未做兼容性测试）。
3. 若不可行，退路是发 Markdown 摘要还是改用其他方式。

## 状态

未决，等待阶段 B 实测。
