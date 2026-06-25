---
description: (launcher) The full-flow SDLC orchestrator (feature · cr · rebuild, S1→S6) runs as a dedicated agent so your default session stays unrestricted. This command tells you how to launch it — it does NOT orchestrate here.
argument-hint: <feature-slug> [ticket <id>]
---

# /sdlc-full → launch the orchestrator agent

The full-flow orchestrator runs as a **dedicated top-level agent**, not in this default session.
That keeps your normal session's shell unrestricted while the pipeline stays guarded (the
orchestrator is held read-only via `agent_type=sdlc-full`; only the developer subagent writes code).

**Relay this to the user, then STOP — do not orchestrate here:**

> Launch the orchestrator in its own session:
> ```
> claude --agent sdlc-full <feature-slug> ticket <id>     # or:  "CR <slug>"  ·  "rebuild <slug>"
> ```
> Then, inside that session, manage the pipeline with: `approve` · `nogo <reason>` · `status` ·
> `continue` · `dispute bug #N — <claim>`.

Do NOT run `pipeline-guard`, spawn role subagents, edit specs, or write code from this command —
**this default session has no orchestration guards.** All pipeline work happens in the
`sdlc-full` agent. (For a single phase by hand you can still use `/analyst` · `/architect` ·
`/developer` · `/qa`, which spawn one guarded role subagent.)
