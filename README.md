# kiro-sdlc-kit

A **project-agnostic** Kiro IDE SDLC kit. Drop a full S1→S6 pipeline (orchestrator + 4
role agents + 24 skills + steering rules + hooks) into any project with one command,
then fill a small **context contract** so the agents understand *your* project.

The framework (agents/skills/process) is generic and frozen. Everything project-specific
lives in one place — `.kiro/context/` — and is wired to each agent declaratively. No
project domain is baked into the agents.

## Two layers

```
FRAMEWORK (generic, never edited per project)        CONTEXT (filled per project)
  .kiro/agents/    6 agents + scripts + examples        .kiro/context/
  .kiro/skills/    24 skills                               project.md       stack.md
  .kiro/steering/  5 generic rules (sdlc-workflow,         conventions.md   architecture.md
                   commit-policy, security, registry,      glossary.md      legacy-ref.md
                   rtk)
  .kiro/ai/        generic quality rules (sonar)        .kiro/context-map.json  ← wiring
```

Agents bind to `ctrl+0..4` + `ctrl+9` — see [Agents & shortcuts](#agents--shortcuts).

## Prerequisite — OpenSpec CLI

This kit uses **[OpenSpec](https://github.com/Fission-AI/OpenSpec)** as its spec-driven
workspace backend. Install it first:

```bash
npm install -g @fission-ai/openspec@latest
```

## Install

From the target project root:

```bash
node /path/to/kiro-sdlc-kit/bin/init.mjs            # into current dir
node /path/to/kiro-sdlc-kit/bin/init.mjs ../other   # into another project
# or, once pushed:  npx gitlab:<group>/kiro-sdlc-kit
```

Flags: `--force` (overwrite kit files; never touches `openspec/`/`memory/`), `--yes`
(defaults, no prompts).

`init` copies the framework, runs `openspec init --tools kiro` (scaffolds `openspec/` +
the `/opsx:*` skills), scaffolds `memory/`, symlinks `.kiro/openspec` + `.kiro/memory`,
installs the `.kiro/tools/` engines, and **wires context → agents** via the mapper.

## Usage — end to end

```
0. Setup once   →  1. Onboard project  →  2. Run a work item  →  3. Pass gates  →  4. Archive
   (per machine)    (per project)          (per feature/fix)      (per phase)       (auto at S6)
```

**0. Setup (once)** — install the OpenSpec CLI, then init the kit into the repo:
```bash
npm install -g @fission-ai/openspec@latest
node /path/to/kiro-sdlc-kit/bin/init.mjs .
```

**1. Onboard the project (once per repo)** — open the **`onboarder`** agent (`ctrl+9`) and
say "bắt đầu". It detects/asks your stack & domain, fills `.kiro/context/*.md`, mirrors a
summary into `openspec/config.yaml`, and re-wires context to every agent. For a known stack
you can pre-fill first: `node .kiro/tools/apply-stack.mjs nestjs`. Verify anytime with
`node .kiro/tools/doctor.mjs`.

**2. Run a work item** — open the orchestrator for your flow and state the work type:
```
# sdlc-full  (ctrl+0) — full S1→S6
sdlc feature user-profile        # new capability (full S1–S6)
sdlc cr update-checkout-flow     # change request (MODIFIED spec delta)
sdlc rebuild legacy-billing      # re-implement existing behavior (parity-first)

# sdlc-fast  (ctrl+5) — fast-track
sdlc bugfix fix-login-401        # bug, clear root cause (S4–S6, QA regression-only)
sdlc hotfix patch-payment-crash  # emergency (S4 + S6)
```
Natural language works too: "fix bug …", "hotfix …", "CR …", "tạo tính năng …". The
orchestrator scaffolds an OpenSpec change (`openspec/changes/<slug>/`), persists the work
`type` into `_state.json`, and routes each phase to the right role agent. Open the wrong
orchestrator for a change and it redirects you to the right one.

**3. Pass the gates** — reply to the orchestrator:
- `approve` / `ok` / `LGTM` — pass the current gate.
- `nogo <reason>` — reject and loop back.
- `status` — show pipeline progress. · `continue` — resume from saved state.

Gates auto-pass on a clean audit only if `gates.auto_pass: true` in `.kiro/sdlc.config.json`
(default `false` = always require explicit approve).

**4. Finish** — at S6 the developer agent runs `openspec archive`, folding the change's spec
deltas into the living `openspec/specs/` and moving the change to `openspec/changes/archive/`.

### Work types (`.kiro/pipelines.json`)

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

| Key | Agent | SDLC phase |
|-----|-------|------------|
| `ctrl+0` | `sdlc-full` | orchestrator for **feature/cr/rebuild** (S1→S6) — routes + gates |
| `ctrl+5` | `sdlc-fast` | orchestrator for **bugfix/hotfix** (fast-track S4+) — routes + gates |
| `ctrl+1` | `analyst` | S1 Req Intake + S2 Func Spec |
| `ctrl+2` | `architect` | S3 Design |
| `ctrl+3` | `developer` | S4 Build + S6 Release |
| `ctrl+4` | `qa` | S5 QA |
| `ctrl+9` | `onboarder` | context setup (not an SDLC phase) |
| — | `rtk` | hook-only (shell token saver) |

Both orchestrators are **thin wrappers** over the shared `sdlc-orchestration-core` skill (one
copy of the lifecycle/gate/CPP/dispute machinery); each declares only its own work types. An
orchestrator refuses to drive a change whose persisted `type` belongs to the other (it tells you
which to open), so you can't run the wrong pipeline.

## Fill the context (the part that makes it yours)

Open the **`onboarder`** agent (ctrl+9). It:

1. **Scans the repo** (package.json / lockfiles / schema / folder layout / README) to
   auto-detect stack & architecture.
2. **Asks only for gaps** (domain, API/status policy, boundaries, glossary, legacy/parity).
3. **Writes** `.kiro/context/*.md`.
4. **Re-wires** context → agents via the `context-mapper` skill.

You can also edit `.kiro/context/*.md` by hand and re-run `node .kiro/tools/context-map.mjs`.

## How context maps to each agent

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
node .kiro/tools/apply-stack.mjs --list      # nestjs · laravel · nextjs
node .kiro/tools/apply-stack.mjs nestjs      # seed stack.md+conventions.md, install skills, wire
```

It seeds `context/stack.md` + `context/conventions.md`, copies the stack's skills into
`.kiro/skills/`, merges them into `context-map.json` (architect/developer/qa), and re-runs
the mapper. The onboarder runs this automatically when a stack matches; you then fill the
project-specific files (project/architecture/glossary). Add a new stack by dropping a folder
under `kit/stacks/<name>/` (`context/`, `skills/`, `preset.json`).

## Pipeline config

`.kiro/sdlc.config.json` tunes pipeline behavior per project — **no prompt edits needed**.
It is loaded into every agent (via `context-map` `always`). Keys: `gates.auto_pass`,
`coverage.{diff,lines,branches}_threshold`, `security.stride_analysis` (auto/always/never),
`test_framework`, `sonar_scan`. The orchestrator honors `gates.auto_pass`; developer honors
`coverage.*`; analyst/qa honor `security.stride_analysis`.

## Health check

```bash
node .kiro/tools/doctor.mjs       # verify the whole install
```

Checks structure, agent JSON validity, that every prompt/skill/knowledge-base reference
resolves, workspace symlinks, and context completeness. Exits non-zero on any FAIL (WARN
for an unfilled context is fine before onboarding).

## Command cheat-sheet

```bash
# kit tools (zero-dependency Node, in .kiro/tools/)
node .kiro/tools/doctor.mjs                 # health-check the whole install
node .kiro/tools/context-check.mjs          # context completeness gate (exit 1 if TODO left)
node .kiro/tools/context-map.mjs            # re-wire agents after editing context/ or context-map.json
node .kiro/tools/apply-stack.mjs --list     # list stack presets
node .kiro/tools/apply-stack.mjs nestjs     # apply a stack preset
node .kiro/tools/pipeline-guard.mjs --gate S3   # deterministic phase/gate guard (the orchestrator
                                                # calls this before every approve: blocks out-of-order
                                                # gates, fence-jumps, and missing-artifact approvals)

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
  file mixing. To pull kit updates, re-run `init --force`.
