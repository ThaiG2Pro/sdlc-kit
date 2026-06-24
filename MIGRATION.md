# MIGRATION — Kiro → Claude Code (dual-target)

> Status: **PLAN / for review**. Nothing here is implemented yet.
> Goal: ship the SDLC kit for **both** Kiro IDE and Claude Code from one source,
> letting the user pick the platform at `init` time (like `create-vite` / `create-next-app`).

This doc is the living spec for the migration itself. It records the locked
decisions, the platform concept-map, the security model (the highest-risk part),
the kit-layout refactor, the new `init` selection UX, and a phased execution plan.

---

## 0. Locked decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Scope | **Dual-target** — one kit source emits `.kiro/` and/or `.claude/`. Keep Kiro users, add Claude users. |
| D2 | Orchestrator entrypoint | **Slash commands** `/sdlc-full`, `/sdlc-fast` (with `$ARGUMENTS`). |
| D3 | Direct role interaction | **Yes** — add `/analyst /architect /developer /qa /onboarder`, each spawns that role subagent with the current baton. |
| D4 | Platform selection | **User chooses at init**: interactive menu (TTY) + `--target kiro\|claude\|both` flag (non-TTY/scripted). |

---

## 1. The core architectural shift (drives everything else)

|  | Kiro | Claude Code |
|---|---|---|
| Model | N peer agents; user presses **ctrl+0..9 to swap** | 1 main session **spawns subagents** via the Task/Agent tool |
| Orchestrator | An agent that *advises* the user to swap (cannot invoke peers) | The **main session**, which actually invokes role subagents and reads their results |
| Role agent | Its own persistent conversation + state | A **one-shot** subagent: hidden context, returns one final message |
| Gates (approve/nogo) | User drives by swapping back to the orchestrator | **Live in the main session** — a subagent is one-shot and cannot pause to ask the user mid-run |

Consequences:

1. **Orchestrator = main session** (kicked off by a slash command). It spawns one role
   subagent per phase, then **pauses for the user** at each gate. Do **not** make the
   orchestrator a subagent — subagents cannot ask the user questions mid-run.
2. **CPP baton files matter MORE, not less.** Subagent context is ephemeral, so
   `_handoff.md` / `_state.json` / `_decisions.jsonl` / `_glossary.md` / `_progress.md`
   are the *only* continuity between phases. This layer ports unchanged.
3. This is a **net upgrade**: in Kiro the orchestrator never truly controlled the role
   agents (the user could wander into the wrong agent — the "accidentally switched to
   sdlc-fast" failure mode). In Claude the orchestrator executes the pipeline.

---

## 2. Concept map (Kiro → Claude Code)

| Kiro | Claude Code | Effort |
|---|---|---|
| `.kiro/agents/*.json` | `.claude/agents/*.md` (YAML frontmatter + body) | rewrite format |
| `prompt: file://*.md` | the `.md` body itself | merge |
| `tools` / `allowedTools` | frontmatter `tools: [...]` (**tool-NAME only**, no path) | direct |
| `toolsSettings.write.allowedPaths` | **PreToolUse hook** (path-guard) + `permissions.deny` | port hook |
| `toolsSettings.shell.allowedCommands` (Kiro does **not** enforce) | `permissions.allow/deny` `Bash(...)` **+** PreToolUse hook (actually enforced) | upgrade |
| `hooks.preToolUse` matcher `fs_write` | PreToolUse matcher `Write\|Edit\|MultiEdit` | change matcher + JSON shape |
| `hooks.preToolUse` matcher `execute_bash` | PreToolUse matcher `Bash` | change matcher + JSON shape |
| `hooks.agentSpawn` (inject context) | `SessionStart` hook (main) / inject via subagent prompt | split |
| `hooks.stop` (detect non-spec changes) | `Stop` + **`SubagentStop`** (carries `agent_type`) | upgrade |
| `hooks.userPromptSubmit` | `UserPromptSubmit` hook | direct |
| steering KB (`.kiro/steering/*.md`) | `CLAUDE.md` + `@import` (recursive, max 4 hops) | direct |
| `knowledgeBase` resources (indexed) | `@import` in CLAUDE.md / read on-demand / skill | simplify |
| skills (`.kiro/skills/*/SKILL.md`) | `.claude/skills/*/SKILL.md` | **near drop-in** |
| `keyboardShortcut: ctrl+N` | slash command `/sdlc-full`, `/analyst`, … | swap mechanism |
| `welcomeMessage` | gone (→ command `description`) | drop |
| `model: claude-sonnet-4.6` | `model: sonnet \| opus \| inherit` | rename |
| orchestrator routes (advisory) | main session spawns Task (real) | redesign |

---

## 3. Security model — the highest-risk part (this is the incident that started it all)

The whole reason for this work: an orchestrator wrote code directly, bypassing
"only the developer writes code". The Claude port makes that guard **cleaner** than
Kiro and adds a **native** enforcement layer Kiro lacked.

### 3.1 The key platform fact

The Claude Code **PreToolUse hook input carries `agent_id` + `agent_type`**
— present **only** when the tool call comes from a Task-spawned subagent; **absent**
when it comes from the main session.

```json
{
  "session_id": "…", "cwd": "…", "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Edit",
  "tool_input": { "file_path": "src/models.py", "old_string": "…", "new_string": "…" },
  "agent_type": "developer",        // ← optional; only when a subagent is acting
  "agent_id": "a87a9c…"
}
```

So one shared hook can switch on role **inside the hook** (in Kiro the agent name
came via argv because each agent wired its own hook):

```
agent_type absent      → MAIN SESSION (orchestrator) → code READ-ONLY; Write only openspec/** + .claude/memory/**
agent_type == developer → may Write/Edit/Bash-mutate src/**, tests/**, pyproject (the ONLY code-writing role)
agent_type in {analyst,architect,qa} → Write only openspec/**; Bash read-only (block >, sed -i, uv add, …)
agent_type == onboarder → Write only .claude/context/** (or docs/**)
```

### 3.2 Three defense layers (Kiro had one)

1. **`tools` frontmatter** per subagent — analyst/architect/qa have **no `Edit`** → physically cannot edit code.
2. **`permissions.deny`** in `.claude/settings.json` — e.g. `deny: ["Edit(src/**)","Write(src/**)"]` applies to the **main session too** → closes the exact orchestrator-writes-code hole.
3. **PreToolUse hook** keyed by `agent_type` — the deterministic, fail-closed last line, and the place that grants the `developer` exception.

### 3.3 Guard scripts: ONE source, dual-input

`check-shell-command.py` and `check-write-path.py` reuse ~90% of today's regex logic.
They become **dual-input**: derive the actor from
- **Claude**: `agent_type` on stdin JSON (absent ⇒ main/orchestrator), `tool_input.command` / `tool_input.file_path`; OR
- **Kiro**: agent name from `argv[1]` (as today), `tool_input.command` / `tool_input.file_path` under the Kiro keys.

This avoids forking the security logic — one denylist (redirection, `sed -i`,
`node -e`, `python -c`, package managers, …) serves both platforms. New self-tests:
`main-session-blocked`, `developer-allowed`, `analyst-openspec-only`, **and the
existing Kiro vectors still pass**.

### 3.4 Known Claude-specific risk to design around

GitHub issue #18950: **user-level** `permissions.allow` rules do not reliably inherit
to subagents. Mitigation: put **all** permission rules in the **project**
`.claude/settings.json`, and **do not rely on `allow` to grant developer write —
rely on the hook** (which always receives `agent_type`). `allow`/`deny` are the
backstop, the hook is the source of truth.

---

## 4. Kit-layout refactor (so one source emits both)

Today `kit/` is Kiro-shaped (`agents/*.json`, etc.) and `init.mjs` copies it flat into
`.kiro/`. For dual-target, split the payload into **shared + per-target overlays**:

```
kit/
  shared/                      # platform-neutral — copied for EVERY target
    skills/**                  # SKILL.md (Kiro & Claude share the same format)
    steering/**                # rule content (becomes KB on Kiro, @import on Claude)
    context/*.md               # project/glossary/conventions templates (TODO-tokened)
    ai/openspec-rules.yaml
    pipelines.json, sdlc.config.json
    hooks/                     # the dual-input guard scripts (.py) + helpers
    tools/                     # context-map.mjs, cpp-guard.mjs, … (copied as today)
  targets/
    kiro/                      # overlay → .kiro/
      agents/*.json            # current Kiro agent defs (+ hooks wiring, keyboardShortcut)
    claude/                    # overlay → .claude/
      agents/*.md              # 5 role subagents (frontmatter: name/description/tools/model)
      commands/*.md            # sdlc-full, sdlc-fast, analyst, architect, developer, qa, onboarder
      settings.json            # permissions.deny + hooks wiring (PreToolUse/SubagentStop/SessionStart/UserPromptSubmit)
      CLAUDE.md                # @import steering + context
```

`init.mjs` then, per selected target, copies `shared/**` + `targets/<t>/**` into the
target dir, applying the same token substitution / manifest / prune / preserve logic
it already has — generalised from a hardcoded `.kiro` to a `{ dir, target }` loop.

### Claude target tree (result in a user's project)

```
.claude/
  CLAUDE.md
  settings.json
  agents/{analyst,architect,developer,qa,onboarder}.md
  commands/{sdlc-full,sdlc-fast,analyst,architect,developer,qa,onboarder}.md
  skills/**
  hooks/{check-write-path,check-shell-command}.py
  context/{project,glossary,conventions}.md
  memory/                      # CPP baton (symlinked to ../memory, as on Kiro)
openspec/                      # unchanged, shared backend
```

### Role subagent tool matrix (`.claude/agents/*.md`)

| Subagent | `tools` | Writes |
|---|---|---|
| analyst | Read, Grep, Glob, Bash, Write | proposal/specs → `openspec/**` |
| architect | Read, Grep, Glob, Bash, Write | design.md/specs → `openspec/**` |
| **developer** | Read, Grep, Glob, Bash, **Write, Edit** | **code + tests** (only code-writing role) |
| qa | Read, Grep, Glob, Bash, Write | run tests + report → `openspec/**` |
| onboarder | Read, Grep, Glob, Bash, Write | `.claude/context/**` |

All role subagents **omit `Agent`/`Task`** (no self-spawn) unless we later want
rigor-full to fan out verifiers (subagents may nest up to 5 levels).

---

## 5. New `init` UX — user picks the platform

`init.mjs` integration points (current file hardcodes `.kiro` everywhere — kiroDir,
`walk(KIT_SRC)`, manifest path, symlinks, mapper, "Next steps"):

1. **New flag** `--target kiro|claude|both` (value-taking, parsed like `--title`).
2. **Interactive menu** when TTY and no `--target` (mirrors `create-vite`):
   ```
   ?  Which platform(s) should this kit target?
        ❯ Both (Kiro + Claude Code)        ← default highlight
          Kiro IDE only
          Claude Code only
   ```
   (Implement with the existing `readline/promises` interface — a numbered prompt,
   no new dependency.)
3. **Non-interactive default**: if `--yes`/piped and no `--target`, default to
   **`kiro`** to preserve today's behavior exactly (existing scripted installs keep
   getting `.kiro` and nothing new). *(Open question — see §7.Q1: should the default
   become `both`?)*
4. **Generalise the copy loop**: replace the single `kiroDir` with a per-target list
   `[{ dir: '.kiro', target: 'kiro' }, { dir: '.claude', target: 'claude' }]`, running
   the existing manifest/prune/preserve/token pipeline once per selected target.
   Manifest becomes per-target (`.kiro/.kit-manifest.json`, `.claude/.kit-manifest.json`).
5. **Per-target "Next steps"**: Kiro block (ctrl+N shortcuts) and/or Claude block
   (`/sdlc-full …`, plus the **Reload note**, see §6).
6. **openspec init `--tools`** (verified on OpenSpec 1.3.1): pass per target —
   `kiro` → `--tools kiro`; `claude` → `--tools claude`; `both` → `--tools kiro,claude`.
   **Note:** `--tools claude` itself writes into `.claude/` (`commands/opsx/`,
   `skills/openspec-{propose,apply-change,archive-change,explore}`). These are
   **namespaced** and do **not** collide with the kit's `commands/sdlc-*.md`,
   `agents/*.md`, or `skills/sdlc-orchestration-core`. The manifest-driven prune never
   touches them (they're never in the kit manifest), so the two coexist cleanly —
   same pattern as `--tools kiro` on the Kiro side. Run `openspec init` **after** the
   overlay copy (current order) so it can seed `config.yaml` before the rules-block install.

---

## 6. Operational note carried over: reload after update

Kiro caches agent defs at window load → after `init --force` a **Developer: Reload
Window** (or app restart) is required. The Claude equivalent: changes to
`.claude/agents`, `commands`, `settings.json`, hooks take effect on the **next session
/ `/agents` reload**; an in-flight session won't pick up new hooks. Both `init`
"Next steps" blocks must state the platform's reload step.

---

## 7. Resolved decisions (were open questions)

- **Q1 — non-interactive default target → RESOLVED: keep `kiro`.** Zero behavior change
  for existing scripted users; interactive users still get the menu. Revisit when Claude
  support is proven.
- **Q2 — steering → RESOLVED: hybrid.** `@import` the small always-relevant rules into
  `CLAUDE.md`; **skill-ify the large stack-specific packs** (laravel/nestjs/nextjs) as
  model-invoked skills so they don't inflate every session's base context.
- **Q3 — `openspec init --tools` → RESOLVED & TESTED (OpenSpec 1.3.1).**
  `kiro|claude|both` → `--tools kiro` / `--tools claude` / `--tools kiro,claude`.
  `--tools claude` seeds namespaced `.claude/commands/opsx` + `.claude/skills/openspec-*`
  that coexist with the kit files (see §5.6). No collision, prune-safe.
- **Q4 — version-drift detector → RESOLVED: yes, add it.** A `SessionStart` hook
  (Claude) / `agentSpawn` line (Kiro) compares the installed `.kit-manifest.json`
  `kitVersion` against the kit's current `package.json` version when reachable, and
  prints a one-line warning if they differ ("kit X installed, Y available — re-run init
  + reload"). Catches "forgot to reload / re-init after update". Cheap, read-only,
  fail-silent. Added to the phase plan (§9, phase 3).

---

## 8. What gets better / harder / lost

**Better:** real orchestration (no mis-swap); cleaner guard via `agent_type` + native
`permissions.deny`; nested subagents (per-finding verifiers for rigor-full);
`SubagentStop` knows which role just ran → precise desync detection.

**Harder:** path restriction must go through hooks (frontmatter is tool-NAME only);
subagents inherit the parent's permission mode and cannot override it.

**Lost (with mitigation):** persistent direct chat with one role (Kiro ctrl+1) →
replaced by `/analyst` etc. spawning a fresh subagent with baton context;
`keyboardShortcut`; `welcomeMessage`; KB indexing → replaced by `@import`.

---

## 9. Phased execution plan

1. ✅ **Scaffold + layout refactor — DONE.** `kit/` split into `shared/` + `targets/{kiro,claude}/`
   (121 history-preserving `git mv`s); `init.mjs` generalised to a per-target copy loop;
   `--target kiro|claude|both` flag + interactive menu (default Both on TTY, `kiro` non-TTY);
   per-target manifest + "Next steps"; `openspec init --tools <joined>` once after the loop.
   **Verified byte-for-byte:** a golden-master snapshot of the old `.kiro/` output (136 files,
   sha256) matches the new `--target kiro` output exactly; `--target both` produces an identical
   `.kiro/`. Regression harness lives in scratch (`golden-kiro.sha256`).
2. ✅ **Dual-input guards — DONE.** `check-shell-command.py` + `check-write-path.py` now resolve
   the actor from `argv[1]` (Kiro) ∥ stdin `agent_type` (Claude subagent) ∥ `None` (Claude main
   session = orchestrator), and the write path from `tool_input.path` ∥ `file_path`. Shell guard
   maps actor→class (developer=allow / orchestrator=branch-create-only / restricted=read-only).
   Write guard reads the Kiro agent JSON when present (source of truth) else a built-in Claude
   role policy. Embedded `--self-test` suites pass **24/24 each**, covering Kiro vectors
   (unchanged orchestrator/restricted behavior) + Claude vectors (main-session-blocked /
   developer-allowed / analyst-openspec-only). Combined regression: full `--target kiro` init
   differs from golden in **exactly these 2 files** — nothing else moved.
   *Deviation from §4:* the guards stay at `agents/scripts/*.py` in **both** targets (not
   `.claude/hooks/`) so one shared copy keeps the existing Kiro paths byte-identical; Claude's
   `settings.json` (Phase 3) will reference `.claude/agents/scripts/…`.
3. **Claude role subagents** `.claude/agents/*.md` + `settings.json` deny/allow
   (the native permission layer). **+ version-drift detector** (Q4): `SessionStart`
   hook (Claude) / `agentSpawn` (Kiro) warning when manifest `kitVersion` ≠ available.
4. **Orchestrator commands** `/sdlc-full` + `/sdlc-fast`: spawn role subagents,
   gate-in-main-session, baton read/write. Core mechanics shared via
   `skills/sdlc-orchestration-core/` (keep the INVARIANT block).
5. **Role commands** `/analyst …/onboarder` + skills/stack-pack path fixes + CLAUDE.md
   `@import`s.
6. **E2E verify** on a clone of issues-sum: run `/sdlc-full feature X`; confirm the main
   session is blocked from editing code, only the developer subagent can, and baton +
   openspec stay in sync.

---

_Last updated as a plan; supersede sections as they are implemented._
