# Changelog

All notable changes to **kiro-sdlc-kit** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

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
