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
