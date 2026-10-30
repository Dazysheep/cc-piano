# sub-agent 工作区

用于开发和测试 subagent。

- Agent 定义放在 `.claude/agents/<name>.md`（frontmatter：`name`、`description`、可选 `tools`、`model`）
- 需在 `D:\cc-engine\sub-agent` 目录下启动 Claude Code，这里的 agent 才会被加载
- 临时文件仍放 `D:\cc-engine\.tmp\`
