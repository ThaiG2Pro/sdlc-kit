#!/usr/bin/env node
// kiro-sdlc-kit — init CLI
// Materializes the SDLC kit into a target project for one or more PLATFORMS:
//   • kiro   → .kiro/   (Kiro IDE agent defs, KB, hooks)
//   • claude → .claude/ (Claude Code subagents, commands, settings, hooks)
// One source (kit/shared + kit/targets/<platform>) emits each target.
// Zero runtime dependencies (Node >= 18 built-ins only).

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync, lstatSync, copyFileSync, cpSync, rmSync, rmdirSync, renameSync } from 'node:fs';
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
const GITIGNORE = flags.has('--gitignore');       // force-write the kit .gitignore block (no prompt)
const NO_GITIGNORE = flags.has('--no-gitignore'); // never touch .gitignore (no prompt)

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

// .claude/settings.json is the ONE kit-owned file that also carries USER config (enabledPlugins,
// env, model, statusLine, …) and user/skill-added permissions (e.g. /fewer-permission-prompts). A
// blind overwrite on --force would wipe those. Merge instead: the kit OWNS its security policy
// (hooks + its own permission entries + $schema) and wins there, but every user-owned top-level key
// is preserved and the permission lists are UNIONed so additions survive a kit upgrade.
function mergeClaudeSettings(kit, user) {
  const out = JSON.parse(JSON.stringify(kit)); // kit base: $schema, permissions, hooks
  // 1. Preserve user-owned top-level keys the kit template doesn't manage.
  for (const k of Object.keys(user || {})) if (!(k in out)) out[k] = user[k];
  // 2. permissions: union allow + deny so user/skill additions are kept (kit list stays first).
  const uni = (a = [], b = []) => [...new Set([...(a || []), ...(b || [])])];
  if (user && user.permissions) {
    out.permissions = out.permissions || {};
    out.permissions.allow = uni(out.permissions.allow, user.permissions.allow);
    out.permissions.deny = uni(out.permissions.deny, user.permissions.deny);
  }
  // 3. hooks: kit wins on the events it ships; keep any user-added event the kit doesn't define.
  if (user && user.hooks) {
    out.hooks = out.hooks || {};
    for (const ev of Object.keys(user.hooks)) if (!(ev in out.hooks)) out.hooks[ev] = user.hooks[ev];
  }
  return out;
}

const isContextMd = (rel) => /^context[\/\\][^\/\\]+\.md$/.test(rel);
// Project config that must be a SINGLE source shared by every platform (like openspec/memory/context):
// scaffolded once at the project root. Edit once, both targets see it; switching kiro↔claude never
// drifts or loses it.
const SHARED_ROOT_FILES = ['sdlc.config.json', 'pipelines.json'];
const isSharedRootFile = (rel) => SHARED_ROOT_FILES.includes(rel);

// Optional kit-owned .gitignore block (opt-in at init). Ignores ONLY what the kit regenerates on
// every `init --force`: the per-platform framework dirs + the root config files. context/, openspec/,
// docs/, and memory/ are deliberately NOT listed — they hold hand-authored project knowledge / work
// products that SHOULD be committed. Bounded by markers so re-init refreshes the block in place
// (never duplicates) and a user can delete the whole block to commit the kit instead.
const GI_BEGIN = '# >>> kiro-sdlc-kit >>>';
const GI_END = '# <<< kiro-sdlc-kit <<<';
const GITIGNORE_PATTERNS = ['.claude/', '.kiro/', '/sdlc.config.json', '/pipelines.json'];
// Everything that lives ONCE at the project root — NO per-platform copy and NO symlink. Both
// platforms reach these via root-relative paths (Claude: `@../context/*` in CLAUDE.md + `./context`,
// `openspec/…`, `docs/…` via the Read tool/CWD; Kiro: `file://./<entry>` resources[] emitted by the
// mapper). Keeping the canonical copy at root — never inside a platform dir, never symlinked — means
// a single-platform install can't point at the other's path AND removing one platform never breaks
// the share. `docs` is the project doc workspace (intake writes ticket packages to
// docs/extra-docs/<ticket>-<slug>/; project docs live here too). On re-init, applyTarget() strips any
// stale <platform>/<name> symlink or migrated dir a PRIOR symlink-based install left behind.
const SHARED_ROOT_NAMES = ['context', 'docs', 'openspec', 'memory', ...SHARED_ROOT_FILES];

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
  // context/*.md is NOT copied per-platform: it's a single project-root ./context/ workspace
  // (like openspec/ and memory/), scaffolded once at root and read root-relative by each platform.
  // Excluding it here keeps it out of every platform's copy loop, manifest, and prune list.
  const shared = (rel) => isContextMd(rel) || isSharedRootFile(rel); // emitted once at root (no per-platform copy)
  const srcMap = new Map();
  for (const rel of walk(SHARED_SRC)) if (!shared(rel)) srcMap.set(rel, join(SHARED_SRC, rel));
  const overlay = join(TARGETS_SRC, platform);
  for (const rel of walk(overlay)) if (!shared(rel)) srcMap.set(rel, join(overlay, rel));
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
// platform-specific post-steps (Kiro: tools/ + context-map wiring; both: strip stale shared-root links).
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
    if (platform === 'claude' && rel === 'settings.json' && existsSync(dst)) {
      // Merge rather than clobber: preserve user-added enabledPlugins/env/model/permissions.
      const kitJson = JSON.parse(applyTokens(readFileSync(src, 'utf8'), platformVals));
      let userJson = {};
      try { userJson = JSON.parse(readFileSync(dst, 'utf8')); } catch { /* corrupt → kit wins */ }
      writeFileSync(dst, JSON.stringify(mergeClaudeSettings(kitJson, userJson), null, 2) + '\n');
      log('  ✓ merged settings.json (kit security policy refreshed; your enabledPlugins/env/model + extra permissions kept)');
      tokened++; copied++;
      continue;
    }
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
    kiro: ['context-map.mjs', 'context-check.mjs', 'doctor.mjs', 'apply-stack.mjs', 'pipeline-guard.mjs', 'cpp-guard.mjs', 'state-set.mjs', 'state-schema.mjs'],
    claude: ['context-check.mjs', 'doctor-claude.mjs', 'apply-stack.mjs', 'pipeline-guard.mjs', 'cpp-guard.mjs', 'state-set.mjs', 'state-schema.mjs'],
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
  // NOTE (kiro): context→agents wiring (applyContextMap) runs AFTER openspec init in main(),
  // because context-map.json lists `openspec` as a knowledgeBase that is only wired when
  // ./openspec exists (shared-root, checked at the project root — see isSharedRootKb in
  // context-map.mjs). Wiring here (before openspec) would drop that resource.

  // Strip any stale per-platform shared-root artifact a PRIOR (symlink-based) install left inside this
  // platform dir — symlink OR a real dir/file. The canonical copy now lives ONLY at the project root
  // (scaffoldRootContext/scaffoldRootConfig/main migrate + own it before applyTarget runs), and both
  // platforms reference it root-relative, so nothing per-platform should shadow it.
  for (const name of SHARED_ROOT_NAMES) {
    const p = join(outDir, name);
    try { lstatSync(p); } catch { continue; } // not present → nothing to clean
    try { rmSync(p, { recursive: true, force: true }); log(`  ✓ removed stale ${label}/${name} (now root-only)`); }
    catch (e) { log(`  ! could not remove ${label}/${name} (${e.code})`); }
  }

  return { copied, tokened, preserved, pruned };
}

// Migrate a prior install's REAL per-platform <name>/ dir (docs/, memory/) into the project root
// before applyTarget strips the per-platform copy — so no ticket package or memory baton is lost on
// the symlink→root-only upgrade. No-op when root already has it (root is canonical) or the
// per-platform entry is a symlink/absent. Merges file-by-file without overwriting an existing root file.
function migrateRealDirToRoot(name, targets) {
  const root = join(TARGET, name);
  for (const t of targets) {
    const p = join(TARGET, TARGET_DIRS[t], name);
    let real = false;
    try { real = !lstatSync(p).isSymbolicLink() && statSync(p).isDirectory(); } catch { continue; }
    if (!real) continue;
    mkdirSync(root, { recursive: true });
    for (const f of readdirSync(p)) {
      const dst = join(root, f);
      if (existsSync(dst)) continue; // root copy wins
      try { cpSync(join(p, f), dst, { recursive: true }); } catch { /* skip */ }
    }
    log(`  ✓ migrated existing ${TARGET_DIRS[t]}/${name} → ./${name}`);
  }
}

// Split a legacy SHARED file (every SDLC change appended a `## ` section to it) into one file per
// change under destDir/<change-name>.md. Every change runs on its own isolated branch, so a single
// shared file that every branch appends to is a guaranteed merge conflict the moment two changes are
// in flight at once — the fix is one file per change, never a shared path. No-op if srcPath is
// absent (already migrated, or a fresh install with nothing to migrate yet). The original is kept
// as `<file>.pre-migration-backup`, never deleted, so a mis-parsed edge case is one `cp` from
// recovery. `headerRe` must capture the change-name from the `## ` line (group 1).
function splitSharedFileIntoPerChange(srcPath, destDir, headerRe) {
  if (!existsSync(srcPath) || !statSync(srcPath).isFile()) return;
  const text = readFileSync(srcPath, 'utf8');
  const sections = [];
  let current = null;
  for (const line of text.split('\n')) {
    const m = line.match(headerRe);
    if (m) { if (current) sections.push(current); current = { changeName: m[1].trim().replace(/\s+/g, '-'), body: [line] }; }
    else if (current) current.body.push(line);
  }
  if (current) sections.push(current);
  if (sections.length === 0) return; // no '## ' section found — leave the file alone, don't guess

  const byChange = new Map();
  for (const s of sections) {
    const body = s.body.join('\n').replace(/\n+$/, '') + '\n';
    byChange.set(s.changeName, (byChange.get(s.changeName) || '') + body);
  }
  mkdirSync(destDir, { recursive: true });
  for (const [changeName, body] of byChange) {
    const destPath = join(destDir, `${changeName}.md`);
    const finalBody = existsSync(destPath) ? readFileSync(destPath, 'utf8').replace(/\n+$/, '') + '\n' + body : body;
    writeFileSync(destPath, finalBody);
  }
  // Never clobber a PRIOR backup — a stale session that keeps recreating the legacy flat file (its
  // agent defs only reload at session start, so it can keep writing the old path for a long time
  // after an upgrade) must not cause a second migration pass to overwrite the first backup's content.
  let backupPath = srcPath + '.pre-migration-backup';
  for (let n = 2; existsSync(backupPath); n++) backupPath = `${srcPath}.pre-migration-backup.${n}`;
  renameSync(srcPath, backupPath);
  log(`  ✓ migrated ${relative(TARGET, srcPath)} → ${byChange.size} per-change file(s) under ${relative(TARGET, destDir)}/ (original kept as ${relative(TARGET, backupPath)})`);
}

// One-time upgrade path: pre-per-change-fragment installs kept ONE shared memory/<role>.md and ONE
// openspec/_cross-spec-context.md that every change appended to. Split each into per-change files.
function migrateSharedMemoryAndCrossSpecToPerChange() {
  for (const role of ['analyst', 'architect', 'developer', 'qa']) {
    splitSharedFileIntoPerChange(
      join(TARGET, 'memory', `${role}.md`),
      join(TARGET, 'memory', role),
      /^##\s+\S+\s+—\s+([^:]+):/,
    );
  }
  splitSharedFileIntoPerChange(
    join(TARGET, 'openspec', '_cross-spec-context.md'),
    join(TARGET, 'openspec', '_cross-spec-context'),
    /^##\s+\S+\s+—\s+([^(]+)\(S3/,
  );
}

// Backfill memory/<role>/_index.md (the one-line-per-change digest roles read before opening any
// full fragment file — see sdlc-orchestration-core SKILL.md §Role-memory index) from EXISTING
// per-change fragment files, for projects upgrading from before this feature existed. Idempotent:
// only appends digest lines not already present, so re-running --force never duplicates entries.
// One line per `## ` section found (one per write-back round) — agents write new lines themselves
// going forward; this only seeds history that predates the feature.
function backfillMemoryIndex() {
  const headerRe = /^##\s+(\S+)\s+—\s+[^:]+:\s*(.+?)\s*$/;
  for (const role of ['analyst', 'architect', 'developer', 'qa']) {
    const dir = join(TARGET, 'memory', role);
    if (!existsSync(dir) || !statSync(dir).isDirectory()) continue;
    const indexPath = join(dir, '_index.md');
    const existing = existsSync(indexPath) ? readFileSync(indexPath, 'utf8') : '';
    const seen = new Set(existing.split('\n').map((l) => l.trim()).filter(Boolean));
    const newLines = [];
    for (const f of readdirSync(dir)) {
      if (f === '_index.md' || !f.endsWith('.md')) continue;
      const changeName = f.slice(0, -3);
      for (const line of readFileSync(join(dir, f), 'utf8').split('\n')) {
        const m = line.match(headerRe);
        if (!m) continue;
        const entry = `- ${changeName} (${m[1]}): ${m[2]}`;
        if (!seen.has(entry)) { newLines.push(entry); seen.add(entry); }
      }
    }
    if (!newLines.length) continue;
    const finalText = existing.trim()
      ? existing.replace(/\n+$/, '') + '\n' + newLines.join('\n') + '\n'
      : newLines.join('\n') + '\n';
    writeFileSync(indexPath, finalText);
    log(`  ✓ backfilled ${relative(TARGET, indexPath)} · ${newLines.length} entr${newLines.length === 1 ? 'y' : 'ies'}`);
  }
}

// Establish the single project-root ./context/ workspace (canonical, root-only — both platforms read
// it root-relative, no symlink). Migrates a prior install's filled per-platform context into root
// first, then scaffolds templates (preserving any already-filled file). Runs once for all targets.
function scaffoldRootContext(targets, vals) {
  const rootCtx = join(TARGET, 'context');
  // Migration: no root ./context yet, but an older install has a REAL <platform>/context dir →
  // copy its (possibly filled) files to root before applyTarget strips that per-platform dir.
  if (!existsSync(rootCtx)) {
    for (const t of targets) {
      const pCtx = join(TARGET, TARGET_DIRS[t], 'context');
      let real = false;
      try { real = !lstatSync(pCtx).isSymbolicLink(); } catch { /* absent */ }
      if (real) {
        mkdirSync(rootCtx, { recursive: true });
        for (const f of readdirSync(pCtx)) {
          const s = join(pCtx, f);
          try { if (statSync(s).isFile()) copyFileSync(s, join(rootCtx, f)); } catch { /* skip */ }
        }
        log(`  ✓ migrated existing ${TARGET_DIRS[t]}/context → ./context`);
        break;
      }
    }
  }
  const srcDir = join(SHARED_SRC, 'context');
  if (!existsSync(srcDir)) return;
  mkdirSync(rootCtx, { recursive: true });
  let scaffolded = 0, preserved = 0;
  for (const f of readdirSync(srcDir)) {
    const dst = join(rootCtx, f);
    if (existsSync(dst) && !readFileSync(dst, 'utf8').includes('<!-- TODO')) { preserved++; continue; }
    writeFileSync(dst, applyTokens(readFileSync(join(srcDir, f), 'utf8'), vals));
    scaffolded++;
  }
  log(`  ✓ context → ./context (${scaffolded} scaffolded, ${preserved} preserved filled)`);
}

// Scaffold the shared project-config files (sdlc.config.json, pipelines.json) ONCE at the project
// root; both platforms read them root-relative (no per-platform copy/symlink). Kit-owned → regenerated
// from the single kit source ("cùng 1 mẹ") on every init, so the two platforms can never drift.
function scaffoldRootConfig(vals) {
  let n = 0;
  for (const f of SHARED_ROOT_FILES) {
    const src = join(SHARED_SRC, f);
    if (!existsSync(src)) continue;
    const dst = join(TARGET, f);
    let out = applyTokens(readFileSync(src, 'utf8'), vals);
    // sdlc.config.json is kit-owned and regenerated here EXCEPT the user-owned `paths` key (per-project
    // code/test roots the write-fence reads). Carry a project's declared roots over the fresh template
    // so a --force redeploy never wipes them. Only re-serialize when roots are actually present, so the
    // common case keeps the template's exact formatting.
    if (f === 'sdlc.config.json' && existsSync(dst)) {
      try {
        const prev = JSON.parse(readFileSync(dst, 'utf8'));
        const p = prev && prev.paths;
        const hasRoots = p && ((Array.isArray(p.code_roots) && p.code_roots.length) ||
                               (Array.isArray(p.test_roots) && p.test_roots.length));
        if (hasRoots) {
          const tmpl = JSON.parse(out);
          tmpl.paths = p;
          out = JSON.stringify(tmpl, null, 2) + '\n';
          log(`  ✓ preserved sdlc.config.json paths.{code_roots,test_roots} across --force`);
        }
      } catch { /* non-JSON on either side → fall back to the freshly-templated output */ }
    }
    writeFileSync(dst, out);
    n++;
  }
  if (n) log(`  ✓ config → ./{${SHARED_ROOT_FILES.join(', ')}} (shared root, read root-relative by each platform)`);
}

// Idempotently maintain the kit-owned block in the project's .gitignore. Strips any prior block
// (between markers, inclusive) and re-appends a fresh one, so re-running init never duplicates it and
// always reflects the current pattern list. Everything outside the markers is left untouched; delete
// the whole block to commit the kit instead.
function updateGitignore() {
  const giPath = join(TARGET, '.gitignore');
  let body = '', existed = false;
  try { body = readFileSync(giPath, 'utf8'); existed = true; } catch { /* no .gitignore yet */ }
  const re = new RegExp(`\\n*${GI_BEGIN}[\\s\\S]*?${GI_END}\\n?`, 'g');
  const stripped = body.replace(re, '');
  const block = [
    GI_BEGIN,
    '# Kit-owned: regenerated by `kiro-sdlc-init --force`. Delete this block to commit the kit.',
    '# (context/, openspec/, docs/, memory/ are intentionally NOT ignored — commit those.)',
    ...GITIGNORE_PATTERNS,
    GI_END,
  ].join('\n');
  const next = stripped.replace(/\s*$/, '') + (stripped.trim() ? '\n\n' : '') + block + '\n';
  if (next === body) { log('  ✓ .gitignore kit block already up to date'); return; }
  writeFileSync(giPath, next);
  log(`  ✓ ${existed ? 'updated' : 'created'} .gitignore (kit block: ${GITIGNORE_PATTERNS.join(', ')})`);
}

function printNextSteps(targets, hasOpenspec) {
  log('\n  Done. Next steps:');
  if (targets.includes('kiro')) {
    log('   [kiro] Open the project in Kiro:');
    log('     • agents: ctrl+0 sdlc-full · ctrl+5 sdlc-fast · ctrl+1..4 (analyst/architect/developer/qa) · ctrl+6 intake · ctrl+7 context-refresh · ctrl+9 onboarder');
    log('     • After any kit update, run "Developer: Reload Window" (Ctrl+R) so Kiro reloads agent defs + hooks.');
    log('     • Run the ONBOARDER (ctrl+9) first: fills ./context/*.md (shared root, read by both platforms), mirrors into openspec/config.yaml, re-wires context.');
    log('     • Before a work item, run INTAKE (ctrl+6): pulls a Redmine ticket + its Figma UI into docs/extra-docs/<ticket_id>-<slug>/ so the analyst starts with full context.');
    log('     • When context drifts (new stack/docs over many features), run CONTEXT-REFRESH (ctrl+7) to re-sync ./context/*.md + re-wire.');
  }
  if (targets.includes('claude')) {
    log('   [claude] Open the project in Claude Code:');
    log('     • Orchestrator (main session): /sdlc-full <slug> ticket <id> · /sdlc-fast bugfix <slug>');
    log('     • Role subagents (.claude/agents/): analyst · architect · developer · qa · onboarder · intake · context-refresh');
    log('     • Run the onboarder first on a new project: it fills ./context/*.md (shared root, read by both platforms) + mirrors openspec/config.yaml.');
    log('     • Before a work item: /intake <slug> <ticket-id> pulls a Redmine ticket + its Figma UI into docs/extra-docs/<ticket_id>-<slug>/ for the analyst. /context-refresh re-syncs context when it drifts.');
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
  // Resolve whether to manage the project's .gitignore (kit-owned framework + config block).
  // Precedence: --no-gitignore < --gitignore < interactive prompt (default yes) < non-interactive default (yes).
  let doGitignore;
  if (NO_GITIGNORE) doGitignore = false;
  else if (GITIGNORE) doGitignore = true;
  else if (rl) {
    const ans = (await rl.question('  Add kit files (.claude/, .kiro/, sdlc.config.json, pipelines.json) to .gitignore? [Y/n]: ')).trim().toLowerCase();
    doGitignore = !(ans === 'n' || ans === 'no');
  } else doGitignore = true; // non-interactive (--yes / --title) → default yes; pass --no-gitignore to skip

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
      log(`    - prune     ${c.pruneList.length} stale file(s) from the previous version${sample(c.pruneList)}`);
      log(`    ⌫ strip     stale per-platform ${TARGET_DIRS[c.platform]}/{${SHARED_ROOT_NAMES.join(', ')}} (symlink or dir) — these are now root-only`);
    }
    log(`\n  ${doGitignore ? '✎ gitignore  add/refresh kit block → ' + GITIGNORE_PATTERNS.join(', ') : '· gitignore  left untouched (--no-gitignore)'}`);
    log(`\n  (shared workspace + config — ./{${SHARED_ROOT_NAMES.join(', ')}} — live ONCE at the project root, no symlink; both platforms reference them root-relative.`);
    log('   openspec init, tools, the root ./context + ./{sdlc.config,pipelines}.json scaffold, and the context→agents mapper also run on apply.)');
    log('  Re-run without --check (add --force on an existing install) to apply.\n');
    exit(0);
  }

  // Establish the shared project-root workspace FIRST (canonical, root-only — no symlink), so the
  // per-platform strip in applyTarget never discards data: scaffold ./context/ (migrating any older
  // real per-platform context dir), then migrate any older real per-platform docs/memory to root.
  scaffoldRootContext(targets, vals);
  scaffoldRootConfig(vals);
  // docs/ workspace (intake's extra-docs/ ticket packages; project docs). memory/ baton workspace.
  // Both live ONCE at the root and are read root-relative by both platforms.
  migrateRealDirToRoot('docs', targets);
  migrateRealDirToRoot('memory', targets);
  { const d = join(TARGET, 'docs'); if (!existsSync(d)) { mkdirSync(d, { recursive: true }); log('  ✓ created docs/ (shared root)'); } }
  { const d = join(TARGET, 'memory'); if (!existsSync(d)) { mkdirSync(d, { recursive: true }); log('  ✓ created memory/ (shared root)'); } }
  // Upgrade path: split any legacy shared memory/<role>.md + openspec/_cross-spec-context.md (one
  // file every change appended to — a merge-conflict magnet across isolated change branches) into
  // one file per change. No-op once already migrated or on a fresh install.
  migrateSharedMemoryAndCrossSpecToPerChange();
  // Seed/refresh the per-role digest (_index.md) from whatever per-change fragments exist now —
  // covers both the split above and fragments from a prior install that predates the digest feature.
  backfillMemoryIndex();

  // Apply each target.
  for (const c of ctxs) applyTarget(c, vals);

  // Optionally manage the project's .gitignore (kit-owned framework + config block). Project-wide,
  // so run ONCE after all targets are applied.
  if (doGitignore) updateGitignore();

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
    // Marker-bounded (same pattern as the kit .gitignore block) so `--force` REFRESHES the kit-owned
    // rules whenever openspec-rules.yaml changes upstream, without clobbering any project-specific
    // rules a user hand-added outside the markers. Previously this checked "does `rules:` exist at
    // all" and left it untouched forever once installed — a kit-side rule fix (e.g. a new scope=tiny
    // exception) then silently never reached an already-onboarded project even after `--force`.
    try {
      const cfgPath = join(TARGET, 'openspec', 'config.yaml');
      const rulesSrc = join(SHARED_SRC, 'ai', 'openspec-rules.yaml');
      const RULES_START = '# --- kiro-sdlc-kit rules (managed by `init --force` — add project-specific rules OUTSIDE these markers) ---';
      const RULES_END = '# --- end kiro-sdlc-kit rules ---';
      if (existsSync(cfgPath) && existsSync(rulesSrc)) {
        const cfg = readFileSync(cfgPath, 'utf8');
        const rulesBlock = readFileSync(rulesSrc, 'utf8').replace(/\s*$/, '');
        const managedBlock = `${RULES_START}\n${rulesBlock}\n${RULES_END}\n`;
        const si = cfg.indexOf(RULES_START), ei = cfg.indexOf(RULES_END);
        if (si !== -1 && ei !== -1) {
          writeFileSync(cfgPath, cfg.slice(0, si) + managedBlock + cfg.slice(ei + RULES_END.length).replace(/^\n/, ''));
          log('  ✓ refreshed kit-managed rules: block in openspec/config.yaml');
        } else if (/^rules:/m.test(cfg)) {
          // Legacy unmarked install (pre-dates the marker fix). `rules:` was always appended LAST,
          // so everything from that line to EOF is the kit's old block — replace it with the fresh
          // marked one. If you had hand-customized it, check `git diff` and re-add your rules OUTSIDE
          // the new markers.
          const idx = cfg.search(/^rules:/m);
          writeFileSync(cfgPath, cfg.slice(0, idx).replace(/\s*$/, '') + '\n\n' + managedBlock);
          log('  ✓ migrated unmarked rules: block in openspec/config.yaml to the managed, refreshable form');
          log('    (hand-customized it before? check `git diff` and re-add your rules OUTSIDE the markers)');
        } else {
          writeFileSync(cfgPath, cfg.replace(/\s*$/, '') + '\n\n' + managedBlock);
          log('  ✓ installed kit per-artifact rules into openspec/config.yaml');
        }
      }
    } catch (e) { log(`  ! could not install openspec rules: ${e.message}`); }
  } else {
    log('\n  ! openspec CLI not found — this kit uses OpenSpec as its spec workspace. Install then re-run init:');
    log('      npm install -g @fission-ai/openspec@latest');
  }

  // Wire context → each Kiro agent's resources[] from .kiro/context-map.json. Runs LAST so the
  // root openspec/ (created by openspec init above) exists — context-map.json lists `openspec` as a KB.
  for (const c of ctxs) {
    if (c.platform !== 'kiro') continue;
    log('\n  Wiring context → agents (context-map):');
    try { applyContextMap({ kiroDir: c.outDir, log }); }
    catch (e) { log(`  ! context-map skipped: ${e.message}`); }
  }

  printNextSteps(targets, hasOpenspec);
}

main().catch((e) => die(e.message));
