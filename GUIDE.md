# kiro-sdlc-kit — User Guide (HDSD)

Step-by-step: install the kit, onboard your project, run a work item through the **S1→S6** pipeline,
pass the gates, and pull updates. For the *what* and *why* — the dual-target model, the two-layer
split, and the security model — see **[README.md](README.md)** (architecture overview).

---

## Prerequisite — OpenSpec CLI

This kit uses **[OpenSpec](https://github.com/Fission-AI/OpenSpec)** as its spec-driven
workspace backend. Install it first:

```bash
npm install -g @fission-ai/openspec@latest
```

## Install

From the target project root. **The only thing that differs between Kiro and Claude is
`--target`** — same command, same engine:

```bash
# run straight from GitHub (no clone, no npm publish — always latest):
npx github:<owner>/kiro-sdlc-kit ../my-project --title "My App"   # interactive: asks the platform

# choose the platform up front (skips the menu):
npx github:<owner>/kiro-sdlc-kit . --target claude   # Claude Code only  → .claude/
npx github:<owner>/kiro-sdlc-kit . --target kiro     # Kiro IDE only     → .kiro/
npx github:<owner>/kiro-sdlc-kit . --target both     # both              → .kiro/ + .claude/

# or from a local clone:
node /path/to/kiro-sdlc-kit/bin/init.mjs --target claude        # into current dir
node /path/to/kiro-sdlc-kit/bin/init.mjs ../other --target both # into another project
```

Flags: `--target kiro|claude|both` (which platform(s) to emit; default = interactive menu, or
**both** non-interactively), `--force` (overwrite kit files; never touches `openspec/`/`memory/`/`docs/`
contents, and **merges** `.claude/settings.json` so your `enabledPlugins`/`env`/`model` + extra
permissions survive a kit upgrade),
`--yes` (defaults, no prompts), `--title "Name"` (set the project title non-interactively),
`--check` / `--dry-run` (print the per-target add/overwrite/preserve/prune plan and exit — writes nothing),
`--gitignore` / `--no-gitignore` (force-add / never-touch the kit `.gitignore` block — see below).

**`.gitignore` (optional).** `init` offers to add a kit-owned block to the project's `.gitignore`
(interactive prompt defaults to **yes**; `--gitignore`/`--no-gitignore` decide it non-interactively).
The block ignores only what the kit **regenerates** on every `--force`: `.claude/`, `.kiro/`,
`/sdlc.config.json`, `/pipelines.json`. Your hand-authored knowledge — `context/`, `openspec/`,
`docs/`, `memory/` — is deliberately **kept committable**. The block is bounded by
`# >>> kiro-sdlc-kit >>>` / `# <<< kiro-sdlc-kit <<<` markers, so re-running `init` refreshes it in
place (never duplicates), and deleting the whole block opts you back into committing the kit.

`init` copies the framework for each target, runs `openspec init --tools <platform>` (scaffolds
`openspec/` + the namespaced `opsx`/`openspec-*` skills), scaffolds the root `./context/` +
`./memory/` + `./docs/` + config (all root-only, no symlink), strips any stale per-platform
copy/symlink a prior install left behind, and installs the `<platform>/tools/` engines. On
**Kiro** it also **wires context → agents** via the mapper (root-relative `file://./…` resources); on
**Claude** there is no wiring step — context is `@import`ed (`@../context/*`) in `CLAUDE.md` and skills
are auto-discovered.

> ⚠️ On **Claude**, agents/commands/hooks load only at session start. After `init` (or a `--force`
> update), open a **new Claude Code session** before the slash commands take effect.

## Usage — end to end

```
0. Setup once   →  1. Onboard project  →  1b. Intake ticket  →  2. Run a work item  →  3. Pass gates  →  4. Archive
   (per machine)    (per project)          (per work item, opt)   (per feature/fix)      (per phase)       (auto at S6)
```

**0. Setup (once)** — install the OpenSpec CLI, then init the kit into the repo for your platform:
```bash
npm install -g @fission-ai/openspec@latest
node /path/to/kiro-sdlc-kit/bin/init.mjs . --target claude   # or --target kiro / both
```

**1. Onboard the project (once per repo)** — establish the context contract every role reads:
- **Kiro:** open the **`onboarder`** agent (`ctrl+9`) and say "bắt đầu".
- **Claude:** run **`/onboarder`** — it spawns the one-shot onboarder subagent, drafts
  `./context/*.md`, and returns a **Facts-to-commit** table for your sign-off (the main
  session never finalizes context on its own).

  Either way it detects/asks your stack & domain, fills the shared root `./context/*.md` (read by
  both platforms, no symlink), and mirrors a summary into `openspec/config.yaml`. For a known stack,
  pre-fill first: `node <platform>/tools/apply-stack.mjs nestjs`. On Kiro, verify with `node .kiro/tools/doctor.mjs`.

**1b. Prepare the ticket input (optional, per work item)** — when the work originates from a Redmine
ticket (with a Figma UI link and/or a docs folder), run the **`intake`** agent first so the analyst
starts from a complete, captured package instead of a one-line request:
- **Kiro:** open the **`intake`** agent (`ctrl+6`) → `intake <slug> <ticket-id>`.
- **Claude:** run **`/intake <slug> <ticket-id>`**.

  It uses the Redmine + Figma MCP servers to pull the ticket description/status/attachments + the
  linked Figma screens, normalizes them into `docs/extra-docs/<ticket_id>-<slug>/` (`intake.md` +
  `figma-urls.txt` + `figma/` + `attachments/`), and — when the ticket has UI — plans **one
  `ui/<screen>.md` per screen** (layout, component states, fields, interactions). It reports any gaps.
  The **analyst** reads this folder as its primary S1 input; the **developer** reads `ui/*.md` when
  building the frontend at S4. Skip this step for ad-hoc work with no ticket.

> Over many features the context contract drifts (a new stack lands, new `docs/extra-docs/` packages
> pile up). Run **`context-refresh`** (Kiro `ctrl+7` · Claude `/context-refresh`) to re-scan, diff,
> update only what changed, and re-wire — the incremental counterpart to the onboarder.

**2. Run a work item** — state the work type:
```
# Kiro: open the orchestrator agent (sdlc-full ctrl+0 / sdlc-fast ctrl+5), then:
sdlc feature user-profile        # new capability (full S1–S6)
sdlc cr update-checkout-flow     # change request (MODIFIED spec delta)
sdlc rebuild legacy-billing      # re-implement existing behavior (parity-first)
sdlc bugfix fix-login-401        # bug, clear root cause (S4–S6, QA regression-only)
sdlc hotfix patch-payment-crash  # emergency (S4 + S6)

# Claude: launch the orchestrator AGENT (carries the pipeline guards; your plain session stays free):
claude --agent sdlc-full feature user-profile      # full S1→S6 · or "cr <slug>" · "rebuild <slug>"
claude --agent sdlc-fast bugfix fix-login-401      # fast-track · or "hotfix <slug>"
# (the /sdlc-full and /sdlc-fast slash commands inside a session just PRINT this launch line —
#  they deliberately don't orchestrate in the default session, which has no guards)
```
On Kiro, natural language works too ("fix bug …", "CR …", "tạo tính năng …"). Either way the
orchestrator scaffolds an OpenSpec change (`openspec/changes/<slug>/`), persists the work `type`
into `_state.json`, and **delegates** each phase to the right role agent (Claude: Task spawn · Kiro
CLI: "use the {role} agent"). Use the wrong flow for a change and it redirects you. To drive one
phase by hand, use `/analyst`, `/architect`, `/developer`, `/qa` (spawn one guarded role; do **not**
gate/advance).

**3. Pass the gates** — reply to the orchestrator (same words on both platforms):
- `approve` / `ok` / `LGTM` — pass the current gate.
- `nogo <reason>` — reject and loop back.
- `status` — show pipeline progress. · `continue` — resume from saved state.

Gates auto-pass on a clean audit only if `gates.auto_pass: true` in
`sdlc.config.json` (default `false` = always require explicit approve).

**4. Finish** — at S6 the developer agent runs `openspec archive`, folding the change's spec
deltas into the living `openspec/specs/` and moving the change to `openspec/changes/archive/`.

### Work types (`pipelines.json`)

| Type | Phases | Notes |
|------|--------|-------|
| `feature` | S1→S6 | full pipeline (delta `ADDED`) |
| `rebuild` | S1→S6 | full; read existing source for parity first |
| `cr` | S1→S6 | change request; delta `MODIFIED`; S3 optional |
| `bugfix` | S4→S6 | fast-track, skip S1–S3; S5 = regression only |
| `hotfix` | S4 + S6 | emergency; minimal build + post-deploy verify |
| `spike` | S1 + S2 | research → decision-doc.md; no code (escalate to `feature` on GO) |
| `tech-debt` | S3→S6 | refactor, zero behavior change; S3 confirms scope |

Phases / gates / lifecycle are defined **once** and reused; each type only lists which phases
it runs. Edit `pipelines.json` to tune a type per project — no prompt edits.

### Agents & shortcuts

| Role | Kiro (IDE key / CLI) | Claude | SDLC phase |
|------|----------------------|--------|------------|
| `sdlc-full` | `ctrl+0` agent | `claude --agent sdlc-full` | orchestrator **feature/cr/rebuild** (S1→S6) — delegates + gates |
| `sdlc-fast` | `ctrl+5` agent | `claude --agent sdlc-fast` | orchestrator **bugfix/hotfix** (fast-track S4+) |
| `analyst` | `ctrl+1` / `/analyst` | `/analyst` | S1 Req Intake + S2 Func Spec |
| `architect` | `ctrl+2` / `/architect` | `/architect` | S3 Design |
| `developer` | `ctrl+3` / `/developer` | `/developer` | S4 Build + S6 Release |
| `qa` | `ctrl+4` / `/qa` | `/qa` | S5 QA |
| `intake` | `ctrl+6` / `/intake` | `/intake` | pre-S1 input prep (Redmine + Figma → `docs/extra-docs/<ticket_id>-<slug>/`) |
| `context-refresh` | `ctrl+7` / `/context-refresh` | `/context-refresh` | context re-sync when it drifts (not an SDLC phase) |
| `onboarder` | `ctrl+9` / `/onboarder` | `/onboarder` | context setup (not an SDLC phase) |

The **orchestrator** (`sdlc-full`/`sdlc-fast`) is a dedicated agent you launch (Kiro: switch to it;
Claude: `claude --agent …`). It drives the whole pipeline and **delegates** each phase to its role
agent (Claude: Task spawn · Kiro CLI: "use the {role} agent" · `/agent swap` is the manual fallback).
The per-role commands (`/analyst` …) spawn one guarded role for a single phase. A plain session
(no role agent) is your unrestricted default workspace.

Both orchestrators are **thin wrappers** over the shared `sdlc-orchestration-core` skill (one
copy of the lifecycle/gate/CPP/dispute machinery); each declares only its own work types. An
orchestrator refuses to drive a change whose persisted `type` belongs to the other (it tells you
which to open), so you can't run the wrong pipeline.

## Fill the context (the part that makes it yours)

Run the **onboarder** (Kiro: `ctrl+9` agent · Claude: `/onboarder`). It:

1. **Scans the repo** (package.json / lockfiles / schema / folder layout / README) to
   auto-detect stack & architecture.
2. **Asks only for gaps** (domain, API/status policy, boundaries, glossary, legacy/parity).
3. **Writes** the shared root `./context/*.md` (one copy, read by both platforms).
4. **Wires** context → agents — on Kiro via the `context-mapper` skill (root-relative `file://./context/…`
   resources); on Claude the context files are `@import`ed (`@../context/*`) in `CLAUDE.md`, so there is
   nothing to re-wire.

You can also edit `./context/*.md` by hand (on Kiro, re-run
`node .kiro/tools/context-map.mjs` afterwards). When the project has moved on since onboarding —
a new stack, new `docs/extra-docs/` packages, changed conventions — run **`context-refresh`** (Kiro
`ctrl+7` · Claude `/context-refresh`) instead of re-onboarding: it diffs the repo against the
existing context, updates only what drifted (preserving curated facts), and re-wires.

> 🛟 **Preservation net.** Onboarder/context-refresh write through a PreToolUse hook that snapshots
> every `context/*.md` to `./.snapshots/` (rotating, last 5) **before** any overwrite, and
> append-guards `memory/*.md` (a write that would drop an existing `## ` section is blocked). So a
> bad refresh is always one `cp` from recovery. `.snapshots/` is local-only — add it to `.gitignore`
> if you don't want it tracked.

## Stack presets (multi-stack)

A preset pre-fills the stack-determined context and installs a stack-specific skill pack,
so onboarding a `nestjs`/`laravel`/`nextjs`/`fastapi` project is "pick a stack, go" instead of
answering everything by hand.

```bash
node <platform>/tools/apply-stack.mjs --list      # nestjs · laravel · nextjs · fastapi
node <platform>/tools/apply-stack.mjs nestjs      # seed stack.md+conventions.md, install skills
```

It seeds `context/stack.md` + `context/conventions.md` and copies the stack's skills into
`<platform>/skills/`. On **Kiro** it also merges them into `context-map.json`
(architect/developer/qa) and re-runs the mapper; on **Claude** there is no wiring step — the
skills under `.claude/skills/` are auto-discovered (model-invoked). The onboarder runs this
automatically when a stack matches; you then fill the project-specific files
(project/architecture/glossary). Add a new stack by dropping a folder under
`kit/shared/stacks/<name>/` (`context/`, `skills/`, `preset.json`) — shared stacks are emitted
to both `.kiro/stacks/` and `.claude/stacks/`.

## Health check

```bash
node .kiro/tools/doctor.mjs           # Kiro   — validates agent JSON + resources[] + context map
node .claude/tools/doctor-claude.mjs  # Claude — validates @imports, commands/subagents, hooks
```

Each platform ships its own structural validator (their internals differ completely). Both check
the root workspace + context completeness and exit non-zero on any FAIL (a WARN for unfilled
context is fine before onboarding).

- **`doctor.mjs`** (Kiro) validates agent JSON, every `resources[]` prompt/skill/knowledge-base
  reference, and the context map.
- **`doctor-claude.mjs`** (Claude) validates what Claude actually relies on: that **`CLAUDE.md`
  `@import`s resolve** (relative to the file's own dir — the #1 silent-failure mode), all 7 commands
  + 5 subagents exist, the **"only `developer` has the `Edit` tool" security invariant** holds, and
  `settings.json` hooks point at installed scripts/tools.

## Command cheat-sheet

```bash
# kit tools (zero-dependency Node, in <platform>/tools/)
#   Kiro installs:   doctor · context-map · context-check · apply-stack · pipeline-guard · cpp-guard
#   Claude installs: doctor-claude · context-check · apply-stack · pipeline-guard · cpp-guard  (no context-map)
node .kiro/tools/doctor.mjs                  # [Kiro]   structural health-check (agent JSON + resources[] + map)
node .claude/tools/doctor-claude.mjs         # [Claude] structural health-check (@imports + commands + hooks + Edit invariant)
node .kiro/tools/context-map.mjs            # [Kiro] re-wire agents after editing context/ or context-map.json
node <platform>/tools/context-check.mjs     # context completeness gate (exit 1 if TODO left)
node <platform>/tools/apply-stack.mjs --list # list stack presets
node <platform>/tools/apply-stack.mjs nestjs # apply a stack preset
node <platform>/tools/pipeline-guard.mjs --gate S3   # deterministic phase/gate guard (the orchestrator
                                                # calls this before every approve: blocks out-of-order
                                                # gates, fence-jumps, missing-artifact AND missing-CPP-
                                                # context approvals — it calls cpp-guard.mjs internally)
node <platform>/tools/cpp-guard.mjs --gate S3        # deterministic CPP context-baton check for a gate
node <platform>/tools/cpp-guard.mjs --role architect # advisory stop-hook check (reminds an agent that made
                                                # its deliverable but forgot the handoff/decisions baton)

# OpenSpec lifecycle (driven by the agents, but runnable by hand)
openspec list                               # active changes (pipeline state)
openspec change validate "<change-name>"    # structural gate (deltas well-formed)
openspec archive "<change-name>"            # merge spec deltas → openspec/specs/
```

## Updating

The kit evolves; each project pulls changes by re-running `init`. There's no live coupling,
so updates are explicit and legible:

```bash
# 1. Refresh your local kit source first (it's where init copies from):
git -C /path/to/kiro-sdlc-kit pull          # or just use `npx github:<owner>/kiro-sdlc-kit` (always latest)

# 2. Preview what the update would change — writes nothing (per target):
node /path/to/kiro-sdlc-kit/bin/init.mjs ../my-project --target claude --check

# 3. Apply it (re-state the same --target you installed with):
node /path/to/kiro-sdlc-kit/bin/init.mjs ../my-project --target claude --force
```

`init` records the kit version it installed in `<platform>/.kit-manifest.json` (one per target),
so `--force`/`--check` report the transition (e.g. `⬆ Upgrading kit 1.0.0 → 1.1.0`). On Claude,
re-init then **start a new session** so the refreshed agents/commands/hooks load. On apply it:

- **overwrites kit-owned files** (`agents/`, `skills/`, `steering/`, `ai/`, `hooks/`, `tools/`) —
  these belong to the kit; **local edits to them are replaced**. Customize via your `context/` and
  `pipelines.json`, not by editing agent/skill files.
- **preserves filled `context/*.md`** (any file without a `<!-- TODO` marker) — your project
  identity survives upgrades untouched. ⚠️ A **not-yet-onboarded** repo (context still has `<!-- TODO`
  markers) is treated as unfilled, so `--force` **re-scaffolds** those template files — pass
  `--title "Name"` when upgrading such a repo so its name isn't reset to the default.
- **merges `.claude/settings.json`** instead of clobbering it — the kit refreshes its own security
  policy (hooks + its permission entries + `$schema`), but your `enabledPlugins`/`env`/`model` and
  any extra `permissions` (e.g. from `/fewer-permission-prompts`) are kept and the allow/deny lists
  are unioned.
- **prunes stale files** the previous kit version shipped but this one dropped (renamed/removed
  agents or skills), using the manifest — so nothing phantom lingers to mis-wire the mapper.
- **never touches** `openspec/`, `memory/`, or `docs/` (per-project workspace).

Run `--check` first whenever you're unsure — especially on targets that aren't git repos, where
there's no `git diff` to fall back on.
