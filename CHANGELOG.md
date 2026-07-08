# Changelog

All notable changes to **kiro-sdlc-kit** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

**Theme — dual-target (Kiro + Claude Code) from one source, on a root-only shared workspace.**
The kit emits both `.kiro/` and `.claude/` from `kit/shared/**` + `kit/targets/<platform>/**`; the
project workspace/config (`context/`, `docs/`, `memory/`, `openspec/`, `sdlc.config.json`,
`pipelines.json`) lives once at the project root — no per-platform copy, no symlink — referenced
root-relative by both. The framework (process, skills, gates, security) is identical on both.

### Added

- **Claude Code target (`.claude/`).** Orchestrator runs as a dedicated `sdlc-full`/`sdlc-fast` agent
  that spawns one-shot role subagents; context via `@import`, skills auto-discovered. `--target
  kiro|claude|both` on `init` (per-target `.kit-manifest.json`; per-target `--check`/`--force` plans).
- **Role-aware security on Claude.** An `agent_type`-keyed PreToolUse hook enforces "only the developer
  writes code"; a bare main session (no `agent_type`) is your unrestricted workspace. Fail-closed.
- **Per-project code/test roots.** `sdlc.config.json.paths.{code_roots,test_roots}` extend the
  developer/qa write-fence (preserved across `--force`; interior-`**` globs supported).
- **`state-set.mjs` + `state-schema.mjs`.** Surgical, schema-validated `_state.json` writes; drift is
  rejected at write time and at `pipeline-guard` STEP 0 (was read-only/reactive — slipped through on
  terminal gates).
- **Role-memory write-back wired and gate-enforced.** Each role appends cross-spec lessons to
  `memory/<role>.md` at phase end and records the decision in `_state.json.memory_writeback.<role>`
  (`appended`/`nothing-reusable`); `cpp-guard` blocks the gate until set, and `sprint-retro` harvests at
  S6 as the safety net. Previously the read pointers existed but nothing ever wrote back.
- **Subagents granted their MCP tools.** intake/analyst/architect/qa frontmatter + `settings.json`
  allow `mcp__redmine` / `mcp__figma-legacy` / `mcp__bookstack` (Kiro `@figma` → `@figma-legacy`);
  fixes "No such tool available" when a subagent calls Redmine/Figma/BookStack.
- **`spike` + `tech-debt` pipeline types and a `fastapi` stack preset.** `spike` (S1+S2 → decision-doc,
  no code) and `tech-debt` (S3→S6, zero-behavior-change); `apply-stack fastapi` seeds context + skills.
- **Optional kit `.gitignore` block.** `init` ignores only kit-regenerated paths (`.claude/`, `.kiro/`,
  `/sdlc.config.json`, `/pipelines.json`); marker-bounded, refreshed in place, deletable to opt back in.
- **Intake plans the UI.** When a ticket has UI, intake writes one
  `docs/extra-docs/<ticket>-<slug>/ui/<screen>.md` per screen; the developer reads them at S4. New
  golden templates (`intake-example.md`, `ui-screen-example.md`).
- **Preservation net in the write hook.** Snapshots `context/**`/`memory/**` to `.snapshots/` (last 5)
  before any overwrite, and append-guards `memory/*.md` (a write dropping a `## ` section is blocked).
- **`ai/` reachable on Claude** — `developer`/`qa` point to `.claude/ai/sonar-policy.md` (+ `sonar-rules.md`).
- **A `scope` axis (`tiny`/`standard`) scales HOW MUCH a phase writes, independent of `type`/`rigor`.**
  `type` still picks which phases run and `rigor` how hard the gates squeeze; `scope=tiny` (set by
  whichever role first has real size evidence — analyst at S2, or developer at S4 for bugfix/hotfix)
  lets architect condense design.md sections the change doesn't touch to one line and skip an ADR's
  options table when only one approach is genuinely reasonable, and lets developer run
  affected-tests-only at intermediate checkpoints (the final checkpoint's depth — coverage, always —
  never shrinks; see `test_scope` below for its width). Default `standard` when unset; architect may
  escalate `tiny`→`standard`, never the reverse. Targets design.md ballooning to hundreds of lines and
  full test-suite reruns for a handful of changed lines.
- **A `test_scope` axis (`module`/`full`) controls WIDTH of the developer S4 final checkpoint AND the
  QA S5 independent re-run — both now read the same value instead of each defaulting to "the full test
  suite."** Resolved once at kickoff (runtime flag → `sdlc.config.json.tests.final_scope` → derive from
  `rigor`: full→full, lite→module) and persisted to `_state.json.test_scope`; validated by
  `state-schema.mjs`. `module` restricts the test AND lint/static-analysis commands to the
  module/directory containing every touched file (siblings included), instead of the whole app/repo.
  Fixes a real case: a 1-file, 25-AC Laravel change burned ~500k tokens at QA because `qa.md` said
  "re-run the full test suite yourself" with no scope awareness — QA re-ran the entire module's test
  suite AND a module-wide static-analysis pass on top of the developer's already-scoped final
  checkpoint, in addition to (not instead of) the correctly-scoped feature test. Neither role
  previously consumed `rigor` for test breadth — only for gate convergence and test-case format.
- **`memory/<role>/_index.md` — a one-line-per-change digest.** Every role-memory write-back now also
  appends one line to a per-role index; roles read the index FIRST (cheap, flat cost regardless of how
  much project history has accumulated) and open individual `memory/<role>/{change-name}.md` files
  only for entries that look relevant, instead of reading every past-change file on every run. `init`
  backfills the index from existing fragment files on upgrade (idempotent — safe to re-run). The
  write-fence append-guards `_index.md` the same way it already append-guards the fragment files
  (blocks a write that drops an existing digest line).
- **`scope=tiny` now applies to EVERY artifact, not just design.md.** Numeric floors that otherwise
  force padding — analyst's ≥10 edge cases and ≥3 happy/error ACs per story (`edge-case-enumerator`,
  `spec-auditor` C4, `openspec-rules.yaml`), architect's ≥2 tasks.md checkpoints — relax to ≥3, ≥1+1,
  and 1 (final only) respectively at `scope=tiny`; unset/`standard` keeps the original floors. A new
  universal rule in `sdlc-orchestration-core` SKILL.md states every golden example under
  `agents/examples/` shows required STRUCTURE, never a length target, and every role prompt now says
  so next to its own examples — a `scope=tiny` change's proposal.md/design.md/tasks.md/
  dev-test-report.md/qa-report.md should each be a fraction of the worked example's length while still
  hitting every required section.
- **CPP baton writes are batched, not per-decision** — the Kiro role prompts (analyst/architect/
  developer/qa) each had an "APPEND-AS-YOU-GO" rule instructing an immediate `_decisions.jsonl` write
  the moment any single AC/ADR/deviation/bug was finalized — a 25-decision phase meant 25 separate
  Write calls. Real cost: this is the literal Kiro-side mechanism behind a QA run that logged its bugs
  one Write at a time. Now each role accumulates decisions in-session and writes them in ONE batched
  pass (developer: per checkpoint segment, matching its existing multi-run structure; the other three:
  once per phase) — the CPP-completeness gate and stop-hook reminder already catch a genuinely missed
  entry, so immediate per-decision writes bought no real safety, only tool-call overhead. Claude target
  never had the AS-YOU-GO instruction, but batching wasn't explicit there either — both targets now
  explicitly say "accumulate, one batched Write" in all 4 role prompts, plus a terse-fields reminder
  (`decision`/`reasoning`: keyword/fragment, not full prose) right where each writes `_decisions.jsonl`.
  Also added a universal style rule in `sdlc-orchestration-core` SKILL.md restating this for the
  orchestrator's own awareness: CPP baton text fields are keyword/telegraphic by default at every
  scope — same information, fewer words — not just at `scope=tiny`.

### Changed

- **Shared workspace + config are root-only** (no symlink); framework runtime stays per-platform. `init`
  migrates older per-platform copies/symlinks to the root and merges `.claude/settings.json` (unions
  permissions; preserves `enabledPlugins`/`env`/`model`) instead of clobbering it.
- **Orchestrator is a dedicated agent**, write-fenced to baton/state files — it cannot author a phase
  deliverable, forcing delegation to the role agent (Claude: Task spawn · Kiro: subagent / `/agent swap`).
  A bare main session on Claude is the unrestricted default workspace.
- **Kiro orchestrators delegate via real subagents** (gained the `subagent` tool); the delegated role
  runs under its own write-fence. `/agent swap` remains the manual fallback.
- `apply-stack`, both doctors, the mapper, `context-check`, and `agent-spawn-context` all resolve the
  shared workspace at the project root; `settings.json` allow-list widened for the orchestrator's routine
  ops (Task spawn, `Write/Edit(openspec/** + memory/**)`, branch-create git) — code writes stay prompted.
- **Role memory + cross-spec bridge are now one-file-per-change, not one shared file.** Every SDLC
  change runs on its own isolated branch/worktree; a shared `memory/<role>.md` or
  `openspec/_cross-spec-context.md` that every branch appends to guarantees a merge conflict the moment
  two changes are in flight at once. Now each write-back targets `memory/<role>/<change-name>.md` /
  `openspec/_cross-spec-context/<change-name>.md` — unique filenames never collide across branches, and
  reads glob+concat the directory instead of one file. `cpp-guard`'s trailing check and
  `check-write-path.py`'s write-fence/append-guard already matched on path *prefixes* (`memory/**`,
  `openspec/_*.md` with fnmatch spanning `/`), so no guard code changed — only the agent
  prompts/skill instructions and `cpp-guard`'s cross-spec existence check. Existing shared files in a
  deployed project are migrated automatically (split by `## ` section into the new per-change files;
  the original is kept as `<file>.pre-migration-backup`).
- **Legacy shared memory/cross-spec paths are now hard-blocked**, not just migrated. A role running
  under a stale cached agent definition (agent defs only reload at session start — a session opened
  before an upgrade keeps using the old prompt for its whole lifetime) could otherwise keep
  recreating `memory/<role>.md` / `openspec/_cross-spec-context.md` indefinitely, silently
  reintroducing the shared-file merge-conflict hazard the per-change split was meant to remove.
  `check-write-path.py` now denies a write to those five exact legacy paths outright with a message
  pointing at the new per-change path and naming the stale-session cause, instead of allowing it
  through `memory/**`.
- **The per-change-file migration in `init.mjs` no longer clobbers its own backup.** A second
  migration pass (e.g. triggered by a stale session recreating the legacy file after the first
  upgrade) used to `rename()` straight onto `<file>.pre-migration-backup`, silently overwriting the
  first pass's backup — the actual mechanism behind a real data-loss incident. Backups are now
  numbered (`.pre-migration-backup`, `.pre-migration-backup.2`, …) and never overwritten.

### Fixed

- **Hooks survive a mid-session `cd`** — every hook runs `cd "${CLAUDE_PROJECT_DIR}" && …` and the
  scripts self-locate the project root, so a `cd` into a subdir no longer bricks the session (cwd-poisoning).
- **Guards read config from the project root** (`./pipelines.json` / `./sdlc.config.json`), not the
  per-platform paths removed by the root-only refactor.
- **`CLAUDE.md` `@import` paths** fixed to `@steering/…` / `@context/…` (were `@.claude/…`, silently
  dropping all steering + context at runtime).
- **Shared skills no longer hardcode `.kiro/`** — a per-platform `{{PLATFORM_DIR}}` token; a claude-only
  install no longer fails the gate guard or the xlsx generator.
- **`check-write-path` follows the host** (Claude built-in policy vs Kiro JSON); platform-prefixed write
  targets are blocked; `src/**` stays developer-only on every non-developer role.
- **`doctor-claude`** validates the kit-managed `.claude/CLAUDE.md` (not a project's own root file).
- **Gate-rejection vocabulary unified to `nogo`** — `sdlc-orchestration-core` SKILL.md internally named
  the same action `reject`, diverging from every user-facing doc/agent prompt (both platforms already
  said `nogo <reason>`). GUIDE.md now documents `nogo`'s default per-phase routing (S2→analyst ·
  S3→architect · S4→developer · S5→qa), how to override it when root cause is already known to sit in
  an earlier phase, and `dispute bug #N`'s BUG/DESIGN GAP/SPEC GAP routing — previously undocumented
  outside the shared skill.
- **Kiro `analyst.json`/`architect.json` write-fence never got `memory/**`** when role-memory
  write-back shipped (they were narrowed to `openspec/**` only in an earlier, unrelated pass) —
  `cpp-guard` required the write-back decision but the Kiro host physically blocked the write it
  gates on. `developer.json` had the same drift for `pkg/**`/`internal/**`/`cmd/**`/`e2e/**`/
  `pyproject.toml`, present in the built-in policy but never ported to its JSON. Also fixed
  `check-write-path.py`'s own self-test, which could not have caught this: run from the kit source
  tree, its cwd-relocation landed one directory short of the repo root, so every "Kiro host" vector
  silently fell back to the built-in policy instead of reading the real per-agent JSON; added
  `memory/<role>.md` + the missing developer-path vectors so this class of drift fails loudly.
- **`openspec/config.yaml`'s kit-installed `rules:` block was write-once, then frozen forever.**
  `init` checked "does `rules:` exist at all" and skipped re-installing it on every subsequent
  `--force` — so any upgrade to `kit/shared/ai/openspec-rules.yaml` (including the `scope=tiny`
  exceptions above) silently never reached an already-onboarded project; `openspec instructions`
  kept emitting the stale rules text no role prompt could override. Now marker-bounded
  (`# --- kiro-sdlc-kit rules ... ---`), like the kit's `.gitignore` block: `--force` replaces only
  the content between the markers, so kit-side rule fixes always propagate, while anything a project
  hand-added outside the markers survives. A one-time migration replaces an old unmarked block (it
  was always appended last, so everything from `rules:` to EOF is the kit's own content).
- **`normalize_path()` tried the `specs/` marker before `openspec/`** — a git-worktree write to
  `openspec/changes/<name>/specs/<cap>/spec.md` (cwd-strip doesn't apply to a worktree, a sibling
  dir) truncated at the inner `specs/` marker and never reached `openspec/`, dropping the prefix the
  allow-list needs and wrongly blocking the analyst's spec-delta write. Marker order is now
  `openspec/` before `specs/` (specific-before-general, matching every other marker pair); added
  regression vectors for both worktree shapes.
- **`check-shell-command.py` false-positive-blocked plain reads for restricted roles**, from a real
  incident (a QA re-run retried repeatedly and burned tokens on retries alone): the guard scanned raw
  command TEXT with no notion of quoting, so a literal `>` inside a grep/sed pattern (`grep -o
  '<Tag>.*</Tag>' file.xml`) or a `->` inside a quoted `--execute="Foo::bar()->baz()"` string looked
  identical to a real shell redirect and got blocked; separately, `phpstan analyse A.php B.php` was
  misread as "interpreter `php` running script `B.php`" because the script-file regex matched the
  tail of `A.php`'s OWN extension as if it were the interpreter name. Fixed by (1) blanking the
  CONTENTS of `'...'`/`"..."` string literals before the `_DENY` scan — quoted text is inert shell-wise,
  verified empirically that an UNQUOTED `->` really is a redirect (`echo a->b` creates file `b`) so
  this had to be quote-aware, not a blanket exclusion, or it would have opened a real bypass; (2) a
  `(?<!\.)` lookbehind on the script-execution rule so an interpreter name glued directly after a `.`
  (i.e., someone else's file extension) is never treated as a real invocation. 9 new self-test vectors
  cover both the fixed false positives and that real redirects/mutations still block. `mkdir`/`tee`
  remain absolute blocks for restricted roles (by design, not a bug) — use the Write tool or let the
  target command create its own directory.
- **No way to update `_state.json` without a full-file round-trip for array fields.** `state-set.mjs`
  only supported `--set`/`--unset` on scalars/objects; appending one `phase_history` entry (the one
  update every role makes every phase) meant reading the whole array, splicing in one element, and
  passing the ENTIRE thing back as a `--set` value — or falling back to a raw `Write` of the whole
  file, the exact per-gate full-rewrite cost `state-set.mjs` was built to eliminate. Added `--append
  <path>=<json>` (creates the array if unset); all four role prompts (both targets) now append their
  own `phase_history` entry instead of rewriting `_state.json` wholesale. Also added a non-blocking
  length nudge: an appended entry's `note`/`result`/`summary` past ~400 chars prints a warning — detail
  belongs in `_handoff.md`/`memory/<role>/`, which are read selectively; `phase_history` is read in
  full by every later phase, forever.
- **QA had no resume path after being killed mid-run.** An interrupted QA pass (another real incident)
  had no way to signal "partially done" — a re-spawn regenerated test scenarios and re-ran already-
  passed tests from scratch, re-spending the whole prior run's tokens. QA (both targets) now checks for
  an existing partial `qa-report.md`/`qa/testcases.*` first and continues from what's missing instead
  of restarting.
- **`_progress.md` was written TWICE per gate — once by the role, once by the orchestrator — using
  two INCOMPATIBLE formats.** Every role already writes its own table row (the shape in
  `agents/examples/progress-example.md`) when finishing a phase. Separately, the orchestrator's
  "Progress Marking (MANDATORY on gate approval)" step had it hunt for a `## Overall Progress`
  checkbox-list heading and flip `- [ ] {phase}` → `- [x]` — a format NO role's actual output has ever
  produced (grep confirms it appears nowhere else in the kit); this dead pattern-match forced the
  orchestrator into an ad-hoc full-file rewrite every approval, duplicating information the role had
  already written, in a shape that never matched. `cpp-guard`'s actual check is a loose count
  (`[x]`/`✅` occurrences ≥ passed-gate count) that the role's own row already satisfies, so the
  orchestrator's second write bought nothing. Removed it — `_progress.md` is now the role's artifact
  only, everywhere the orchestrator prompts (both targets' `sdlc-full`/`sdlc-fast` +
  `sdlc-orchestration-core` SKILL.md) previously said otherwise. Also closed a real gap this surfaced:
  the Claude-target role prompts listed `_progress.md` as a required CPP artifact but never actually
  said how/when to write it (Kiro's did) — all four now carry the same row-format instruction Kiro
  already had.
- **A stale Hard Rule still told the orchestrator to hand-rewrite `_state.json`** (`"NEVER create
  duplicate JSON keys — READ → parse → modify in-memory → WRITE whole file"`), left over from before
  `state-set.mjs` existed and directly contradicting the "never hand-rewrite" rule earlier in the same
  file. Now says to always use `state-set.mjs`.
- **A systematic 3-agent sweep for the same "leftover from an older design" bug shape found 8 more
  confirmed instances, each verified with grep evidence before fixing:**
  - `qa-analysis`/`qa-test-design`/`cross-artifact-audit` all read a `## _Structured Extract` section
    from `proposal.md` as their FIRST, authoritative input — but only the Kiro-target analyst.md ever
    had a rule requiring the analyst to write it (`R5: Structured Extract — MANDATORY Section`); the
    Claude-target analyst.md had zero mention of it. Every Claude-target QA/architect run was hunting
    for a section the Claude-target analyst was never told to produce. Added the equivalent `R5` to
    Claude's `analyst.md`.
  - Kiro `architect.md`'s S3-A/B/C sub-phase transitions hand-wrote `_state.json` as a raw JSON
    literal 3× per S3 phase, two paragraphs below the file's own `state-set.mjs`-only rule (R12) —
    now all three use `state-set.mjs --set current_phase=…`.
  - S6/archive in BOTH targets' `developer.md` hand-wrote `_state.json` with 3 fields at once,
    *in the same paragraph* whose very next sentence correctly used `state-set.mjs` for a smaller
    follow-up write — backwards from every other instance in the kit. Both now use `state-set.mjs`.
  - Kiro `developer.md`'s S4-FIX exit hand-wrote `_state.json` the same way — same fix.
  - `sdlc-orchestration-core` SKILL.md's Dispute Resolution and Convergence-loop sections described
    `disputes[]` and `convergence.<PHASE>` as raw JSON shapes with no `state-set.mjs` call given,
    unlike `phase_history`/`gates`/`deploy_status` which each get a worked example — both now do too
    (`--append disputes=…`, `--set convergence.<PHASE>.rounds=… --set convergence.<PHASE>.stable=…`).
  - Claude `architect.md`'s own `_state.json` bullet ended with a dangling `"READ → modify → WRITE
    whole file."` sentence directly contradicting the `state-set.mjs` command two lines above it — a
    copy/paste leftover from the boilerplate shared with `_handoff.md`/`_decisions.jsonl` (where that
    phrase IS correct), never rescoped when reused for `_state.json`. Removed.
  - `cross-artifact-audit` SKILL.md flagged any `tasks.md` with `< 2 checkpoints` as a gap with no
    `scope=tiny` exception, while architect's own Hard Rule R3 (both targets) and `openspec-rules.yaml`
    already carry the exception (1 final checkpoint is enough at `scope=tiny`) — the audit gate would
    flag a legitimately-tiny change's own correctly-sized `tasks.md` as defective, forcing padding or
    blocking convergence from ever stabilizing. Added the matching exception to the audit rule.
  - Kiro `developer.md`'s R13 ("run type-check, lint, format-check, test, AND coverage" at every
    checkpoint) contradicted the file's own later, `test_scope`-aware checkpoint rules two sections
    down (intermediate = affected-tests-only, no coverage; final = full `test_scope`-width + coverage)
    — R13 was never updated when `scope`/`test_scope` shipped. Now points at the detailed rule instead
    of restating a stale blanket version of it.
  - `sdlc-orchestration-core` SKILL.md's own CPP Contract Checks section still named the pre-migration
    flat `memory/<role>.md` path in one blockquote, contradicting the per-change-file path
    (`memory/<role>/{change-name}.md`) correctly used everywhere else in the same file and by every
    role prompt. Fixed the reference.
- **`memory/<role>/_index.md` added to the kit's `.gitignore` block** — real conflict reported: it's
  the one `memory/` artifact every parallel branch/worktree appends to at the SAME path (unlike
  `memory/<role>/{change-name}.md`, one unique file per change, which is exactly why THAT split
  happened). `context/`, `openspec/`, `docs/`, and the per-change memory files stay tracked/committed
  as before — only this specific derived digest is now ignored, since `init --force`'s
  `backfillMemoryIndex()` already regenerates it in full from the `{change-name}.md` files' own `## `
  headers, so nothing is lost by not tracking it.

### Tooling

- **`doctor-claude.mjs`** — structural health check for the Claude target: `CLAUDE.md` `@import`s
  resolve, all commands + subagents exist, the "only `developer` has `Edit`" invariant holds, and
  `settings.json` hooks point at installed scripts/tools.

## [1.1.0] — 2026-06-24

Three themes: a full skill audit, automatic git isolation per pipeline, and a working
per-pipeline test-case (`testcases.xlsx`) option. All changes are backward-compatible —
existing installs upgrade cleanly via `init --force` (kit-owned files are replaced; your
`openspec/` changes & specs, `memory/`, and filled `context/*.md` are preserved).

> **Upgrading:** run `node bin/init.mjs <project> --check` to preview, then `--force` to apply.
> ⚠️ `sdlc.config.json` is kit-owned and will be overwritten — diff first if you customized it.

### Added

- **Git isolation per pipeline.** When the orchestrator creates a new change it now auto-creates a
  dedicated **branch or worktree** before the first phase, so no pipeline ever codes on a protected
  branch or a previous feature's branch.
  - New `git` block in `sdlc.config.json`: `isolation` (`ask`/`branch`/`worktree`/`off`),
    `default_method`, `branch_naming` (`{type}/{ticket}-{slug}`), `worktree_path`, `protected_branches`.
  - The chosen method/branch is persisted to `_state.json.isolation`.
  - Orchestrators (`sdlc-full`/`sdlc-fast`) gain a narrowly-scoped `git` shell permission for
    branch/worktree creation only.
- **Per-pipeline test-case artifact option.** The `testcases.xlsx` deliverable for QA managers is now
  selectable **per change** (the knob existed but was orphaned — nothing produced or enforced it).
  - Resolved at kickoff: runtime flag (`--xlsx`/`--md`/`--no-xlsx`) → `qa.testcase_export` config seed
    → one kickoff question; the answer persists to `_state.json.testcase_export`.
  - Shipped a portable generator `kit/skills/qa-test-design/gen_testcases_xlsx.py` (Python + openpyxl,
    Status colour-coded; automatic **`.csv` fallback** when openpyxl is absent — no Node dependency).
  - The QA agent (S5) now actually produces the artifact (previously Phase 1 was forbidden).
- **Skill documentation in agent prompts.** Every wired skill is now documented (when/how to use) in
  its agent: `developer` +5 (`deployment-patterns`, `sonar-local`, `search-first`,
  `api-documentation-checker`, `agentic-engineering`), `architect` +1 (`search-first`), and
  `onboarder` gained a Skills section.
- `CHANGELOG.md` (this file); `__pycache__/` and `*.pyc` added to `.gitignore`.

### Changed

- **Test-case format** is now read from `_state.json.testcase_export` (the per-pipeline choice), not
  re-derived from config/rigor inside the skill.
- `sdlc-fast` no longer wires `spec-auditor` / `cross-artifact-audit` (those gates are S2/S3 and never
  run in fast-track); `sprint-retro` is kept (it runs at S6, which fast-track does reach).
- `R-SDLC-003` (branch policy) generalized from feature-only to **all** pipeline types, with the
  `{type}/{ticket}-{slug}` naming convention and a pointer to the `git` config block.
- Stack-coupled skills now defer to project conventions instead of hardcoding a stack:
  `api-design` and `cross-artifact-audit` defer to `context/conventions.md`; `security-audit` is
  stack-agnostic (Laravel/Next.js/zod equivalents alongside the NestJS examples); `verification-loop`
  uses the project's commands (`context/stack.md`) instead of literal `npm`/`vitest`/`tsc`.

### Fixed

- **S5 gate now enforces the test-case artifact** when selected: if `testcase_export ∈ {xlsx, md}`,
  `pipeline-guard.mjs` blocks the gate unless `qa/testcases.{xlsx|md|csv}` exists with ≥1 row
  (no auto-pass, even at 0 Critical/High). `none` and legacy state without the key skip the check.
- **Dead references removed** across skills: `search-first` (non-existent `planner`/`researcher`
  agents, `iterative-retrieval` skill), `agentic-engineering` (`tdd-workflow`),
  `api-documentation-checker` (phantom `api-doc-reminder` hook), `sonar-local` (phantom
  `scripts/sonar-local.sh` — `npx sonarqube-scanner` is now the primary path).
- **Phantom generator reference** in `qa-test-design` (`scripts/generate-test-excel.ts`) replaced with
  the shipped Python generator.
- Stale content fixes: `php-implicit-behavior-audit` de-branded (hardcoded vendor paths →
  `context/legacy-ref.md`); `context-mapper` example (`specs` key that doesn't exist);
  `assumption-detector` step number; `edge-case-enumerator` category list; `sprint-retro` gate table,
  cost model, and dead skill/agent references; `architect` description sync (`.md` ↔ `.json`).

### Security

- Hardened the orchestrator shell guard (`check-shell-command.py`): the new git permission is a tight
  allow-list — only `git checkout -b` / `git switch -c` / `git worktree add` (no command chaining or
  substitution); all other git working-tree mutations (`add`/`commit`/`checkout <file>`/`reset`/
  `merge`) stay blocked, and a pre-existing gap (`git branch -D/-m` delete/rename) is now closed.
  The "orchestrator never writes code" invariant is preserved.

[1.1.0]: https://github.com/your-org/kiro-sdlc-kit/releases/tag/v1.1.0
