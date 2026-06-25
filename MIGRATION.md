# MIGRATION — Kiro → Claude Code (dual-target)

> Status: **IMPLEMENTED** (Phases 1–10 ✅ on `feat/claude-target`; Phase 7 = Claude validator +
> `@import` bugfix; Phase 8 = real-project rollout hardening; Phase 9 = orchestrator-as-agent so the
> default session is unrestricted; Phase 10 = orchestrator write-fence so it delegates phases instead
> of doing them inline). One kit source emits `.kiro/`
> and/or `.claude/`; the user picks at `init` time (`--target kiro|claude|both`).
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
2. **`permissions.deny`** in `.claude/settings.json` — a coarse backstop. **Implementation deviation
   (see §9.3):** we do **NOT** blanket-deny `Edit(src/**)`/`Write(src/**)` here, because
   `permissions.deny` is **not role-aware** — a global src-deny would also block the *developer
   subagent*, which legitimately must write code. The role-based "main session can't write code"
   rule is enforced by the `agent_type`-keyed hook (layer 3), the only layer that can distinguish the
   developer from the orchestrator. `deny` instead protects universally-unsafe targets (the kit's own
   `.claude/settings.json`, `agents/scripts/**`, `agents/**`, `commands/**`, and the living spec
   `openspec/specs/**` — written only by `openspec archive`).
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
3. ✅ **Claude role subagents + settings + drift detector — DONE.**
   - `kit/targets/claude/agents/{analyst,architect,developer,qa,onboarder}.md` — Claude-native
     subagents (frontmatter `name`/`description`/`tools`/`model`; opus for analyst/architect/onboarder,
     sonnet for developer/qa). Ported faithfully from the Kiro prompts (hard rules, ID formats,
     thresholds, gate criteria preserved) but adapted to the **one-shot** model: a subagent cannot
     interview the user mid-run, so it records `[UNCLEAR]`/`[ASSUMED]` + returns a structured
     question/assumption list for the orchestrator to resolve at the gate. Tool matrix per §4 (only
     **developer** has `Edit`); none carry `Task`/`Agent`. Detailed methodology stays in the shared
     `.claude/skills/`.
   - `kit/targets/claude/settings.json` — `permissions.deny`/`allow` + hooks: PreToolUse `Bash` →
     `check-shell-command.py`, PreToolUse `Write|Edit|MultiEdit` → `check-write-path.py`, SessionStart
     → `check-kit-version.py` + `agent-spawn-context.py`, UserPromptSubmit (ticket auto-context), Stop
     (non-spec-change desync flag). Hooks reference `.claude/agents/scripts/…`.
   - `kit/targets/claude/CLAUDE.md` — `@import`s steering (security/sdlc-workflow/rules-registry) +
     the 6 context files; stack packs stay model-invoked skills (Q2).
   - **Version-drift detector** (Q4): `kit/shared/agents/scripts/check-kit-version.py` (shared) —
     compares the installed manifest `kitVersion` to the available version (env
     `KIRO_SDLC_KIT_VERSION` / `KIRO_SDLC_KIT_HOME/package.json`); warns on drift, **silent when the
     available version can't be resolved**, always exit 0. Wired as a Claude SessionStart hook.
   - *Settings deviation (see §3.2):* code-write role enforcement is the hook, not a src-`deny`
     (deny is not role-aware and would block the developer subagent).
4. ✅ **Orchestrator commands — DONE.** `kit/targets/claude/commands/{sdlc-full,sdlc-fast}.md` —
   slash commands that run the orchestrator **in the main session** (`$ARGUMENTS`, `argument-hint`).
   They defer all machinery to the shared `sdlc-orchestration-core` skill (kept byte-identical for the
   Kiro golden) and add a **Claude translation layer**: "route to {agent}" ⇒ spawn that role via the
   Task tool with the baton injected; gates run in-session and pause for the user; `.kiro/tools/*` ⇒
   `.claude/tools/*`. The INVARIANT block (orchestrator never writes code) is restated in each.
   - **Tooling:** the deterministic guards (`pipeline-guard.mjs`, `cpp-guard.mjs`, `context-check.mjs`)
     are now **platform-aware** — they resolve `.kiro` vs `.claude` from their own install path
     (`import.meta.url`), so one source works under both `<target>/tools/`. `init.mjs` copies the
     neutral subset into `.claude/tools/` (context-map/apply-stack stay Kiro-only — they wire Kiro
     agent JSON). Kiro runtime behavior unchanged (defaults to `.kiro`).
   - **Verified:** `--target both` produces a complete `.claude/` (5 agents, 2 commands, settings,
     CLAUDE.md, 3 tools, guard scripts, 30 skills incl. namespaced openspec-* coexisting); all
     frontmatter parses; no unsubstituted tokens; the guards load the correct `pipelines.json` under
     both hosts at runtime; guard self-tests 27/27 + 24/24.

   _(Phase 5–6 below complete the remaining role commands, stack-pack path fix, and E2E verify.)_
5. ✅ **Role commands + stack-pack path fix — DONE.**
   - `kit/targets/claude/commands/{analyst,architect,developer,qa,onboarder}.md` — direct-invocation
     (D3) slash commands. Each is thin: resolve the active change's CPP baton, **spawn that one role
     via the Task tool** (`subagent_type`) with `priority_reading`/`watch_items` injected, then relay
     the subagent's blocking questions/assumptions for the user. Each restates the INVARIANT
     (`/developer` clarifies that **only the spawned developer subagent** writes code — the main
     session still cannot) and states plainly that a role command runs ONE phase and does **not**
     gate/advance `_state.json` — gating stays with `/sdlc-full … approve`. `init`'s overlay `walk()`
     picks them up automatically (no init change needed) → `--target both` now emits **7** commands.
   - **Stack-pack path fix:** stack packs ship under `<platform>/stacks/<stack>/` but only Kiro had
     an apply path (`apply-stack.mjs` merged `context-map.json` + re-wired). Made `apply-stack.mjs`
     **platform-aware** (same `import.meta.url` → `PLATFORM_DIR` pattern as the guards): on Claude it
     seeds `.claude/context/{stack,conventions}.md` and copies the pack's skills into
     `.claude/skills/` (where Claude auto-discovers them as model-invoked skills), and **skips** the
     Kiro-only `context-map.json` merge + `applyContextMap` re-wire (loaded via dynamic `import` so
     `context-map.mjs`, which isn't copied to Claude, is never required there). Added `apply-stack.mjs`
     to the Claude tool list in `init.mjs`. `CLAUDE.md` rewritten to describe the real path
     (`.claude/stacks/` → `apply-stack` → `.claude/skills/`) instead of the previously-inaccurate
     "already under `.claude/skills/`", and its entry-points now list `/onboarder` + the 5 role commands.
   - **Verified:** `--target both` emits 7 commands + `apply-stack.mjs` in `.claude/tools/` + the 3
     stacks; no unsubstituted tokens; `node --check` clean. `apply-stack laravel` on a Claude install
     installs 5 skills into `.claude/skills/`, seeds context, and creates **no** `context-map.json`
     (correct); the same tool on a Kiro install still merges `context-map.json` + re-wires all agents
     (regression-clean).
6. ✅ **E2E verify on an issues-sum clone — DONE (security + tooling).** Installed `--target claude`
   into a clone of `~/issues-sum` (real Python repo) — clean install: 5 agents, 7 commands, settings,
   CLAUDE.md, 4 tools, 3 stacks, openspec symlink resolving. Drove the **security invariant E2E** by
   feeding the installed hooks the exact PreToolUse JSON Claude Code emits per actor — **14/14 pass**:
   main-session Edit `src/**` → BLOCK; **developer** Edit `src/**` → ALLOW; analyst/qa Write `src/**`
   → BLOCK; analyst Write `openspec/**` / qa Write `tests/**` / onboarder Write `.claude/context/**`
   → ALLOW; main-session `sed -i`/`git commit` → BLOCK but pipeline-isolation `git checkout -b` →
   ALLOW; developer `pytest`/`uv add` → ALLOW; analyst `uv add` → BLOCK, `grep -r` → ALLOW. This
   proves the **only the developer writes code** invariant deterministically across all five roles +
   the orchestrator. `pipeline-guard.mjs` in the clone loads `pipelines.json` and reaches the
   `openspec/` symlink (reports "no active change", as expected pre-`/sdlc-full`). Guard self-tests
   27/27 + 24/24.
   - _Not self-driven (a live-usage step for the user):_ a full interactive `/sdlc-full feature X`
     run from start to S6 — it spawns subagents and pauses for human approval at each gate, and would
     write real code into the clone via the developer subagent. The deterministic security + tooling
     E2E above is the faithful scoped verification; the end-to-end pipeline drive should be exercised
     in a real session.
7. ✅ **Post-migration hardening — DONE (Claude validator + `@import` bugfix).** Review of the
   Kiro↔Claude differences surfaced that the migration had **no structural validator for the Claude
   target** — `doctor.mjs` only validates Kiro agent JSON + `resources[]` + the context map, none of
   which exist on Claude, and `context-check.mjs` covers only context *completeness*. Closing that gap
   with `doctor-claude.mjs` immediately exposed a real shipping bug:
   - **🐞 `CLAUDE.md` `@import` paths were broken.** The file installs to `.claude/CLAUDE.md` (Claude
     Code auto-loads either `./CLAUDE.md` or `./.claude/CLAUDE.md` — confirmed against
     code.claude.com/docs/en/memory), but its imports used the `@.claude/steering/…` / `@.claude/context/…`
     prefix. Claude resolves `@imports` **relative to the importing file's own directory**, so from
     `.claude/CLAUDE.md` those resolved to the non-existent `.claude/.claude/…` — silently dropping
     **all** steering rules + the entire context contract at runtime. Phase 6's E2E never exercised
     `@import` resolution, so it slipped through. Fixed the source to `@steering/…` / `@context/…`.
   - **`doctor-claude.mjs`** (added to the Claude tool list in `init.mjs`) validates: required dirs +
     `CLAUDE.md`/`settings.json`; **every `@import` resolves relative to the file's own dir** (the
     check that would have caught the bug); all 7 commands + 5 subagents present; subagent frontmatter
     valid and the **"only `developer` carries the `Edit` tool" security invariant** (regression guard
     for defense-layer 1); `settings.json` valid JSON with hook scripts + the 4 tools installed; the
     `sdlc-orchestration-core` skill present; openspec CLI + workspace + symlinks; context completeness.
   - **Verified:** fresh `--target claude` install → `doctor-claude` reports HEALTHY (only the expected
     pre-onboarder "context not filled" WARN). Negative test: re-introducing the `@.claude/` prefix and
     granting `analyst` the `Edit` tool both FAIL as designed (`@import does not resolve`; `SECURITY:
     analyst subagent carries Edit`).
8. ✅ **Real-project rollout hardening — DONE.** Installing into 5 real repos (issues-sum, colemark-dh,
   portal, zellij-claude-sync, image-to-report) surfaced three more fixes:
   - **`{{PLATFORM_DIR}}` token.** Shared skills hardcoded `.kiro/…` paths that break on a claude-only
     install — two **executable** (`node .kiro/tools/pipeline-guard.mjs`, the mandatory gate guard; and
     `gen_testcases_xlsx.py`, the QA xlsx export) plus ~15 advisory refs. They only ever worked because
     test installs also had `.kiro/`. Added a per-platform `{{PLATFORM_DIR}}` token that `init`
     substitutes to `.kiro`/`.claude` per target; switched all shared `.md`/`.json` refs to it (guard
     `.py` comments/self-test vectors keep literal `.kiro/`). The now-redundant "translate `.kiro/` ⇒
     `.claude/`" notes in the Claude commands were removed.
   - **`settings.json` allow-list widened.** The shipped list was read-only-tight, so `/sdlc-full`
     prompted on nearly every step (Task spawn, baton write, branch create). Added `Task`,
     `Write`/`Edit(openspec/** + memory/**)`, and branch-create git to `allow` — permission prompts
     aren't the security boundary (the hooks are); code writes (`src/**`) stay un-allowlisted (prompt +
     hook-enforced) and `deny(openspec/specs/**)` still wins.
   - **`doctor-claude` CLAUDE.md preference.** On a repo with its own root `CLAUDE.md` (no `@import`s),
     the doctor validated that instead of the kit's `.claude/CLAUDE.md` and falsely flagged missing
     `@import`s. Now it validates the kit-managed `.claude/CLAUDE.md` first.
   - **Write-guard host-precedence bug.** On a dual-target project the guard preferred
     `.kiro/agents/<role>.json` (paths all `.kiro/…`), so a Claude-session `onboarder` could write
     `.kiro/context/` but was BLOCKED from `.claude/context/`. Fixed: the policy source now follows
     the **host** (detected from the hook script's own install path) — Claude host → built-in policy,
     Kiro host → the agent JSON. The self-test (which had pinned the source per vector, hiding the
     bug) now exercises the real `decide()`.
   - **Context unified into a shared root `./context/`.** The dual-context duplication was the root of
     the sync/port pain, so context joined `openspec/` + `memory/` as a project-root workspace:
     `init` scaffolds `./context/` once and symlinks `.kiro/context` + `.claude/context` → `../context`
     (single + both targets). `scaffoldRootContext()` migrates an existing install's filled
     per-platform context into `./context` (preserved) before the dir becomes a symlink, so
     `init --force` upgrades cleanly. All 5 repos migrated: filled context (issues-sum, portal)
     survived as `context-check` COMPLETE; everything resolves through the symlink (`@import`,
     `doctor`, `context-check`, `apply-stack`, `applyContextMap`).
   - **Per-project notes:** issues-sum context was **ported** from its existing filled `.kiro/context/`
     (no re-onboard needed); colemark-dh's own `.claude/settings.json` was **merged** (kept its
     `enabledPlugins`); installs are additive (`.kiro/` untouched where present, `openspec/`+`memory/`
     never touched). All 5 → `doctor-claude` HEALTHY.
9. ✅ **Orchestrator-as-agent — DONE (default session unrestricted).** A user reported that the plain
   default Claude session in a kit-installed project was blocked from normal read-only work (e.g.
   `curl … | python3 -c "…print…"`). Root cause: the orchestrator WAS the bare main session (driven by
   the `/sdlc-full` slash command), so the guards had to hold **every** main session read-only — they
   couldn't distinguish "orchestrating" from "the user doing ad-hoc work" (both have no `agent_type`).
   - **Fix:** the orchestrator now runs as a **named top-level agent** — `claude --agent sdlc-full` /
     `sdlc-fast` — which carries `agent_type=sdlc-full|sdlc-fast` (empirically confirmed: `--agent`
     surfaces `agent_type` to PreToolUse hooks). Both guards pick policy by actor: orchestrator agents
     → read-only (+ branch-create); role agents → role policy; `developer` → code; **bare main session
     (no `agent_type`) on Claude → DEFAULT, unrestricted.** On Kiro a missing actor still fails closed.
   - **Files:** new `.claude/agents/{sdlc-full,sdlc-fast}.md` (orchestration prompt; `tools` without
     `Edit`); `/sdlc-full` `/sdlc-fast` slash commands → thin launchers; both guard scripts +
     `CLAUDE.md` + `doctor-claude` (now 7 subagents) updated. Self-tests 31/31 + 27/27.
   - **Verified + deployed to all 5 repos:** `doctor-claude` HEALTHY (7 agents); E2E on the installed
     hooks — default session runs `python3 -c`/`rm`/writes; the `sdlc-full` agent is read-only
     (blocks `src/**` writes, allows baton + branch-create); `developer` writes code.
   - **Trade-off (accepted):** pipeline safety is now "on inside the sdlc agent," not always-on for
     every session — the deliberate price of an unrestricted default workspace.

10. ✅ **Orchestrator write-fence — DONE (delegates phases, can't do them inline).** A user observed
    that on `continue` the orchestrator "became the architect" and produced `design.md` itself instead
    of routing to the architect — and **no guard stopped it**. Root cause: the guards enforced only
    "developer writes code (`src/**`)"; all non-code artifacts live under `openspec/**` and the
    orchestrator's write policy was the whole `openspec/**`, so it could author any deliverable. The
    "you don't design yourself" rule was soft, `continue` didn't hard-block, and the gate's
    `"Generated by: architect"` provenance is self-declared (impersonation passes it).
    - **Fix (deterministic guard):** every file the orchestrator legitimately writes is
      underscore-prefixed (`_state.json`, `_progress.md`, `_handoff.md`, `_decisions.jsonl`,
      `_glossary.md`, `openspec/_cross-spec-context.md`); no deliverable is. So the orchestrator
      (`sdlc-full`/`sdlc-fast`) write allow-list was narrowed to those `_`-files + memory — Claude
      (`_ORCH` in `check-write-path.py`) and Kiro (`sdlc-full.json`/`sdlc-fast.json` allowedPaths).
      Writing `proposal.md`/`design.md`/`tasks.md`/`specs/**`/`*-report.md` now BLOCKS (exit 2),
      forcing delegation. **Prompt** hardened (`sdlc-orchestration-core` INVARIANT 1 + `continue`/route
      now say spawn-the-role / `/agent swap`, never produce the deliverable; `"Generated by"` must be
      the real author).
    - **Verified + deployed to all 5 repos:** self-tests 31/31 + 31/31; E2E both hosts —
      `sdlc-full`→`design.md` BLOCK, →`_state.json`/`_cross-spec-context.md` ALLOW, `architect`→
      `design.md` ALLOW; portal confirmed; `doctor-claude` HEALTHY across all 5.

---

_Last updated as a plan; supersede sections as they are implemented._
