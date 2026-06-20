#!/usr/bin/env node
// kiro-sdlc-kit — init CLI
// Materializes the Kiro SDLC kit into a target project's .kiro/ directory.
// Zero runtime dependencies (Node >= 18 built-ins only).

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, symlinkSync, copyFileSync } from 'node:fs';
import { join, dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout, argv, exit } from 'node:process';

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

  // Scaffold project-specific dirs + symlinks (single source of truth at repo root)
  for (const d of ['specs', 'memory']) {
    const real = join(TARGET, d);
    if (!existsSync(real)) { mkdirSync(real, { recursive: true }); log(`  ✓ created ${d}/`); }
    const link = join(kiroDir, d);
    if (!existsSync(link)) {
      try { symlinkSync(join('..', d), link); log(`  ✓ symlink .kiro/${d} -> ../${d}`); }
      catch (e) { log(`  ! could not symlink .kiro/${d} (${e.code}) — create manually`); }
    }
  }

  // Seed active-feature pointer
  const af = join(TARGET, 'specs', '.active-feature.json');
  if (!existsSync(af)) {
    writeFileSync(af, JSON.stringify({ active_spec: null, current_phase: null, last_agent: null, last_updated: null }, null, 2) + '\n');
    log('  ✓ seeded specs/.active-feature.json');
  }

  log('\n  Done. Next steps:');
  log('   1. Open the project in Kiro — agents appear as ctrl+0..4 (sdlc/analyst/architect/developer/qa)');
  log('   2. Review .kiro/steering/ — customize api-standards.md, stack-*.md, ai/ for your stack');
  log('   3. Start a feature:  say "sdlc feature {slug} ticket {id}" to the sdlc agent\n');
}

main().catch((e) => die(e.message));
