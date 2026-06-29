---
description: Prepare a ticket's input package BEFORE the SDLC pipeline. Spawns the one-shot intake subagent to pull a Redmine ticket + the Figma UI it links to, normalize them into docs/extra-docs/<ticket_id>-<slug>/intake.md (+ images + figma-urls.txt), and relay an intake summary. Run this before /sdlc-full or /sdlc-fast. Usage: /intake <slug> <ticket-id>
argument-hint: <slug> <ticket-id>
---

# /intake — prepare the ticket input package (pre-S1)

You are the **main session**. This command spawns the **intake subagent** (one-shot) to turn a raw
ticket into a complete, normalized input package the analyst can read, then relays its summary. Run
it **before** `/sdlc-full` / `/sdlc-fast` so S1/S2 starts from full context, not a one-line request.

Request: **$ARGUMENTS**

> ### 🚫 INVARIANT — intake prepares INPUT, it does not write specs or code
> You spawn the intake subagent and relay its return. The subagent writes only
> `docs/extra-docs/**` + the CPP baton; it does **not** author `proposal.md`, spec deltas, or code
> (those are the analyst/developer's). Enforced by the `agent_type`-keyed PreToolUse hooks.

## What this does

1. **Parse `$ARGUMENTS`** → `<slug>` (kebab-case) + `<ticket-id>` (Redmine issue number). If only a
   ticket id is given, let the subagent propose a slug from the subject and confirm it on return.
2. **Spawn `intake` via the Task tool** (`subagent_type: intake`). It uses the Redmine + Figma MCP
   servers to fetch the issue, harvest Figma links, export screens, download attachments, and write
   `docs/extra-docs/<ticket_id>-<slug>/{intake.md,figma-urls.txt,figma/,attachments/}`. No CPP baton needed —
   this runs before any change is scaffolded.
3. **Relay the return + own the gaps.** The subagent returns the package path, a ticket one-liner,
   counts (screens/attachments), and a **gaps list** (`MISSING` sources + risky `[INFERRED]`).
   Present the gaps to the user; for any unreachable MCP source, get the content pasted and re-spawn
   so the package is complete.
4. **Next step.** Tell the user: run `/sdlc-full <slug> ticket <ticket-id>` (feature/cr/rebuild) or
   `/sdlc-fast bugfix <slug>` — the analyst will read `docs/extra-docs/<ticket_id>-<slug>/intake.md` as its
   primary input.

## Notes

- This is **not** an SDLC phase and runs **no gate** — it only produces the input package.
- The analyst subagent reads its per-ticket knowledge from `docs/extra-docs/<ticket_id>-<slug>/` +
  `figma-urls.txt`; this package satisfies that exactly. On Claude there's no `resources[]` wiring —
  discovery is by path.

→ For requirements/spec conventions the package feeds: **follow the analyst agent**.
