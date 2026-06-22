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
// Extract --title (value-taking) first so its value is never mistaken for the TARGET positional.
const rawArgs = argv.slice(2);
let TITLE = null;
const args = [];
for (let i = 0; i < rawArgs.length; i++) {
  const a = rawArgs[i];
  if (a === '--title') TITLE = rawArgs[++i] ?? null;
  else if (a.startsWith('--title=')) TITLE = a.slice('--title='.length);
  else args.push(a);
}
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
    die(`.kiro already has [${existing.join(', ')}]. Re-run with --force to overwrite kit files (your specs/, memory/, and already-filled context/*.md are preserved).`);
  }

  // Fail loudly on non-interactive (piped/non-TTY) stdin instead of the old silent no-op:
  // readline.question never resolves without a TTY, so main() used to hang and Node exited 0
  // having copied nothing. Require --yes and/or --title in that case.
  if (!YES && !stdin.isTTY && TITLE === null) {
    die('non-interactive (piped) stdin and neither --title nor --yes was given.\n' +
        '    Re-run in a real terminal, or pass --title "Project Name" (optionally with --yes for other defaults).\n' +
        '    Nothing was changed.');
  }

  // Collect placeholder values. --title sets PROJECT_TITLE up front; only prompt when we have a TTY.
  const vals = { PROJECT_TITLE: TITLE ?? '', LEGACY_REF_PATH: 'N/A' };
  const canPrompt = stdin.isTTY && !YES;
  if (canPrompt) {
    const rl = createInterface({ input: stdin, output: stdout });
    for (const p of PLACEHOLDERS) {
      if (p.key === 'PROJECT_TITLE' && TITLE !== null) continue; // already provided via --title
      const ans = (await rl.question(`  ${p.prompt}${p.def ? ` [${p.def}]` : ''}: `)).trim();
      vals[p.key] = ans || p.def;
    }
    rl.close();
  }
  if (!vals.PROJECT_TITLE) vals.PROJECT_TITLE = 'My Project';

  // Copy kit -> .kiro with token substitution
  const files = walk(KIT_SRC);
  const isContextMd = (rel) => /^context[\/\\][^\/\\]+\.md$/.test(rel);
  let copied = 0, tokened = 0, preserved = 0;
  for (const rel of files) {
    const src = join(KIT_SRC, rel);
    const dst = join(kiroDir, rel);
    // Preserve human-filled context on re-init/upgrade: never clobber a context/*.md that no
    // longer has any `<!-- TODO` marker (i.e. the onboarder/user already filled it).
    if (isContextMd(rel) && existsSync(dst) && !readFileSync(dst, 'utf8').includes('<!-- TODO')) {
      preserved++;
      continue;
    }
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
  log(`\n  ✓ copied ${copied} files (${tokened} with substitutions)` +
      (preserved ? `; preserved ${preserved} filled context file(s)` : ''));

  // Copy the context-map engine into the project so the onboarder agent / context-mapper
  // skill can re-run it in-place (node .kiro/tools/context-map.mjs).
  for (const tool of ['context-map.mjs', 'context-check.mjs', 'doctor.mjs', 'apply-stack.mjs', 'pipeline-guard.mjs', 'cpp-guard.mjs']) {
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

    // Install the kit's per-artifact rules into openspec/config.yaml so `openspec instructions`
    // emits them in its <rules> block. This is why the role agents carry NO inline format for
    // proposal/spec/design/tasks — the conventions live here, deterministically installed.
    try {
      const cfgPath = join(TARGET, 'openspec', 'config.yaml');
      const rulesSrc = join(KIT_SRC, 'ai', 'openspec-rules.yaml');
      if (existsSync(cfgPath) && existsSync(rulesSrc)) {
        const cfg = readFileSync(cfgPath, 'utf8');
        if (/^rules:/m.test(cfg)) {
          log('  ✓ openspec/config.yaml already has rules: — left untouched');
        } else {
          const rulesBlock = readFileSync(rulesSrc, 'utf8');
          writeFileSync(cfgPath, cfg.replace(/\s*$/, '') + '\n\n' + rulesBlock);
          log('  ✓ installed kit per-artifact rules into openspec/config.yaml');
        }
      }
    } catch (e) { log(`  ! could not install openspec rules: ${e.message}`); }
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
