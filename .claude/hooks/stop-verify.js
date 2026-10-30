#!/usr/bin/env node
// Stop hook: 交付验收。
// 本轮若修改了代码/配置/文档，但在最后一次修改之后没有说明测试、lint、typecheck、
// 功能验证或 TODO 检查的结果，则阻止结束，让 Claude 继续完成验证。
const fs = require('fs');
const os = require('os');
const path = require('path');

const MAX_BLOCKS = 3; // 同一轮最多拦截次数，防止死循环

const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit']);
// Bash / PowerShell 中写文件的常见形式
const SHELL_WRITE_RE = /(\bsed\s+-i\b|[^2&]>{1,2}\s*[^&\s]|\btee\b|Set-Content|Add-Content|Out-File|New-Item\b.*-ItemType\s+File|\bmv\b|\bcp\b|\brm\b|Remove-Item)/i;
const VERIFY_RE = new RegExp(
  [
    '测试', '验证', '类型检查', '检查结果', '自测', '冒烟',
    '\\btests?\\b', '\\btesting\\b', '\\blint', '\\btypecheck', '\\btype-check', '\\btsc\\b',
    'eslint', 'prettier', 'pytest', 'jest', 'vitest', 'mocha', 'cargo (test|check|clippy)',
    'go (test|vet)', 'mypy', 'ruff', 'npm (run )?test', 'verif', 'TODO',
  ].join('|'),
  'i'
);

function readJsonl(file) {
  try {
    return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => {
      try { return JSON.parse(l); } catch { return null; }
    }).filter(Boolean);
  } catch { return []; }
}

function contentBlocks(entry) {
  const c = entry && entry.message && entry.message.content;
  if (typeof c === 'string') return [{ type: 'text', text: c }];
  return Array.isArray(c) ? c : [];
}

// 真正的用户输入（不是 tool_result、不是 meta）
function isUserPrompt(entry) {
  if (entry.type !== 'user' || entry.isMeta) return false;
  const blocks = contentBlocks(entry);
  return blocks.length > 0 && blocks.every((b) => b.type === 'text');
}

function counterFile(sessionId) {
  return path.join(os.tmpdir(), `claude-stop-verify-${sessionId || 'default'}.cnt`);
}

function allow(sessionId) {
  try { fs.unlinkSync(counterFile(sessionId)); } catch {}
  process.exit(0);
}

let input = {};
try { input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}'); } catch {}
const sessionId = input.session_id;
const entries = readJsonl(input.transcript_path);

// 截取本轮：最后一条用户输入之后的记录
let start = 0;
for (let i = entries.length - 1; i >= 0; i--) {
  if (isUserPrompt(entries[i])) { start = i + 1; break; }
}
const turn = entries.slice(start);

// 找到本轮最后一次修改文件的位置，并收集修改过的文件
let lastEditIdx = -1;
const changed = new Set();
turn.forEach((e, i) => {
  if (e.type !== 'assistant') return;
  for (const b of contentBlocks(e)) {
    if (b.type !== 'tool_use') continue;
    const inp = b.input || {};
    if (EDIT_TOOLS.has(b.name)) {
      lastEditIdx = i;
      changed.add(inp.file_path || inp.notebook_path || '(unknown)');
    } else if ((b.name === 'Bash' || b.name === 'PowerShell') && SHELL_WRITE_RE.test(inp.command || '')) {
      lastEditIdx = i;
      changed.add(`(${b.name}) ${String(inp.command).slice(0, 60)}`);
    }
  }
});

if (lastEditIdx === -1) allow(sessionId); // 本轮没改东西

// 最后一次修改之后，Claude 的文字说明里是否给出了验证结果
let textAfter = '';
for (const e of turn.slice(lastEditIdx + 1)) {
  if (e.type !== 'assistant') continue;
  for (const b of contentBlocks(e)) if (b.type === 'text') textAfter += b.text + '\n';
}
if (input.last_assistant_message) textAfter += String(input.last_assistant_message);

if (VERIFY_RE.test(textAfter)) allow(sessionId);

// 未验证：计数，超过上限则放行，避免无限循环
let count = 0;
try { count = parseInt(fs.readFileSync(counterFile(sessionId), 'utf8'), 10) || 0; } catch {}
if (count >= MAX_BLOCKS) allow(sessionId);
try { fs.writeFileSync(counterFile(sessionId), String(count + 1)); } catch {}

const files = [...changed].slice(0, 10).map((f) => `  - ${f}`).join('\n');
const reason = [
  `【交付验收未通过】本轮修改了以下文件，但在最后一次修改之后没有说明验证结果：`,
  files,
  ``,
  `请继续工作，完成以下适用的验证，并在最终回复中逐项写明结果：`,
  `  1. 测试（运行相关单元/集成测试）`,
  `  2. lint / 格式检查`,
  `  3. typecheck（如项目有类型系统）`,
  `  4. 功能验证（实际运行或调用修改后的功能）`,
  `  5. TODO 检查（确认没有遗留 TODO/FIXME/占位代码）`,
  `某项不适用或无法执行时，写明原因（例如"该项目没有测试框架"）。`,
  `(拦截 ${count + 1}/${MAX_BLOCKS})`,
].join('\n');

process.stdout.write(JSON.stringify({ decision: 'block', reason }));
process.exit(0);
