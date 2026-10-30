# 预期结果（给人看的答案，别让 verifier 先读）

| 检查项 | 预期 | 原因 |
|---|---|---|
| 测试 | ❌ | 3 个用例全挂：subtotal 漏算最后一件；applyDiscount(100) 未打折 |
| lint | ➖ | 没有配置 eslint |
| typecheck | ➖ | 纯 JS，无 tsconfig |
| 功能验证 | ❌ | 直接调用 total() 结果错误 |
| TODO 检查 | ❌ | cart.js 中有 `TODO: 运费规则还没实现` |

结论：`结论：不可交付（3 项失败）`
