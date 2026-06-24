# {{PROJECT_TITLE}} — SDLC kit (Claude Code)

This project runs the **dual-target SDLC kit** on Claude Code. The orchestrator is the **main
session**, driven by a slash command; it spawns one-shot role subagents per phase and pauses for you
at each gate.

## Entry points

- **Full flow** (feature · cr · rebuild, S1→S6): `/sdlc-full <slug> ticket <id>`
- **Fast track** (bugfix · hotfix): `/sdlc-fast bugfix <slug>` · `/sdlc-fast hotfix <slug>`
- **Manage a running pipeline**: `approve` · `nogo <reason>` · `status` · `continue` ·
  `dispute bug #N — <claim>`
- **Project setup / context**: spawn the `onboarder` subagent first on a new project.

> 🚫 **Invariant:** only the **developer** subagent writes code. The main session (orchestrator) and
> the analyst/architect/qa/onboarder subagents treat the shell as read-only and write only specs/
> artifacts. This is enforced by the `agent_type`-keyed PreToolUse hooks in `.claude/settings.json`
> (a subagent's `agent_type` is present; the main session's is absent ⇒ it is the orchestrator).

## Always-on rules (steering)

@.claude/steering/security.md
@.claude/steering/sdlc-workflow.md
@.claude/steering/rules-registry.md

## Project context contract

@.claude/context/project.md
@.claude/context/stack.md
@.claude/context/conventions.md
@.claude/context/architecture.md
@.claude/context/glossary.md
@.claude/context/legacy-ref.md

## Notes

- **Stack-specific packs** (laravel / nestjs / nextjs, etc.) are installed as **model-invoked skills**
  under `.claude/skills/` so they load only when relevant — they are intentionally NOT `@import`ed
  here (keeps every session's base context small; see MIGRATION.md §7 Q2).
- The OpenSpec workspace (`openspec/`) is the spec backend; `.claude/sdlc.config.json` +
  `.claude/pipelines.json` configure gates, rigor, and the phase pipeline.
- After updating the kit, re-run `npx kiro-sdlc-init . --force` and start a **new session** — agents,
  commands, settings, and hooks load at session start, not mid-session.
