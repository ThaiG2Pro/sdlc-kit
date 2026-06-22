#!/usr/bin/env node
// kiro-sdlc-kit — init CLI
// Materializes the Kiro SDLC kit into a target project's .kiro/ directory.
// Zero runtime dependencies (Node >= 18 built-ins only).

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, symlinkSync, copyFileSync } from 'node:fs';
import { join, dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout, argv, exit } from 'node:process';
import { execSync } from 'node:child_process';
import { applyContextMap } from './lib/context-map.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const KIT_ROOT = resolve(__dirname, '..');
const KIT_SRC = join(KIT_ROOT, 'kit');

// ---- args ----
const args = argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith('--')));
const positional = args.filter((a) => !a.startsWith('--'));
const TARGET = resolve(positional[0] || '.');
const FORCE = flags.has('--force');
const YES = flags.has('--yes') || flags.has('-y');

// Text extensions that get placeholder substitution
const TEXT_EXT = /\.(md|json|txt|ts|js|mjs|py|yaml|yml)$/i;
const PLACEHOLDERS = [
  { key: 'PROJECT_TITLE', prompt: 'Project title (human-readable, e.g. "Acme Billing API")', def: '' },
  { key: 'LEGACY_REF_PATH', prompt: 'Legacy/reference source path (or N/A)', def: 'N/A' },
];

function log(s) { stdout.write(s + '\n'); }
function die(s) { stdout.write('✗ ' + s + '\n'); exit(1); }

function walk(dir, base = dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, base, out);
    else out.push(relative(base, full));
  }
  return out;
}

function applyTokens(content, vals) {
  return content.replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => (k in vals ? vals[k] : m));
}

async function main() {
  log('\n  kiro-sdlc-kit — init\n  ' + '─'.repeat(40));
  if (!existsSync(KIT_SRC)) die(`kit payload not found at ${KIT_SRC}`);

  const kiroDir = join(TARGET, '.kiro');
  log(`  Target project : ${TARGET}`);
  log(`  Will populate  : .kiro/{agents,skills,steering,ai,hooks,settings}`);

  // Guard: existing .kiro
  const existing = ['agents', 'skills', 'steering'].filter((d) => existsSync(join(kiroDir, d)));
  if (existing.length && !FORCE) {
    die(`.kiro already has [${existing.join(', ')}]. Re-run with --force to overwrite kit files (your specs/ & memory/ are never touched).`);
  }

  // Collect placeholder values
  const vals = {};
  const rl = (!YES) ? createInterface({ input: stdin, output: stdout }) : null;
  for (const p of PLACEHOLDERS) {
    if (YES) { vals[p.key] = p.def; continue; }
    const ans = (await rl.question(`  ${p.prompt}${p.def ? ` [${p.def}]` : ''}: `)).trim();
    vals[p.key] = ans || p.def;
  }
  if (rl) rl.close();
  if (!vals.PROJECT_TITLE) vals.PROJECT_TITLE = vals.PROJECT_SLUG || 'My Project';

  // Copy kit -> .kiro with token substitution
  const files = walk(KIT_SRC);
  let copied = 0, tokened = 0;
  for (const rel of files) {
    const src = join(KIT_SRC, rel);
    const dst = join(kiroDir, rel);
    mkdirSync(dirname(dst), { recursive: true });
    if (TEXT_EXT.test(rel)) {
      let content = readFileSync(src, 'utf8');
      const before = content;
      content = applyTokens(content, vals);
      if (content !== before) tokened++;
      writeFileSync(dst, content);
    } else {
      copyFileSync(src, dst);
    }
    copied++;
  }
  log(`\n  ✓ copied ${copied} files (${tokened} with substitutions)`);

  // Copy the context-map engine into the project so the onboarder agent / context-mapper
  // skill can re-run it in-place (node .kiro/tools/context-map.mjs).
  for (const tool of ['context-map.mjs', 'context-check.mjs', 'doctor.mjs', 'apply-stack.mjs', 'pipeline-guard.mjs']) {
    const toolSrc = join(KIT_ROOT, 'bin', 'lib', tool);
    if (existsSync(toolSrc)) {
      const toolDst = join(kiroDir, 'tools', tool);
      mkdirSync(dirname(toolDst), { recursive: true });
      copyFileSync(toolSrc, toolDst);
      log(`  ✓ installed .kiro/tools/${tool}`);
    }
  }

  // memory/ workspace (lessons learned) + symlink
  {
    const real = join(TARGET, 'memory');
    if (!existsSync(real)) { mkdirSync(real, { recursive: true }); log('  ✓ created memory/'); }
    const link = join(kiroDir, 'memory');
    if (!existsSync(link)) {
      try { symlinkSync(join('..', 'memory'), link); log('  ✓ symlink .kiro/memory -> ../memory'); }
      catch (e) { log(`  ! could not symlink .kiro/memory (${e.code})`); }
    }
  }

  // OpenSpec workspace (spec-driven backend): openspec/{changes,specs,config.yaml} + opsx skills/prompts
  let hasOpenspec = false;
  try { execSync('openspec --version', { stdio: 'ignore' }); hasOpenspec = true; } catch { /* not installed */ }
  if (hasOpenspec) {
    try {
      execSync('openspec init --tools kiro --force', { cwd: TARGET, stdio: 'ignore' });
      log('  ✓ openspec init (openspec/ + opsx skills/prompts)');
    } catch (e) { log(`  ! openspec init failed: ${e.message}`); }
  } else {
    log('  ! openspec CLI not found — this kit uses OpenSpec as its spec workspace. Install then re-run init:');
    log('      npm install -g @fission-ai/openspec@latest');
  }
  // symlink .kiro/openspec -> ../openspec so agents read the workspace via knowledgeBase
  if (existsSync(join(TARGET, 'openspec'))) {
    const link = join(kiroDir, 'openspec');
    if (!existsSync(link)) {
      try { symlinkSync(join('..', 'openspec'), link); log('  ✓ symlink .kiro/openspec -> ../openspec'); }
      catch (e) { log(`  ! could not symlink .kiro/openspec (${e.code})`); }
    }
  }

  // Wire context → each agent's resources[] from .kiro/context-map.json
  log('\n  Wiring context → agents (context-map):');
  try {
    applyContextMap({ kiroDir, log });
  } catch (e) {
    log(`  ! context-map skipped: ${e.message}`);
  }

  log('\n  Done. Next steps:');
  log('   1. Open the project in Kiro — agents: ctrl+0 sdlc-full · ctrl+5 sdlc-fast ·');
  log('      ctrl+1..4 (analyst/architect/developer/qa) · ctrl+9 onboarder');
  log('   2. Run the ONBOARDER agent (ctrl+9): fills .kiro/context/*.md, mirrors it into');
  log('      openspec/config.yaml, and re-wires context to each agent.');
  log('   3. Start work: tell sdlc-full "sdlc feature {slug}" (or sdlc-fast "fix bug {slug}")');
  log('      — it drives the OpenSpec lifecycle (propose → apply → archive) in openspec/changes/.\n');
  if (!hasOpenspec) log('   ⚠ Install the openspec CLI first (see warning above) — the workspace needs it.\n');
}

main().catch((e) => die(e.message));
