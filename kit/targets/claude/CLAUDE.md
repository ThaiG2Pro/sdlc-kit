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

## Always-on rules (steering)

@steering/security.md
@steering/sdlc-workflow.md
@steering/rules-registry.md

## Project context contract

<!-- Context lives ONCE at the project root (./context/) — shared by both platforms, no symlink.
     @imports resolve relative to THIS file's dir (.claude/), so the root copy is `@../context/*`. -->
@../context/project.md
@../context/stack.md
@../context/conventions.md
@../context/architecture.md
@../context/glossary.md
@../context/legacy-ref.md

## Notes

- **Stack-specific packs** (laravel / nestjs / nextjs, etc.) ship under `.claude/stacks/<stack>/`
  (a `preset.json` + `context/` + `skills/`). Activate one with
  `node .claude/tools/apply-stack.mjs <stack>` (`--list` to see them): it seeds
  `./context/{stack,conventions}.md` (shared root) and copies the pack's skills into `.claude/skills/`,
  where they become **model-invoked skills** that load only when relevant. They are intentionally
  NOT `@import`ed here — keeps every session's base context small (see MIGRATION.md §7 Q2). On
  Claude there is no `context-map.json` wiring step (skills auto-discover); that is Kiro-only.
- **Golden examples** — fully worked-out reference artifacts (proposal, design, tasks, qa-report,
  dev-test-report, openapi, migration, handoff/state/progress, glossary, …) live under
  `.claude/agents/examples/`. Role subagents should read the matching example before authoring an
  artifact: it shows the *assembled* document shape, which the OpenSpec `<template>`/`<rules>` (skeleton
  + checklist) do not. They are reference-only — never edited, never part of a change.
- The OpenSpec workspace (`openspec/`) is the spec backend; `sdlc.config.json` +
  `pipelines.json` (shared-root, at the project root — read root-relative) configure gates, rigor,
  and the phase pipeline.
- After updating the kit, re-run `npx kiro-sdlc-init . --force` and start a **new session** — agents,
  commands, settings, and hooks load at session start, not mid-session.
