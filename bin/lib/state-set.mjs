#!/usr/bin/env node
// kiro-sdlc-kit — state-set: surgical, deterministic updates to a change's _state.json.
//
// WHY: the orchestrator (sdlc-full / sdlc-fast) runs with a READ-ONLY shell and has NO Edit tool, so
// without this it must rewrite the WHOLE _state.json via the Write tool on every gate/phase change —
// clobber-prone (one dropped field re-asks rigor/testcase_export or mis-gates). This does a safe
// read-modify-write IN CODE: only the named keys change; every other field is preserved byte-for-byte
// in value. Invoked via the allowed `Bash(node <platform>/tools/...)` path — the shell-guard permits
// kit node tools (it only blocks `node -e/--eval/-p` and node-reads-stdin), and _state.json is the
// baton the orchestrator is already allowed to write.
//
// Usage:
//   node .claude/tools/state-set.mjs [projectDir] --change <name> --set <dotpath>=<value> [--set ...] [--unset <dotpath>]
//   node .claude/tools/state-set.mjs --set current_phase=S3 --set gates.S2=passed   (active change auto-resolved)
//
// Each <value> is JSON.parse'd when possible (true/false/null, numbers, JSON arrays/objects), else
// taken as a literal string ("passed", "S3"). Dot-paths create nested objects as needed.

import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

function die(m) { console.log(`  ✗ ${m}`); process.exit(1); }
function readJson(p) { try { return JSON.parse(readFileSync(p, 'utf8')); } catch { return null; } }

// ---- args ----
const argv = process.argv.slice(2);
let projectDir = '.', changeName = null;
const sets = [], unsets = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--change') changeName = argv[++i];
  else if (a === '--set') sets.push(argv[++i]);
  else if (a === '--unset') unsets.push(argv[++i]);
  else if (!a.startsWith('--')) projectDir = a;
  else die(`unknown flag ${a}`);
}
projectDir = resolve(projectDir);
if (!sets.length && !unsets.length) die('nothing to do: pass at least one --set key=value or --unset key');

// ---- resolve the change dir (explicit --change, else the most-recent _state.json) ----
const changesBase = join(projectDir, 'openspec', 'changes');
let stateFile = null;
if (changeName) {
  const f = join(changesBase, changeName, '_state.json');
  if (!existsSync(f)) die(`no _state.json for change "${changeName}" at ${f}`);
  stateFile = f;
} else {
  if (!existsSync(changesBase)) die(`no openspec/changes/ at ${projectDir}`);
  const cands = [];
  for (const n of readdirSync(changesBase)) {
    const f = join(changesBase, n, '_state.json');
    if (existsSync(f)) cands.push([statSync(f).mtimeMs, f]);
  }
  if (!cands.length) die('no active change (_state.json) found; pass --change <name>');
  cands.sort((a, b) => b[0] - a[0]);
  stateFile = cands[0][1];
}

const state = readJson(stateFile);
if (state === null) die(`could not parse ${stateFile}`);

// ---- apply ----
function parseVal(s) { try { return JSON.parse(s); } catch { return s; } }
function setPath(obj, path, val) {
  const ks = path.split('.');
  let o = obj;
  for (let i = 0; i < ks.length - 1; i++) {
    const k = ks[i];
    if (o[k] == null || typeof o[k] !== 'object') o[k] = {};
    o = o[k];
  }
  const last = ks[ks.length - 1];
  const old = o[last];
  o[last] = val;
  return old;
}
function unsetPath(obj, path) {
  const ks = path.split('.');
  let o = obj;
  for (let i = 0; i < ks.length - 1; i++) { o = o?.[ks[i]]; if (o == null) return undefined; }
  const last = ks[ks.length - 1];
  const old = o[last];
  delete o[last];
  return old;
}

const changes = [];
for (const s of sets) {
  const eq = s.indexOf('=');
  if (eq < 0) die(`--set needs key=value (got "${s}")`);
  const path = s.slice(0, eq), val = parseVal(s.slice(eq + 1));
  const old = setPath(state, path, val);
  changes.push(`${path}: ${JSON.stringify(old)} → ${JSON.stringify(val)}`);
}
for (const p of unsets) changes.push(`${p}: ${JSON.stringify(unsetPath(state, p))} → (removed)`);

writeFileSync(stateFile, JSON.stringify(state, null, 2) + '\n');
console.log(`  ✓ state-set · ${stateFile.split(/[\\/]/).slice(-2).join('/')}`);
for (const c of changes) console.log(`      ${c}`);
