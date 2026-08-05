# {{PROJECT_TITLE}} — SDLC kit (Claude Code)

This project runs the **dual-target SDLC kit** on Claude Code. The SDLC orchestrator runs as a
**dedicated agent** (`claude --agent sdlc-full` / `sdlc-fast`); it spawns one-shot role subagents per
phase and pauses for you at each gate. Your plain `claude` session is your **unrestricted default
workspace** — the pipeline guards do not touch it.

## Entry points

- **Full flow** (feature · cr · rebuild, S1→S6): `claude --agent sdlc-full <slug> ticket <id>`
- **Fast track** (bugfix · hotfix): `claude --agent sdlc-fast bugfix <slug>` · `… hotfix <slug>`
- **Manage a running pipeline** (inside that agent session): `approve` · `nogo <reason>` · `status` ·
  `continue` · `dispute bug #N — <claim>`
- **Project setup / context**: run `/onboarder` first on a new project (drafts `./context/`,
  returns a Facts-to-commit table for your sign-off).
- **Run a single role directly** (D3): `/analyst` · `/architect` · `/developer` · `/qa` ·
  `/onboarder` — each spawns that one-shot role subagent with the active change's CPP baton. These
  run ONE phase and do **not** gate/advance the pipeline; gate from the orchestrator agent.
- `/sdlc-full` · `/sdlc-fast` (slash) are **launchers** — they only print the `claude --agent …`
  command; they do not orchestrate in this default session (it has no pipeline guards).

> 🚫 **Invariant:** only the **developer** subagent writes code. The **orchestrator** runs as the
> `sdlc-full`/`sdlc-fast` agent and the analyst/architect/qa/onboarder subagents treat the shell as
> read-only (specs/artifacts only). Enforced by the `agent_type`-keyed PreToolUse hooks in
> `.claude/settings.json`: `agent_type ∈ {sdlc-full, sdlc-fast}` ⇒ orchestrator (read-only);
> a role subagent's `agent_type` ⇒ its role policy; `developer` ⇒ writes code. A **bare main session**
> (no `agent_type`) is your unrestricted default — so do the SDLC pipeline inside the agent, not here.

## Essential project context (loaded every spawn)

<!-- Only non-verbose context that changes per-project. Steering files (security, sdlc-workflow, 
rules-registry) are role-specific reads referenced in agent docs, not defaults. Context lives ONCE
at the project root (./context/) — shared by both platforms, no symlink. -->
@../context/stack.md
@../context/conventions.md
@../context/glossary.md

## Optional context (agents read as needed)

Agents may reference these directly:
- `context/project.md` — for project overview
- `context/architecture.md` — for design/dev phases
- `context/legacy-ref.md` — for legacy code areas
- `.claude/steering/{security,sdlc-workflow,rules-registry}.md` — role-specific guidance

## Notes

- **Stack packs** (laravel / nestjs / nextjs, …) live in `.claude/stacks/<stack>/`. Activate:
  `node .claude/tools/apply-stack.mjs <stack>` (`--list` to see them) — seeds
  `./context/{stack,conventions}.md` and copies the pack's skills into `.claude/skills/` as
  **model-invoked skills** that load only when relevant. Deliberately NOT `@import`ed here, to keep
  base context small.
- **Golden examples** (`.claude/agents/examples/`) — worked reference artifacts (proposal, design,
  tasks, qa-report, dev-test-report, openapi, migration, handoff/state/progress, glossary). A role
  reads the matching one before authoring: it shows the *assembled* shape that the OpenSpec
  `<template>`/`<rules>` skeleton doesn't. Reference-only, never edited. **They show STRUCTURE, never
  a length target** — at `scope=tiny` an artifact should be a fraction of the example's length while
  still hitting every required section (each role's Hard Rules list the minimums that relax at `tiny`).
- `openspec/` is the spec backend; `sdlc.config.json` + `pipelines.json` (project root, read
  root-relative) configure gates, rigor, and the phase pipeline.
- After updating the kit: re-run `npx kiro-sdlc-init . --force` and start a **new session** — agents,
  commands, settings, and hooks load at session start.
