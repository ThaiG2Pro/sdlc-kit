---
description: Re-sync the project context after drift. Spawns the one-shot context-refresh subagent to re-scan the repo against the existing context/ contract, report a Drift Report, update only what changed, and re-run the gates — then relays the diff for your sign-off. Run when a new stack/docs were added over several features, or when doctor warns. Usage: /context-refresh
argument-hint: (blank)
---

# /context-refresh — incremental context re-sync

You are the **main session**. This command spawns the **context-refresh subagent** (one-shot) to
detect and repair context drift, then relays its diff for your sign-off. Use it when the project has
moved on since onboarding (new stack, new `docs/extra-docs/` packages, changed conventions) and
`context/*.md` is stale. It is the **incremental** counterpart to `/onboarder` (which sets context
up the first time).

Request: **$ARGUMENTS**

> ### 🚫 INVARIANT — you confirm the diff; the subagent preserves, it does not reset
> You spawn the subagent and **own the sign-off**. It writes only `context/**` and
> `openspec/**` (drafts), preserves human-written facts, and returns a Drift
> Report; **you get explicit user confirmation** before treating the refreshed context as final. No
> code is written. Enforced by the `agent_type`-keyed PreToolUse hooks.

## What this does

1. **Spawn `context-refresh` via the Task tool** (`subagent_type: context-refresh`). It re-detects
   the current stack/deps/docs/conventions, diffs them against `context/*.md`, updates only the
   drifted fields, and runs `context-check.mjs` + `doctor-claude.mjs`.
2. **Relay the Drift Report + own sign-off.** It returns: the Drift Report
   (`Area | file:field | Current | Detected now | Evidence | Action`), the files it edited, a
   doc→role routing table for any new `docs/extra-docs/...` packages, any `UNKNOWN`, and the gate
   results. **Present these and ask the user to confirm** ("Confirm these updates (yes / edit
   <field> / no)"). If nothing drifted it returns "no drift detected" — relay that and stop.
3. **Multi-target note.** On a `--target both` install the Kiro side shares the same `context/*.md`,
   so tell the user to re-wire Kiro afterward: `node .kiro/tools/context-map.mjs` +
   `node .kiro/tools/doctor.mjs`.

## Notes

- Claude has no `context-map.json`; role subagents read context + docs by path, so "wiring" is
  static. New-doc routing is advisory (a table in the return).
- The completeness gate `node .claude/tools/context-check.mjs` must exit 0 before refreshed context
  is final — relay any ❌ items so the user can supply them.
- **Safety net:** the write hook snapshots each `context/*.md` to `.snapshots/` (last 5) before any
  overwrite, and append-guards `memory/*.md` — so a bad refresh is recoverable. Best run on a clean
  git tree. `.snapshots/` is local-only; add it to `.gitignore` if you don't want it tracked.

→ For the context contract's required fields: **follow the onboarder agent**.
