# Changelog

All notable changes to **kiro-sdlc-kit** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

**Dual-target: Claude Code support.** The kit now emits both `.kiro/` (Kiro IDE) and `.claude/`
(Claude Code) from one source — `kit/shared/**` overlaid by `kit/targets/<platform>/**`. Pick the
platform at install time; the framework (process, skills, gates, security model) is identical on both.

### Added

- **`--target kiro|claude|both` flag on `init`.** Default is an interactive platform menu (or `both`
  non-interactively). Each target gets its own `<platform>/.kit-manifest.json`; `--check`/`--force`
  report per-target plans.
- **Claude Code target (`.claude/`).** The orchestrator is the **main session**, driven by slash
  commands: `/sdlc-full` and `/sdlc-fast` run the whole pipeline and spawn each role as a one-shot
  subagent; `/onboarder`, `/analyst`, `/architect`, `/developer`, `/qa` run a single role directly.
  Context is `@import`ed in `CLAUDE.md`; stack skills under `.claude/skills/` are auto-discovered
  (no `context-map.json`).
- **Role-aware security via PreToolUse hooks.** "Only the developer writes code" is enforced on
  Claude by an `agent_type`-keyed hook (a subagent's `agent_type` is present; the main session's is
  absent ⇒ orchestrator), mirroring the Kiro guard that reads the agent name from `argv[1]`. Fail-closed.
- **"Role is a playbook, not an identity" invariant** documented in the always-on `sdlc-workflow.md`
  steering and a new README **Security model** section: loading a role's prompt borrows its checklist,
  not its write-permissions; the write-fence is keyed to the host-provided identity (`argv[1]` /
  `agent_type`), so impersonating a read-only role is harmless and impersonating `developer` cannot
  escalate to code (the guard blocks any non-developer `src/**` write).

### Changed

- **`apply-stack.mjs` is platform-aware.** On Claude it seeds context + copies skills into
  `.claude/skills/` and skips the Kiro-only `context-map.json` merge/re-wire.
- **`openspec init --tools <platform>`** scaffolds the namespaced `opsx`/`openspec-*` skills for the
  chosen target(s).
- **Tooling per platform.** Kiro installs `doctor` + `context-map` + the shared guards. Claude
  installs `doctor-claude` + the shared guards (`context-check`, `apply-stack`, `pipeline-guard`,
  `cpp-guard`) — no `context-map` (skills auto-discover; nothing to wire).
- **`settings.json` allow-list widened for the orchestrator's routine ops.** `Task` (spawn role
  subagents), `Write`/`Edit(openspec/** + memory/**)`, and the branch-create git commands
  (`checkout -b` / `switch -c` / `worktree add`) are now pre-approved, so `/sdlc-full` no longer
  prompts on nearly every step. Code writes (`src/**`) are deliberately NOT allowlisted — they still
  prompt and stay hook-enforced; `deny(openspec/specs/**)` still wins over the new `allow(openspec/**)`.
- **Context is now a single shared project-root `./context/`, symlinked into each platform.**
  Previously each target had its own `<platform>/context/` (duplicated, drift-prone — the source of
  the dual-target sync/port pain). Now `init` scaffolds `./context/` once (like `openspec/` and
  `memory/`) and symlinks `.kiro/context` + `.claude/context` → `../context`. Fill once, both targets
  read it. Re-running `init --force` migrates an existing install (its filled per-platform context is
  copied to `./context` and preserved before the dir becomes a symlink). Stack-seeded context refs
  were de-tokenized (`{{PLATFORM_DIR}}/sdlc.config.json` → `sdlc.config.json`) since a shared file
  can't carry a per-platform token.
- **`sdlc.config.json` + `pipelines.json` are shared single-source root files too.** They joined
  `openspec/`/`memory/`/`context/`: `init` scaffolds them once at the project root and symlinks them
  into each `<platform>/`. Edit the root copy → both targets see it (no drift; a kiro↔claude switch
  never loses config). **Separation of concerns:** shared *workspace + project config* live once at
  the root (symlinked); *framework runtime* (`agents`, `commands`, `skills`, `steering`, `ai`,
  `tools`, `settings`/hooks) stays per-platform. Claude runtime artifacts are `.kiro/`-free, so a
  Claude session only touches `.claude/` paths (which resolve to the shared root via the symlinks).
- **The SDLC orchestrator is now a dedicated agent; the bare main session is unrestricted.**
  Previously the orchestrator WAS the Claude main session (via `/sdlc-full`), so the guards held
  every bare main session read-only — which blocked normal interactive work in a kit-installed
  project (e.g. `curl … | python3 -c "…"`), since a session with no `agent_type` was assumed to be
  the orchestrator. Now the orchestrator runs as a named top-level agent
  (`claude --agent sdlc-full` / `sdlc-fast`, carrying `agent_type=sdlc-full|sdlc-fast`); the guards
  hold *that* read-only, while a bare main session (no `agent_type`) on Claude is your **unrestricted
  default workspace**. New `.claude/agents/{sdlc-full,sdlc-fast}.md`; the `/sdlc-full` `/sdlc-fast`
  slash commands became thin launchers (orchestrating in the default session would have no guards).
  Kiro is unchanged (its orchestrator is already the named `sdlc-full` agent; a missing actor still
  fails closed). Trade-off: pipeline safety is "on inside the sdlc agent" rather than always-on.
- **Orchestrator delegates via Kiro CLI subagents, not just manual `/agent swap`.** Confirmed against
  the Kiro CLI docs that the kit's `.kiro/agents/*.json` is already Kiro-CLI-native (same schema:
  `toolsSettings.write.allowedPaths`, `hooks.preToolUse {matcher, command}` with exit-2 block,
  `fs_write`/`execute_bash` matchers, `keyboardShortcut`; per-agent hooks, agent identity baked as
  `argv[1]`) — so every guard works on Kiro CLI as-is. Kiro CLI also supports programmatic delegation
  ("use the {role} agent" → returns via the `summary` tool), which the orchestrator now uses as the
  primary routing mechanism (`/agent swap` is the manual fallback), matching how Claude spawns role
  subagents via Task. The delegated role runs under its own per-agent write-guard, composing with the
  orchestrator write-fence.
- **README** rewritten for dual-target install & usage.

### Fixed

- **`CLAUDE.md` `@import` paths were wrong for the install location.** The file installs to
  `.claude/CLAUDE.md`, but its imports used the `@.claude/steering/…` / `@.claude/context/…` prefix —
  and Claude Code resolves `@imports` relative to the **importing file's own directory**, so those
  resolved to the non-existent `.claude/.claude/…` and silently dropped **all** steering rules and
  the context contract at runtime. Fixed to `@steering/…` / `@context/…`.

- **Shared skills hardcoded `.kiro/` paths that break on a claude-only install.** Two were
  executable and would actually fail there — the mandatory gate guard
  (`node .kiro/tools/pipeline-guard.mjs`) and the QA test-case xlsx generator
  (`gen_testcases_xlsx.py`) — plus ~15 advisory refs (`.kiro/context`, `.kiro/sdlc.config.json`,
  `.kiro/steering`). They only worked so far because every test install also had `.kiro/`. Added a
  per-platform `{{PLATFORM_DIR}}` token (init substitutes `.kiro`/`.claude` for each target;
  `.md`/`.json` already go through substitution) and switched all shared refs to it. The
  now-redundant "translate `.kiro/` to `.claude/`" notes in the Claude commands were removed.
  (Guard-script `.py` comments/self-test vectors keep their literal `.kiro/` — they describe the
  dual-platform contract.)
- **The orchestrator could do a role's job itself (e.g. author `design.md` on `continue`) — no
  guard stopped it.** The guards only enforced "developer writes code (`src/**`)"; every non-code
  artifact lives under `openspec/**`, and the orchestrator's write policy was `openspec/**` (all of
  it), so it could write any phase deliverable with nothing tripping. "You don't do design yourself"
  was a soft instruction; `continue` didn't hard-block; and the gate's `"Generated by: architect"`
  provenance is self-declared (impersonation satisfies it). Fixed: the orchestrator's write allow-list
  is now restricted to the underscore-prefixed baton/state files (`_state.json`, `_progress.md`,
  `_handoff.md`, `_decisions.jsonl`, `_glossary.md`, `openspec/_cross-spec-context.md`) + memory — so
  writing `proposal.md`/`design.md`/`tasks.md`/`specs/**`/`*-report.md` is BLOCKED (exit 2), forcing
  delegation to the role agent (spawn on Claude / `/agent swap` on Kiro). The `sdlc-orchestration-core`
  prompt was hardened to match (INVARIANT 1: delegate every phase; `continue` = spawn/swap, never
  produce the deliverable). Applies to both Kiro and Claude.
- **`doctor-claude` validated the wrong `CLAUDE.md` on a project with its own root file.** It
  preferred `./CLAUDE.md` (the project's own doc, which has no `@import`s) and falsely warned about
  missing `@import` lines while never checking the kit's wiring. Now validates the kit-managed
  `.claude/CLAUDE.md` (falling back to root only if absent).
- **Write-guard blocked Claude subagents from `.claude/context/**` on dual-target projects.** With
  both `.kiro/` and `.claude/` installed, `check-write-path.py` always preferred the
  `.kiro/agents/<role>.json` allow-list ("Kiro JSON wins"), whose paths are all `.kiro/…` — so a
  Claude-session `onboarder` could fill the contract only into `.kiro/context/` and was blocked from
  `.claude/context/` (where the Claude session reads). Now the policy **source follows the host**
  (detected from the hook script's own install path): Claude host → the built-in role policy; Kiro
  host → the agent JSON. `src/**` stays blocked for every non-developer role. The self-test was
  rewritten to exercise the real `decide()` (it had pinned the source per vector, hiding the bug).

### Tooling

- **`doctor-claude.mjs` — structural health check for the Claude target** (the Kiro `doctor.mjs`
  validates agent JSON + `resources[]` + the context map, none of which exist on Claude). It verifies
  `CLAUDE.md` `@import`s resolve (relative to the file's dir — would have caught the bug above), all
  7 commands + 5 subagents exist, the **"only `developer` has the `Edit` tool"** security invariant
  holds, `settings.json` hooks point at installed scripts/tools, workspace symlinks, and context
  completeness. `node .claude/tools/doctor-claude.mjs`.

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
