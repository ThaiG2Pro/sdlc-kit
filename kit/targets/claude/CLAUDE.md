# {{PROJECT_TITLE}} — SDLC kit (Claude Code)

This project runs the **dual-target SDLC kit** on Claude Code backed by the **SDLC Context Engine** (`bin/sdlc-ctx`).
The orchestrator runs as a **dedicated agent** (`claude --agent sdlc-full` / `sdlc-fast`); it spawns one-shot role subagents per phase and pauses for you at each gate. Your plain `claude` session is your **unrestricted default workspace** — the pipeline guards do not touch it.

## Entry points

- **Full flow** (feature · cr · rebuild, S1→S6): `claude --agent sdlc-full <slug> ticket <id>`
- **Fast track** (bugfix · hotfix): `claude --agent sdlc-fast bugfix <slug>` · `… hotfix <slug>`
- **Manage a running pipeline** (inside that agent session): `approve` · `nogo <reason>` · `status` ·
  `continue` · `dispute bug #N — <claim>`
- **Project setup / context**: run `/onboarder` first on a new project (drafts `./context/`,
  returns a Facts-to-commit table for your sign-off).
- **Run a single role directly**: `/analyst` · `/architect` · `/developer` · `/qa` · `/onboarder`
- `/sdlc-full` · `/sdlc-fast` (slash) are launchers — they print the `claude --agent …` command.

> 🚫 **Invariant:** only the **developer** subagent writes code. The **orchestrator** runs as the
> `sdlc-full`/`sdlc-fast` agent and the analyst/architect/qa/onboarder subagents treat the shell as
> read-only (specs/artifacts only). Enforced by the `agent_type`-keyed PreToolUse hooks in
> `.claude/settings.json`: `agent_type ∈ {sdlc-full, sdlc-fast}` ⇒ orchestrator (read-only);
> a role subagent's `agent_type` ⇒ its role policy; `developer` ⇒ writes code. All agents are permitted
> to call `bin/sdlc-ctx` for fast, zero-overhead database state management.

## SDLC Context Engine (`bin/sdlc-ctx`)

Instead of repeatedly reading 24KB+ of markdown baton files (`_handoff.md`, `_decisions.jsonl`, `_state.json`), all agents query and update state via `bin/sdlc-ctx`:
- **State & Gates**: `bin/sdlc-ctx change get --change <id>`, `bin/sdlc-ctx gate inspect --change <id> --gate <name>`, `bin/sdlc-ctx gate pass --change <id> --gate <name>`
- **Chunky Context Queries**:
  - `bin/sdlc-ctx task inspect-context --change <id>`: Delivers active task + mapped ACs + reading order + risky areas + ADRs in 1 call.
  - `bin/sdlc-ctx qa inspect-context --change <id>`: Delivers change state + gate audit + verification matrix + open bugs in 1 call.
- **Batch Operations**:
  - `bin/sdlc-ctx knowledge index-batch --dir context`: Indexes all context files in 1 atomic transaction.
  - `bin/sdlc-ctx spec add-req-batch --change <id> --file <reqs.json>`: Inserts all ACs in 1 transaction.
  - `bin/sdlc-ctx qa record-tests-batch --change <id> --file <tests.json>`: Records batch test run outcomes.
- **Flexibility & In-flight Amendments**: `bin/sdlc-ctx flex patch-req`, `bin/sdlc-ctx flex supersede-adr`, `bin/sdlc-ctx flex split-task`, `bin/sdlc-ctx flex preview-impact`
- **Dual-Layer Git Sync**: `bin/sdlc-ctx sync export --change <id> --dir <dir>` automatically renders clean OpenSpec Markdown artifacts for Git commits and PR reviews.

## Project context — read by ROLE, not `@import`ed

Each role reads only its column; nothing here is loaded unless a role opens it.

| file | analyst | architect | developer | qa | note |
|---|:-:|:-:|:-:|:-:|---|
| `context/project.md` | ✓ | – | – | – | others: only if the change's domain is unfamiliar |
| `context/glossary.md` | ✓ | – | – | – | or query via `bin/sdlc-ctx glossary` |
| `context/stack.md` | – | ✓ | ✓ | ✓ | dev/qa: the ACTUAL build/test/lint commands |
| `context/conventions.md` | – | ✓ | ✓ | ✓ | analyst: only when writing INT-tagged requirements |
| `context/architecture.md` | – | ✓ | ✓ | – | analyst/qa: only for INT-tagged / integration tests |
| `context/legacy-ref.md` | ◐ | ◐ | ◐ | ◐ | ◐ = only when the change touches a legacy area |
| `.claude/steering/security.md` | ✓ | ✓ | – | – | developer/qa get it via the security skills |
| `.claude/steering/sdlc-workflow.md` | – | – | – | – | process is already in each role prompt; open only when unsure of a gate |

**At `scope=tiny`** every role queries `bin/sdlc-ctx change get` and reads (dev/qa) `context/stack.md` — no heavy file reads.

## Notes

- **Stack packs** (laravel / nestjs / nextjs, …) live in `.claude/stacks/<stack>/`.
- `openspec/` is the spec backend; `sdlc.config.json` + `pipelines.json` configure gates, rigor, and phase pipeline.
- Dual-layer sync keeps Git history clean: artifacts exist in SQLite during agent execution, and are exported to Markdown at every gate.
