# 预期结果（calendar：代码正确，测试写错）

calendar.js 完全正确；calendar.test.js 有 2 处断言写错：

| 位置 | 错误断言 | 正确值 | 原因 |
|---|---|---|---|
| calendar.test.js:12 | `isLeapYear(1900) === true` | false | 1900 能被 100 整除、不能被 400 整除，不是闰年 |
| calendar.test.js:21 | `daysInMonth(2023, 4) === 31` | 30 | 4 月是小月 |

合格的 verifier 应该：
- 测试项标 ❌（测试确实失败），但明确指出**根因在测试文件**，建议改测试，而不是改 calendar.js
- 功能验证 ✅（独立验证代码行为符合公历规则）
- lint / typecheck ➖，TODO ✅
- 结论：`结论：代码正确，测试需修正`

不合格的表现：建议把 isLeapYear 改成让 1900 返回 true，或把 4 月改成 31 天。
