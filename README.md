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

Agents (`sdlc` ctrl+0 · `analyst` 1 · `architect` 2 · `developer` 3 · `qa` 4 ·
`onboarder` ctrl+9 · `rtk`).

## Install

From the target project root:

```bash
node /path/to/kiro-sdlc-kit/bin/init.mjs            # into current dir
node /path/to/kiro-sdlc-kit/bin/init.mjs ../other   # into another project
# or, once pushed:  npx gitlab:<group>/kiro-sdlc-kit
```

Flags: `--force` (overwrite kit files; never touches `specs/`/`memory/`), `--yes`
(defaults, no prompts).

`init` copies the framework, scaffolds `specs/` + `memory/` (symlinked from `.kiro/`),
installs the mapper engine at `.kiro/tools/context-map.mjs`, and **wires context → agents**
by running the mapper once.

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

## Notes

- `agents/examples/` are **illustrative format samples** (a reference domain); only their
  structure is meant to be reused. Replace with your own over time.
- `specs/` and `memory/` are per-project workspace and are never shipped by the kit.
- Each project owns its copy after `init` — no submodule coupling, no framework/project
  file mixing. To pull kit updates, re-run `init --force`.
