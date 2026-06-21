// context-check — deterministic Completeness Gate for the context contract.
// Scans .kiro/context/*.md and FAILS (exit 1) if any unfilled `<!-- TODO` marker remains.
// Surfaces `UNKNOWN — needs owner input` markers (accepted gaps, but never silent).
//
// Usage:  node .kiro/tools/context-check.mjs [projectDir]
// Exit:   0 = complete (no TODO)   1 = incomplete / missing dir

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

const REQUIRED = ['project.md', 'stack.md', 'conventions.md', 'architecture.md', 'glossary.md', 'legacy-ref.md'];
const TODO_RE = /<!--\s*TODO/g;          // matches `<!-- TODO -->` AND `<!-- TODO: hint -->`
const UNKNOWN_RE = /UNKNOWN — needs owner input/g;

function count(s, re) { return (s.match(re) || []).length; }

const projectDir = resolve(process.argv[2] || '.');
const ctxDir = join(projectDir, '.kiro', 'context');
if (!existsSync(ctxDir)) {
  console.error(`✗ no .kiro/context/ at ${projectDir}`);
  process.exit(1);
}

const present = readdirSync(ctxDir).filter((f) => f.endsWith('.md'));
let totalTodo = 0, totalUnknown = 0, missingFiles = [];

console.log('  context completeness check');
console.log('  ' + '─'.repeat(46));
for (const f of REQUIRED) {
  if (!present.includes(f)) { missingFiles.push(f); console.log(`  ✗ ${f.padEnd(20)} MISSING`); continue; }
  const src = readFileSync(join(ctxDir, f), 'utf8');
  const todo = count(src, TODO_RE);
  const unk = count(src, UNKNOWN_RE);
  totalTodo += todo; totalUnknown += unk;
  const mark = todo === 0 ? '✅' : '❌';
  console.log(`  ${mark} ${f.padEnd(20)} TODO=${todo}${unk ? `  UNKNOWN=${unk}` : ''}`);
}

console.log('  ' + '─'.repeat(46));
if (totalUnknown) {
  console.log(`  ⚠ ${totalUnknown} field(s) marked "UNKNOWN — needs owner input" — surface these at hand-off.`);
}
const fail = totalTodo > 0 || missingFiles.length > 0;
if (fail) {
  console.log(`  ✗ INCOMPLETE — ${totalTodo} TODO marker(s) left${missingFiles.length ? `, ${missingFiles.length} file(s) missing` : ''}. Do NOT hand off.`);
  process.exit(1);
}
console.log('  ✓ COMPLETE — every required context file is filled.');
process.exit(0);
