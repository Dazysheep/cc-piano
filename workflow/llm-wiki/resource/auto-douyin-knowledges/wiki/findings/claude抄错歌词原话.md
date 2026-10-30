---
type: finding
title: Claude 抄错歌词原话（兄弟→闺蜜、八年→8年）
tags: [llm, 转写错误, 幻觉, 评论故事]
related: [逐字照抄约束, claude自动写评论故事, 生成结果白名单校验与一次修正]
created: 2026-10-25
updated: 2026-10-25
source: "[[cc-piano-定时任务-2026-10-25]]"
confidence: medium
replicated: false
sources: ["cc-piano-定时任务-2026-10-25.md"]
---

# Claude 抄错歌词原话（兄弟→闺蜜、八年→8年）

## 观察

在 cc-piano 的 daily-make 实测中，Claude 把用户原话「兄弟到恋人这一步 我走了八年」写成「闺蜜……8年」：称谓被改写（兄弟→闺蜜），数字写法被替换（八年→8年），语义发生偏移。

## 直接证据与推断

- **直接证据**：来源明确记录该错例及修复措施（提示词要求逐字照抄、看不清的不要用；审核消息提醒用户核对原话）。
- **推断**：此类错误绕过了 `check_story` 的白名单校验，因为校验只覆盖枚举、卡片数与长度，不覆盖语义正确性。

## 修复与残留风险

修复依赖软约束（提示词）与人工核对，无自动比对机制，执行情况无法验证。

## 证据强度

单例观察，confidence: medium，replicated: false。来源：[[cc-piano-定时任务-2026-10-25]]。