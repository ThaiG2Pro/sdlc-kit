# kiro-sdlc-kit

A **project-agnostic, dual-target** SDLC kit for **Kiro** (IDE + CLI) *and* **Claude Code**. Drop a
full S1→S6 pipeline (orchestrator + 4 role agents + 24 skills + steering rules + hooks) into
any project with one command, then fill a small **context contract** so the agents understand
*your* project.

One source emits both targets — `kit/shared/**` overlaid by `kit/targets/<platform>/**`. You pick
the platform at install time (`--target kiro|claude|both`); the framework (process, skills, gates,
security model) is identical on both. The project's **workspace + config** — `./openspec/`,
`./memory/`, `./context/`, `./sdlc.config.json`, `./pipelines.json` — lives **once at the project
root** and is symlinked into each `<platform>/`, so the two targets never drift and a kiro↔claude
switch never loses state. No project domain is baked into the agents.

| | **Kiro** (IDE + CLI) | **Claude Code** |
|---|---|---|
| Emits | `.kiro/` | `.claude/` |
| Launch the orchestrator | the `sdlc-full` agent (`ctrl+0` / select it) | `claude --agent sdlc-full <slug>` |
| Delegate a phase to a role | "use the {role} agent" (CLI) · `/agent swap` (IDE) | spawn the role subagent (Task tool) |
| Code-write guard identity | agent name via `argv[1]` | `agent_type` in the PreToolUse hook |
| Context wiring | `context-map.json` + mapper | `@import` in `CLAUDE.md`; skills auto-discovered |

On **both**, the orchestrator is a **dedicated agent** (`sdlc-full`/`sdlc-fast`) that drives the
pipeline, delegates each phase to its role agent, and owns the gates — it **never writes code** (only
the `developer` agent does) and is write-fenced to baton/state files. A **plain session** (no role
agent) is your **unrestricted default workspace** — the kit's `preToolUse` guards bind only the
role agents, so normal interactive work is never blocked.

## Two layers

```
FRAMEWORK — per-platform, re-emitted by init        SHARED — one root copy, symlinked into each platform
  <platform>/agents/   role + orchestrator agents       ./context/    project·stack·conventions·
  <platform>/commands/ slash commands (Claude)                        architecture·glossary·legacy-ref.md
  <platform>/skills/   24 skills                         ./openspec/   spec-driven workspace
  <platform>/steering/ always-on rules                  ./memory/     per-role memory
  <platform>/ai/  <platform>/tools/  rules + guards      ./sdlc.config.json · ./pipelines.json
  .kiro/context-map.json   (Kiro wiring only)            (.kiro/ and .claude/ each symlink to these)
```

`<platform>` is `.kiro/` or `.claude/`. The orchestrator is the **`sdlc-full`/`sdlc-fast` agent**
(Kiro: `ctrl+0`/`ctrl+5`; Claude: `claude --agent sdlc-full`). The `/sdlc-full` · `/sdlc-fast`
slash commands are thin **launchers**; the per-role commands (`/analyst` … `/onboarder`) spawn one
guarded role agent — see [Agents & shortcuts](#agents--shortcuts).

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
**both** non-interactively), `--force` (overwrite kit files; never touches `openspec/`/`memory/`),
`--yes` (defaults, no prompts), `--title "Name"` (set the project title non-interactively),
`--check` / `--dry-run` (print the per-target add/overwrite/preserve/prune plan and exit — writes nothing).

`init` copies the framework for each target, runs `openspec init --tools <platform>` (scaffolds
`openspec/` + the namespaced `opsx`/`openspec-*` skills), scaffolds `memory/`, symlinks
`<platform>/openspec` + `<platform>/memory`, and installs the `<platform>/tools/` engines. On
**Kiro** it also **wires context → agents** via the mapper; on **Claude** there is no wiring step
— context is `@import`ed in `CLAUDE.md` and skills are auto-discovered.

> ⚠️ On **Claude**, agents/commands/hooks load only at session start. After `init` (or a `--force`
> update), open a **new Claude Code session** before the slash commands take effect.

## Usage — end to end

```
0. Setup once   →  1. Onboard project  →  2. Run a work item  →  3. Pass gates  →  4. Archive
   (per machine)    (per project)          (per feature/fix)      (per phase)       (auto at S6)
```

**0. Setup (once)** — install the OpenSpec CLI, then init the kit into the repo for your platform:
```bash
npm install -g @fission-ai/openspec@latest
node /path/to/kiro-sdlc-kit/bin/init.mjs . --target claude   # or --target kiro / both
```

**1. Onboard the project (once per repo)** — establish the context contract every role reads:
- **Kiro:** open the **`onboarder`** agent (`ctrl+9`) and say "bắt đầu".
- **Claude:** run **`/onboarder`** — it spawns the one-shot onboarder subagent, drafts
  `.claude/context/*.md`, and returns a **Facts-to-commit** table for your sign-off (the main
  session never finalizes context on its own).

  Either way it detects/asks your stack & domain, fills `<platform>/context/*.md`, and mirrors
  a summary into `openspec/config.yaml`. For a known stack, pre-fill first:
  `node <platform>/tools/apply-stack.mjs nestjs`. On Kiro, verify with `node .kiro/tools/doctor.mjs`.

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
`<platform>/sdlc.config.json` (default `false` = always require explicit approve).

**4. Finish** — at S6 the developer agent runs `openspec archive`, folding the change's spec
deltas into the living `openspec/specs/` and moving the change to `openspec/changes/archive/`.

### Work types (`<platform>/pipelines.json`)

| Type | Phases | Notes |
|------|--------|-------|
| `feature` | S1→S6 | full pipeline (delta `ADDED`) |
| `rebuild` | S1→S6 | full; read existing source for parity first |
| `cr` | S1→S6 | change request; delta `MODIFIED`; S3 optional |
| `bugfix` | S4→S6 | fast-track, skip S1–S3; S5 = regression only |
| `hotfix` | S4 + S6 | emergency; minimal build + post-deploy verify |

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

## Security model — who can write what

A **role is a playbook, not an identity.** Loading a role's prompt ("I'm the architect now") borrows
its checklist; it does not grant its write-permissions. What a session may write is decided by its
**host-provided identity**, never by what it claims:

- **Kiro** — the active agent's name is its own hook's `argv[1]` (per-agent `preToolUse`). Claiming a
  role doesn't change it.
- **Claude** — a role agent (`claude --agent <role>` or Task-spawned) carries `agent_type`; a plain
  session has none.

Each identity gets a fixed write-fence (Kiro: `<agent>.json → toolsSettings.write.allowedPaths`;
Claude: `check-write-path.py`'s built-in policy, host-selected):

| Identity | May write | Code? |
|----------|-----------|-------|
| **plain session** (no role agent — your default workspace) | anything | your own session |
| orchestrator (`sdlc-full`/`sdlc-fast` agent) | **baton/state only** — `openspec/changes/**/_*`, `openspec/_*.md`, `memory/**` | ❌ |
| `analyst` | `openspec/**`, `docs/knowledge/**` | ❌ |
| `architect` | `openspec/**`, `docs/**` | ❌ |
| `qa` | `openspec/**`, `test/** … __tests__/**` | ❌ tests only |
| `onboarder` | `context/**`, `openspec/**` | ❌ |
| **`developer`** | `src/** app/** lib/** … package.json …` + the above | ✅ **only this one** |

Two consequences:
- The **orchestrator can't even produce a phase deliverable** — `proposal.md`/`design.md`/`tasks.md`/
  `specs/**`/`*-report.md` are not baton `_`-files, so if it tries to write one the guard blocks it
  (exit 2), forcing it to **delegate** to the role agent. So "the orchestrator does S3 itself" cannot
  happen — the guard, not goodwill, prevents it.
- Only the **developer** identity has code paths; impersonation can't escalate, because the guard
  keys on the host-provided identity, not the prose.

Three enforcement layers (defense in depth):
1. **Subagent `tools` frontmatter** — only `developer` is granted `Edit`.
2. **`permissions.deny`** (Claude `settings.json`) — coarse blanket bans (e.g. editing the kit's own
   agents/commands/settings). Not role-aware by design.
3. **PreToolUse guards** (`check-write-path.py` / `check-shell-command.py`) — role-aware,
   **fail-closed**, host-selected policy; the only layer that grants `developer` its code exception.
   The backstop, because an LLM's self-description ("I am the developer now") isn't trustworthy.

> The orchestrator is a **dedicated agent**, not your main session — so a **plain session is
> unrestricted** (the guards bind only the named role agents; normal work is never blocked). Code and
> every deliverable are produced by the **role agent**: on Claude the orchestrator spawns it (Task);
> on Kiro CLI it delegates ("use the {role} agent"); `/agent swap` is the manual fallback.

## Fill the context (the part that makes it yours)

Run the **onboarder** (Kiro: `ctrl+9` agent · Claude: `/onboarder`). It:

1. **Scans the repo** (package.json / lockfiles / schema / folder layout / README) to
   auto-detect stack & architecture.
2. **Asks only for gaps** (domain, API/status policy, boundaries, glossary, legacy/parity).
3. **Writes** `<platform>/context/*.md`.
4. **Wires** context → agents — on Kiro via the `context-mapper` skill; on Claude the context
   files are `@import`ed in `CLAUDE.md`, so there is nothing to re-wire.

You can also edit `<platform>/context/*.md` by hand (on Kiro, re-run
`node .kiro/tools/context-map.mjs` afterwards).

## How context maps to each agent (Kiro only)

> Claude does not use a context map — `CLAUDE.md` `@import`s the context files directly and
> skills are auto-discovered. This section applies to **Kiro** only.

`.kiro/context-map.json` declares, **per agent**, which skills + context files + project
doc folders it consumes. The mapper regenerates each agent's `resources[]` from it,
**skipping anything that doesn't exist** (so references never break):

```jsonc
"architect": {
  "skills": ["cross-artifact-audit", "api-design"],
  "knowledgeBase": ["ai", "context/stack.md", "context/architecture.md", "context/conventions.md"]
},
"extraDocs": { "architect": ["docs/architecture"] }   // optional project doc folders
```

Edit the map (or let the onboarder do it), then `node .kiro/tools/context-map.mjs`.
Never hand-edit `resources[]` in an agent JSON — it gets overwritten.

## Stack presets (multi-stack)

A preset pre-fills the stack-determined context and installs a stack-specific skill pack,
so onboarding a `nestjs`/`laravel`/`nextjs` project is "pick a stack, go" instead of
answering everything by hand.

```bash
node <platform>/tools/apply-stack.mjs --list      # nestjs · laravel · nextjs
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

## Pipeline config

`<platform>/sdlc.config.json` tunes pipeline behavior per project — **no prompt edits needed**.
Keys: `gates.auto_pass`, `coverage.{diff,lines,branches}_threshold`, `security.stride_analysis`
(auto/always/never), `test_framework`, `sonar_scan`. The orchestrator honors `gates.auto_pass`;
developer honors `coverage.*`; analyst/qa honor `security.stride_analysis`. (On Kiro it is loaded
into every agent via `context-map` `always`; on Claude it is read by the orchestrator command + guards.)

## Health check

```bash
node .kiro/tools/doctor.mjs           # Kiro   — validates agent JSON + resources[] + context map
node .claude/tools/doctor-claude.mjs  # Claude — validates @imports, commands/subagents, hooks
```

Each platform ships its own structural validator (their internals differ completely). Both check
workspace symlinks + context completeness and exit non-zero on any FAIL (a WARN for unfilled
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

## Notes

- `agents/examples/` are **illustrative format samples** (a reference domain); only their
  structure is meant to be reused. Replace with your own over time.
- **Workspace = OpenSpec**: features are OpenSpec *changes* at `openspec/changes/<name>/`
  (proposal + spec deltas + design + tasks); the orchestrator drives the lifecycle
  `openspec new change → /opsx:apply → openspec archive` across S1–S6, and `archive` folds
  the change's spec deltas into the living `openspec/specs/`. The onboarder mirrors the
  context contract into `openspec/config.yaml` so OpenSpec's own skills are project-aware.
- `openspec/` and `memory/` are per-project workspace and are never shipped by the kit.
- Each project owns its copy after `init` — no submodule coupling, no framework/project
  file mixing. To pull kit updates, re-run `init --force` (see **Updating** below).

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
  identity survives upgrades untouched.
- **prunes stale files** the previous kit version shipped but this one dropped (renamed/removed
  agents or skills), using the manifest — so nothing phantom lingers to mis-wire the mapper.
- **never touches** `openspec/` or `memory/` (per-project workspace).

Run `--check` first whenever you're unsure — especially on targets that aren't git repos, where
there's no `git diff` to fall back on.
