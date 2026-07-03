# kiro-sdlc-kit

A **project-agnostic, dual-target** SDLC kit for **Kiro** (IDE + CLI) *and* **Claude Code**. Drop a
full S1→S6 pipeline (orchestrator + 4 role agents + 3 utility agents + 24 skills + steering rules + hooks) into
any project with one command, then fill a small **context contract** so the agents understand
*your* project.

> 📖 **Installing & using the kit?** → **[GUIDE.md](GUIDE.md)** (the User Guide / HDSD: install,
> onboard, run a work item, pass gates, update). **This README is the architecture overview** — what
> the kit is and how it's built.

One source emits both targets — `kit/shared/**` overlaid by `kit/targets/<platform>/**`. You pick
the platform at install time (`--target kiro|claude|both`); the framework (process, skills, gates,
security model) is identical on both. The project's **workspace + config** — `./openspec/`,
`./memory/`, `./context/`, `./docs/`, `./sdlc.config.json`, `./pipelines.json` — lives **once at the
project root, with no per-platform copy and no symlink**. Both platforms reference it **root-relative**
(Claude: `@../context/*` in `CLAUDE.md`, `openspec/…`/`docs/…` via the Read tool; Kiro: `file://./<entry>`
resources wired by the mapper), so the two targets never drift, a kiro↔claude switch never loses state,
and **removing one platform never breaks the other** (there are no cross-platform links to dangle). No
project domain is baked into the agents.

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
FRAMEWORK — per-platform, re-emitted by init        SHARED — one root copy (no symlink), referenced root-relative
  <platform>/agents/   role + orchestrator agents       ./context/    project·stack·conventions·
  <platform>/commands/ slash commands (Claude)                        architecture·glossary·legacy-ref.md
  <platform>/skills/   24 skills                         ./openspec/   spec-driven workspace
  <platform>/steering/ always-on rules                  ./memory/     per-role memory
  <platform>/ai/  <platform>/tools/  rules + guards      ./docs/       intake packages + project docs
  .kiro/context-map.json   (Kiro wiring only)            ./sdlc.config.json · ./pipelines.json
                                                         (both platforms read these at the root, no symlink)
```

`<platform>` is `.kiro/` or `.claude/`. The orchestrator is the **`sdlc-full`/`sdlc-fast` agent**
(Kiro: `ctrl+0`/`ctrl+5`; Claude: `claude --agent sdlc-full`). The `/sdlc-full` · `/sdlc-fast`
slash commands are thin **launchers**; the per-role commands (`/analyst` … `/onboarder`) spawn one
guarded role agent — see [GUIDE.md § Agents & shortcuts](GUIDE.md#agents--shortcuts).

**Separation of concerns:** the shared *workspace + project config* live once at the root; the
*framework runtime* (`agents`, `commands`, `skills`, `steering`, `ai`, `tools`, `settings`/hooks)
stays per-platform. Edit the root copy of `context/` / `sdlc.config.json` / `pipelines.json` → both
targets see it (no drift; a kiro↔claude switch never loses config). Each project owns its copy after
`init` — no submodule coupling, no framework/project file mixing.

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
| `analyst` | `openspec/**`, `memory/**` | ❌ |
| `architect` | `openspec/**`, `memory/**` | ❌ |
| `qa` | `openspec/**`, `memory/**`, `test/** … __tests__/**` | ❌ tests only |
| `intake` | `docs/extra-docs/**` + baton/state only | ❌ input docs only |
| `context-refresh` | `context/**`, `openspec/**` | ❌ |
| `onboarder` | `context/**`, `openspec/**` | ❌ |
| **`developer`** | `src/** app/** lib/** … package.json …` + the above | ✅ **only this one** |

Two consequences:
- The **orchestrator can't even produce a phase deliverable** — `proposal.md`/`design.md`/`tasks.md`/
  `specs/**`/`*-report.md` are not baton `_`-files, so if it tries to write one the guard blocks it
  (exit 2), forcing it to **delegate** to the role agent. So "the orchestrator does S3 itself" cannot
  happen — the guard, not goodwill, prevents it.
- Only the **developer** identity has code paths; impersonation can't escalate, because the guard
  keys on the host-provided identity, not the prose. A project whose code lives off the standard roots
  extends the fence via `sdlc.config.json.paths.{code_roots,test_roots}` (preserved across `--force`).

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

## Context preservation protocol (CPP) & gate guards

Every phase hands the next a **baton** of underscore-prefixed context files in the change dir —
`_handoff.md`, `_decisions.jsonl`, `_glossary.md`, `_progress.md`, `_state.json` — plus the cross-spec
bridge, one file per change: `openspec/_cross-spec-context/<change-name>.md` (never a single shared
file every branch would conflict on). This is **deterministically enforced**, not just prose:

- **`pipeline-guard.mjs`** (the orchestrator calls it before every approve) blocks out-of-order gates,
  fence-jumps, and missing-artifact approvals; its **STEP 0** rejects a drifted `_state.json`.
- **`cpp-guard.mjs`** fails a gate when the outgoing phase's baton is incomplete — and now also when a
  role hasn't recorded its **role-memory write-back decision** (`_state.json.memory_writeback.<role>` ∈
  {`appended`, `nothing-reusable`}), closing the gap where a one-shot agent returned and silently lost
  its only chance to persist a cross-spec lesson.
- **`state-schema.mjs`** validates the canonical `_state.json` shape at write time (via `state-set.mjs`)
  and at guard STEP 0, so drift surfaces immediately instead of one gate later.

Trailing side-effects the orchestrator owes (cross-spec bridge at S3, progress marking, the
convergence loop at `rigor=full`) are verified at the next gate. `sprint-retro` at S6 is the final
safety net — it harvests any skipped inline memory write-back into `memory/<role>/<change-name>.md`
(one file per change, so parallel branches never conflict on a shared memory file).

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

## Pipeline config

`sdlc.config.json` (shared root) tunes pipeline behavior per project — **no prompt edits needed**.
Keys: `gates.auto_pass`, `coverage.{diff,lines,branches}_threshold`, `security.stride_analysis`
(auto/always/never), `test_framework`, `sonar_scan`, `git.{isolation,branch_naming,protected_branches,…}`,
and `paths.{code_roots,test_roots}` (extend the developer/qa write-fence). The orchestrator honors
`gates.auto_pass` + `git.*`; developer honors `coverage.*`; analyst/qa honor `security.stride_analysis`.
(On Kiro it is loaded into every agent via `context-map` `always`; on Claude it is read by the
orchestrator + guards.) `pipelines.json` (also shared root) defines the phases/gates/lifecycle once
and the per-type phase lists — edit a type to tune it per project.

## Notes

- `agents/examples/` are **illustrative format samples** (a reference domain); only their
  structure is meant to be reused. Replace with your own over time.
- **Workspace = OpenSpec**: features are OpenSpec *changes* at `openspec/changes/<name>/`
  (proposal + spec deltas + design + tasks); the orchestrator drives the lifecycle
  `openspec new change → /opsx:apply → openspec archive` across S1–S6, and `archive` folds
  the change's spec deltas into the living `openspec/specs/`. The onboarder mirrors the
  context contract into `openspec/config.yaml` so OpenSpec's own skills are project-aware.
- `openspec/` and `memory/` are per-project workspace and are never shipped by the kit.
- To pull kit updates, re-run `init --force` — see [GUIDE.md § Updating](GUIDE.md#updating).
