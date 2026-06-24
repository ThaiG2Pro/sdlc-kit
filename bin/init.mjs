#!/usr/bin/env node
// kiro-sdlc-kit — init CLI
// Materializes the SDLC kit into a target project for one or more PLATFORMS:
//   • kiro   → .kiro/   (Kiro IDE agent defs, KB, hooks)
//   • claude → .claude/ (Claude Code subagents, commands, settings, hooks)
// One source (kit/shared + kit/targets/<platform>) emits each target.
// Zero runtime dependencies (Node >= 18 built-ins only).

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, symlinkSync, copyFileSync, rmSync, rmdirSync } from 'node:fs';
import { join, dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline/promises';
import { stdin, stdout, argv, exit } from 'node:process';
import { execSync } from 'node:child_process';
import { applyContextMap } from './lib/context-map.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const KIT_ROOT = resolve(__dirname, '..');
const KIT_SRC = join(KIT_ROOT, 'kit');
const SHARED_SRC = join(KIT_SRC, 'shared');
const TARGETS_SRC = join(KIT_SRC, 'targets');
const KIT_VERSION = (() => {
  try { return JSON.parse(readFileSync(join(KIT_ROOT, 'package.json'), 'utf8')).version || '0.0.0'; }
  catch { return '0.0.0'; }
})();

// Per-platform output directory under the user's project.
const TARGET_DIRS = { kiro: '.kiro', claude: '.claude' };
const KNOWN_TARGETS = Object.keys(TARGET_DIRS);

// ---- args ----
// Extract --title and --target (both value-taking) first so their values are never
// mistaken for the TARGET positional.
const rawArgs = argv.slice(2);
let TITLE = null;
let TARGET_OPT = null;
const args = [];
for (let i = 0; i < rawArgs.length; i++) {
  const a = rawArgs[i];
  if (a === '--title') TITLE = rawArgs[++i] ?? null;
  else if (a.startsWith('--title=')) TITLE = a.slice('--title='.length);
  else if (a === '--target') TARGET_OPT = rawArgs[++i] ?? null;
  else if (a.startsWith('--target=')) TARGET_OPT = a.slice('--target='.length);
  else args.push(a);
}
const flags = new Set(args.filter((a) => a.startsWith('--')));
const positional = args.filter((a) => !a.startsWith('--'));
const TARGET = resolve(positional[0] || '.');
const FORCE = flags.has('--force');
const YES = flags.has('--yes') || flags.has('-y');
const CHECK = flags.has('--check') || flags.has('--dry-run');

// Text extensions that get placeholder substitution
const TEXT_EXT = /\.(md|json|txt|ts|js|mjs|py|yaml|yml)$/i;
const PLACEHOLDERS = [
  { key: 'PROJECT_TITLE', prompt: 'Project title (human-readable, e.g. "Acme Billing API")', def: '' },
  { key: 'LEGACY_REF_PATH', prompt: 'Legacy/reference source path (or N/A)', def: 'N/A' },
];

function log(s) { stdout.write(s + '\n'); }
function die(s) { stdout.write('✗ ' + s + '\n'); exit(1); }

function walk(dir, base = dir, out = []) {
  if (!existsSync(dir)) return out;
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

const isContextMd = (rel) => /^context[\/\\][^\/\\]+\.md$/.test(rel);

// Normalize a --target value ('kiro' | 'claude' | 'both' | 'kiro,claude') into a deduped list.
// Returns null when no value was given (caller decides: interactive menu vs. non-interactive default).
function parseTargetList(s) {
  if (s == null) return null;
  const v = String(s).trim().toLowerCase();
  if (v === '') return null;
  if (v === 'both' || v === 'all') return ['kiro', 'claude'];
  const parts = v.split(',').map((x) => x.trim()).filter(Boolean);
  for (const p of parts) {
    if (!KNOWN_TARGETS.includes(p)) {
      die(`unknown --target "${p}". Use one of: kiro, claude, both (or kiro,claude).`);
    }
  }
  // preserve a stable order: kiro before claude
  return KNOWN_TARGETS.filter((t) => parts.includes(t));
}

async function promptTarget(rl) {
  log('\n  Which platform(s) should this kit target?');
  log('    1) Both (Kiro + Claude Code)   [default]');
  log('    2) Kiro IDE only');
  log('    3) Claude Code only');
  const ans = (await rl.question('  Choice [1]: ')).trim().toLowerCase();
  const map = {
    '': ['kiro', 'claude'], '1': ['kiro', 'claude'], 'both': ['kiro', 'claude'],
    '2': ['kiro'], 'kiro': ['kiro'],
    '3': ['claude'], 'claude': ['claude'],
  };
  const sel = map[ans];
  if (!sel) { log(`  (unrecognized "${ans}" — defaulting to Both)`); return ['kiro', 'claude']; }
  return sel;
}

// Build the source map for one platform: shared/** overlaid by targets/<platform>/**.
// Returns { rel -> absoluteSourcePath }; the platform overlay wins on path collisions.
function buildSrcMap(platform) {
  const srcMap = new Map();
  for (const rel of walk(SHARED_SRC)) srcMap.set(rel, join(SHARED_SRC, rel));
  const overlay = join(TARGETS_SRC, platform);
  for (const rel of walk(overlay)) srcMap.set(rel, join(overlay, rel));
  return srcMap;
}

// Compute the install plan for one platform without writing anything.
function computeTarget(platform) {
  const outDir = join(TARGET, TARGET_DIRS[platform]);
  const srcMap = buildSrcMap(platform);
  const files = [...srcMap.keys()].sort();
  const manifestPath = join(outDir, '.kit-manifest.json');

  // Read the previous install's manifest. Supports the legacy shape (a bare array of file paths)
  // and the current shape ({ kitVersion, files }) so older projects still upgrade cleanly.
  let prevVersion = null, prevFiles = [];
  if (existsSync(manifestPath)) {
    try {
      const m = JSON.parse(readFileSync(manifestPath, 'utf8'));
      if (Array.isArray(m)) prevFiles = m;
      else { prevFiles = m.files || []; prevVersion = m.kitVersion || null; }
    } catch { /* unreadable manifest — treat as a fresh install */ }
  }

  // Prune orphans on re-init: files the PREVIOUS kit version installed that this version no longer
  // ships. Manifest-driven, so user-added files (never in the manifest) are never touched, and
  // filled context is always preserved.
  const nowSet = new Set(files);
  const pruneList = prevFiles.filter((rel) => !nowSet.has(rel) && !isContextMd(rel) && existsSync(join(outDir, rel)));

  // Classify each shipped file (add / overwrite / preserve).
  const isFilled = (dst) => existsSync(dst) && !readFileSync(dst, 'utf8').includes('<!-- TODO');
  const plan = { add: [], overwrite: [], preserve: [] };
  for (const rel of files) {
    const dst = join(outDir, rel);
    if (isContextMd(rel) && isFilled(dst)) plan.preserve.push(rel);
    else if (existsSync(dst)) plan.overwrite.push(rel);
    else plan.add.push(rel);
  }

  return { platform, outDir, srcMap, files, manifestPath, prevVersion, prevFiles, pruneList, plan };
}

// Apply one platform's plan: prune, copy with token substitution, write manifest, then run the
// platform-specific post-steps (Kiro: tools/ + context-map wiring; both: memory symlink).
function applyTarget(ctx, vals) {
  const { platform, outDir, srcMap, files, manifestPath, prevVersion, pruneList } = ctx;
  const label = TARGET_DIRS[platform];
  // Per-platform token: shared sources reference platform paths via {{PLATFORM_DIR}} so one source
  // emits `.kiro/…` or `.claude/…` correctly for each target (e.g. executable paths in skill docs).
  const platformVals = { ...vals, PLATFORM_DIR: label };

  log(`\n  [${platform}] → ${label}/`);
  if (existsSync(manifestPath)) {
    if (prevVersion && prevVersion !== KIT_VERSION) log(`  ⬆ Upgrading kit ${prevVersion} → ${KIT_VERSION}`);
    else if (prevVersion === KIT_VERSION)           log(`  ↻ Reinstalling kit ${KIT_VERSION} (same version)`);
    else                                            log(`  ⬆ Upgrading kit (unversioned) → ${KIT_VERSION}`);
  }

  // Apply the prune.
  let pruned = 0;
  if (FORCE && pruneList.length) {
    const dirsTouched = new Set();
    for (const rel of pruneList) {
      const p = join(outDir, rel);
      if (existsSync(p)) { rmSync(p, { force: true }); pruned++; dirsTouched.add(dirname(p)); }
    }
    for (const d of dirsTouched) {
      try { if (existsSync(d) && readdirSync(d).length === 0) rmdirSync(d); } catch { /* keep */ }
    }
    if (pruned) log(`  ✓ pruned ${pruned} stale file(s) from the previous kit version`);
  }

  let copied = 0, tokened = 0, preserved = 0;
  for (const rel of files) {
    const src = srcMap.get(rel);
    const dst = join(outDir, rel);
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
      content = applyTokens(content, platformVals);
      if (content !== before) tokened++;
      writeFileSync(dst, content);
    } else {
      copyFileSync(src, dst);
    }
    copied++;
  }
  log(`  ✓ copied ${copied} files (${tokened} with substitutions)` +
      (preserved ? `; preserved ${preserved} filled context file(s)` : ''));

  // Record the manifest of kit-managed files so the NEXT --force re-init can prune what this
  // version shipped but a future one drops. Sorted for stable diffs.
  writeFileSync(manifestPath, JSON.stringify({ kitVersion: KIT_VERSION, files: [...files].sort() }, null, 0) + '\n');

  // --- platform-specific post-steps ---
  // Copy the engine tools into <target>/tools/ so agents/commands/skills can re-run them in place.
  // The platform-aware tools (pipeline-guard, cpp-guard, context-check, apply-stack) resolve their
  // platform dir from their own install path, so the same source works under .kiro/tools/ and
  // .claude/tools/. context-map.mjs wires Kiro agent JSON resources[] — Kiro-only (apply-stack
  // skips the context-map merge/re-wire on Claude, where skills auto-load from .claude/skills/).
  // doctor.mjs validates Kiro agent JSON + resources[] + the context map; doctor-claude.mjs is its
  // Claude counterpart (validates CLAUDE.md @imports, commands/subagents, the Edit-tool invariant,
  // and settings.json hook/tool wiring) — each ships only to its own platform.
  const TOOLS_BY_PLATFORM = {
    kiro: ['context-map.mjs', 'context-check.mjs', 'doctor.mjs', 'apply-stack.mjs', 'pipeline-guard.mjs', 'cpp-guard.mjs'],
    claude: ['context-check.mjs', 'doctor-claude.mjs', 'apply-stack.mjs', 'pipeline-guard.mjs', 'cpp-guard.mjs'],
  };
  for (const tool of TOOLS_BY_PLATFORM[platform] || []) {
    const toolSrc = join(KIT_ROOT, 'bin', 'lib', tool);
    if (existsSync(toolSrc)) {
      const toolDst = join(outDir, 'tools', tool);
      mkdirSync(dirname(toolDst), { recursive: true });
      copyFileSync(toolSrc, toolDst);
      log(`  ✓ installed ${label}/tools/${tool}`);
    }
  }
  // NOTE (kiro): context→agents wiring (applyContextMap) runs AFTER openspec init/symlink in main(),
  // because context-map.json lists `openspec` as a knowledgeBase that is only wired when
  // .kiro/openspec exists. Wiring here (before openspec) would drop that resource.

  // memory/ baton symlink (both platforms point at the single ../memory workspace)
  {
    const real = join(TARGET, 'memory');
    if (!existsSync(real)) { mkdirSync(real, { recursive: true }); log('  ✓ created memory/'); }
    const link = join(outDir, 'memory');
    if (!existsSync(link)) {
      try { symlinkSync(join('..', 'memory'), link); log(`  ✓ symlink ${label}/memory -> ../memory`); }
      catch (e) { log(`  ! could not symlink ${label}/memory (${e.code})`); }
    }
  }

  // openspec workspace symlink so agents can read specs/changes via a stable in-target path
  if (existsSync(join(TARGET, 'openspec'))) {
    const link = join(outDir, 'openspec');
    if (!existsSync(link)) {
      try { symlinkSync(join('..', 'openspec'), link); log(`  ✓ symlink ${label}/openspec -> ../openspec`); }
      catch (e) { log(`  ! could not symlink ${label}/openspec (${e.code})`); }
    }
  }

  return { copied, tokened, preserved, pruned };
}

function printNextSteps(targets, hasOpenspec) {
  log('\n  Done. Next steps:');
  if (targets.includes('kiro')) {
    log('   [kiro] Open the project in Kiro:');
    log('     • agents: ctrl+0 sdlc-full · ctrl+5 sdlc-fast · ctrl+1..4 (analyst/architect/developer/qa) · ctrl+9 onboarder');
    log('     • After any kit update, run "Developer: Reload Window" (Ctrl+R) so Kiro reloads agent defs + hooks.');
    log('     • Run the ONBOARDER (ctrl+9) first: fills .kiro/context/*.md, mirrors into openspec/config.yaml, re-wires context.');
  }
  if (targets.includes('claude')) {
    log('   [claude] Open the project in Claude Code:');
    log('     • Orchestrator (main session): /sdlc-full <slug> ticket <id> · /sdlc-fast bugfix <slug>');
    log('     • Role subagents (.claude/agents/): analyst · architect · developer · qa · onboarder');
    log('     • Run the onboarder first on a new project: it fills .claude/context/*.md + mirrors openspec/config.yaml.');
    log('     • Security: only the developer subagent writes code — enforced by the agent_type-keyed PreToolUse hooks in .claude/settings.json.');
    log('     • New/changed agents, commands, settings & hooks take effect on the NEXT session (or /agents reload) — not mid-session.');
  }
  log('   • Start work: drive the OpenSpec lifecycle (propose → apply → archive) in openspec/changes/.');
  if (!hasOpenspec) log('   ⚠ Install the openspec CLI first (see warning above) — the workspace needs it.\n');
  else log('');
}

async function main() {
  log('\n  kiro-sdlc-kit — init\n  ' + '─'.repeat(40));
  if (!existsSync(SHARED_SRC)) die(`kit payload not found at ${SHARED_SRC}`);

  // Fail loudly on non-interactive (piped/non-TTY) stdin instead of the old silent no-op.
  if (!CHECK && !YES && !stdin.isTTY && TITLE === null) {
    die('non-interactive (piped) stdin and neither --title nor --yes was given.\n' +
        '    Re-run in a real terminal, or pass --title "Project Name" (optionally with --yes for other defaults).\n' +
        '    Nothing was changed.');
  }

  const canPrompt = stdin.isTTY && !YES && !CHECK;
  const rl = canPrompt ? createInterface({ input: stdin, output: stdout }) : null;

  // --- resolve target platform(s) ---
  let targets = parseTargetList(TARGET_OPT);
  if (!targets) {
    // No --target given. Interactive → menu (default Both). Non-interactive → kiro (zero behavior
    // change for existing scripted installs; see MIGRATION.md §7 Q1).
    targets = rl ? await promptTarget(rl) : ['kiro'];
  }

  log(`  Target project : ${TARGET}`);
  log(`  Platform(s)    : ${targets.map((t) => TARGET_DIRS[t]).join(', ')}`);

  // Guard: refuse to clobber an existing kit install per target unless --force/--check.
  for (const t of targets) {
    const outDir = join(TARGET, TARGET_DIRS[t]);
    const existing = ['agents', 'skills', 'steering'].filter((d) => existsSync(join(outDir, d)));
    if (existing.length && !FORCE && !CHECK) {
      if (rl) rl.close();
      die(`${TARGET_DIRS[t]} already has [${existing.join(', ')}]. Re-run with --force to overwrite kit files ` +
          `(your specs/, memory/, and already-filled context/*.md are preserved).`);
    }
  }

  // Collect placeholder values. --title sets PROJECT_TITLE up front; only prompt when we have a TTY.
  const vals = { PROJECT_TITLE: TITLE ?? '', LEGACY_REF_PATH: 'N/A' };
  if (rl) {
    for (const p of PLACEHOLDERS) {
      if (p.key === 'PROJECT_TITLE' && TITLE !== null) continue; // already provided via --title
      const ans = (await rl.question(`  ${p.prompt}${p.def ? ` [${p.def}]` : ''}: `)).trim();
      vals[p.key] = ans || p.def;
    }
  }
  if (rl) rl.close();
  if (!vals.PROJECT_TITLE) vals.PROJECT_TITLE = 'My Project';

  // Compute plans for all selected targets up front.
  const ctxs = targets.map(computeTarget);

  // --check / --dry-run: print every target's plan and exit WITHOUT writing anything.
  if (CHECK) {
    const sample = (arr, n = 8) =>
      (arr.length ? '\n' + arr.slice(0, n).map((r) => `        ${r}`).join('\n') : '') +
      (arr.length > n ? `\n        …and ${arr.length - n} more` : '');
    log('\n  Dry-run plan (no files written):');
    for (const c of ctxs) {
      log(`\n  [${c.platform}] → ${TARGET_DIRS[c.platform]}/`);
      log(`    + add       ${c.plan.add.length}${sample(c.plan.add)}`);
      log(`    ~ overwrite ${c.plan.overwrite.length} (kit-owned; your edits to these are replaced)${sample(c.plan.overwrite)}`);
      log(`    = preserve  ${c.plan.preserve.length} filled context file(s)${sample(c.plan.preserve)}`);
      log(`    - prune     ${c.pruneList.length} stale file(s) from the previous version${sample(c.pruneList)}`);
    }
    log('\n  (openspec init, tools, and the context→agents mapper also run on apply.)');
    log('  Re-run without --check (add --force on an existing install) to apply.\n');
    exit(0);
  }

  // Apply each target.
  for (const c of ctxs) applyTarget(c, vals);

  // OpenSpec workspace (spec-driven backend) — project-global, run ONCE for all selected targets.
  let hasOpenspec = false;
  try { execSync('openspec --version', { stdio: 'ignore' }); hasOpenspec = true; } catch { /* not installed */ }
  if (hasOpenspec) {
    const toolsArg = targets.join(','); // kiro | claude | kiro,claude
    try {
      execSync(`openspec init --tools ${toolsArg} --force`, { cwd: TARGET, stdio: 'ignore' });
      log(`\n  ✓ openspec init --tools ${toolsArg} (openspec/ + per-tool skills/prompts)`);
    } catch (e) { log(`\n  ! openspec init failed: ${e.message}`); }

    // Install the kit's per-artifact rules into openspec/config.yaml so `openspec instructions`
    // emits them in its <rules> block. The role agents carry NO inline format for
    // proposal/spec/design/tasks — the conventions live here, deterministically installed.
    try {
      const cfgPath = join(TARGET, 'openspec', 'config.yaml');
      const rulesSrc = join(SHARED_SRC, 'ai', 'openspec-rules.yaml');
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

    // Re-link openspec into any target that was created before openspec/ existed.
    for (const c of ctxs) {
      const link = join(c.outDir, 'openspec');
      if (!existsSync(link) && existsSync(join(TARGET, 'openspec'))) {
        try { symlinkSync(join('..', 'openspec'), link); log(`  ✓ symlink ${TARGET_DIRS[c.platform]}/openspec -> ../openspec`); }
        catch { /* best-effort */ }
      }
    }
  } else {
    log('\n  ! openspec CLI not found — this kit uses OpenSpec as its spec workspace. Install then re-run init:');
    log('      npm install -g @fission-ai/openspec@latest');
  }

  // Wire context → each Kiro agent's resources[] from .kiro/context-map.json. Runs LAST so the
  // openspec/ symlink (created above) is in place — context-map.json lists `openspec` as a KB.
  for (const c of ctxs) {
    if (c.platform !== 'kiro') continue;
    log('\n  Wiring context → agents (context-map):');
    try { applyContextMap({ kiroDir: c.outDir, log }); }
    catch (e) { log(`  ! context-map skipped: ${e.message}`); }
  }

  printNextSteps(targets, hasOpenspec);
}

main().catch((e) => die(e.message));
