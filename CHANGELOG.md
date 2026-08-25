# Changelog

All notable changes to **kiro-sdlc-kit** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

**Theme — dual-target (Kiro + Claude Code) from one source, on a root-only shared workspace.**
The kit emits both `.kiro/` and `.claude/` from `kit/shared/**` + `kit/targets/<platform>/**`; the
project workspace/config (`context/`, `docs/`, `memory/`, `openspec/`, `sdlc.config.json`,
`pipelines.json`) lives once at the project root — no per-platform copy, no symlink — referenced
root-relative by both. The framework (process, skills, gates, security) is identical on both.

### Changed

- **Per-spawn context is now role-scoped on Claude.** `.claude/CLAUDE.md` no longer `@import`s
  `context/{stack,conventions,glossary}.md` — that block was prepended to EVERY spawn (orchestrator
  and each role, ≈12 KB / ~3k tokens) while every role's Inputs already told it to Read the same
  files, so it was paid twice. It is replaced by a role × file table; each role prompt's Inputs now
  lists only its own files (analyst: project+glossary; architect: stack+architecture+conventions;
  developer: stack+conventions+architecture; qa: stack+conventions; `legacy-ref` / `project` /
  `steering/sdlc-workflow` on demand). At `scope=tiny` every role reads only the CPP baton +
  `priority_reading` (+ `stack.md` for dev/qa) — added to `sdlc-orchestration-core` §Scope, and the
  SessionStart hook prints a one-line **Context Budget** for the active scope. The same hook now
  shows the `memory/<role>/_index.md` digest (last 3 lines) instead of the retired flat
  `memory/<role>.md`. `doctor-claude` no longer warns on zero `@import`s. Kiro is unchanged — its
  `context-map.json` was already per-role and RAG-indexed.
- **Every Claude subagent now carries `Edit`** (analyst, architect, qa, intake, onboarder,
  context-refresh, sdlc-full, sdlc-fast — previously developer-only). The old "only developer has
  Edit" invariant guarded nothing: `Edit` targets the same `file_path` as `Write` and fires the same
  `PreToolUse(Write|Edit|MultiEdit)` → `check-write-path.py` hook, which is the role-aware layer that
  actually fences `src/**`. Without it, an architect fixing one missing AC id in `design.md` had to
  rewrite the entire file via `Write` (the shell guard blocks `sed -i`/heredocs for non-developer
  roles) — token-expensive and clobber-prone. `doctor-claude.mjs` now requires `tools` on every
  subagent and `Edit` on developer; a non-developer role *lacking* Edit is a warning. Kiro is
  unaffected (its `write` tool already covers in-place replace).

### Added

- **`init --worktree` — deterministic setup for a linked git worktree.** Everything the kit owns is
  gitignored, so `git worktree add` brings across *none* of it — no agents, no tools, no config, no
  `context/`. The only guidance was a prose line in `SKILL.md` telling the orchestrator to "`mkdir` or
  symlink" some of it, re-improvised by an LLM per worktree; one project was found with five worktrees
  in five different states, two of them missing `openspec/config.yaml` (and therefore the kit's own
  artifact rules) entirely. The flag replaces that with one idempotent command that splits the
  workspace by what breaks when it exists twice: `context/` + `memory/` are **symlinked** to the main
  checkout (hand-curated, not regenerable, not git-tracked — a second copy diverges with no merge to
  reconcile it); `.kiro/`, `.claude/`, `pipelines.json` are copied fresh (deterministic); and
  `sdlc.config.json` + `openspec/config.yaml` are **seeded from main** so the parts you own survive —
  notably `paths.{code_roots,test_roots}`, which the write-fence reads and a fresh scaffold would
  blank. `openspec/changes/**` is deliberately untouched: the baton is one pipeline's state on one
  branch. Never destructive — real content already sitting where a symlink belongs is reported with
  `!` and left alone; `.gitignore` is not written (it belongs to the branch). Both doctors now flag a
  worktree whose `context/`/`memory/` is a private copy instead of a link, which is the failure that
  hides — it reads fine, and only later does someone notice a branch's learnings went nowhere.
- **`baton-compact.mjs` — the missing compaction step for the CPP baton.** Every writer's instruction
  was "append" and nothing ever shrank the result, so the baton — re-read IN FULL by every role on
  every spawn — had grown to 34–155 KB per spawn across 8 live changes (≈9–39k tokens, i.e. **2–6× the
  entire agent prompt + steering**). The tool does only what is mechanically safe: archives
  non-canonical `_state.json` keys, folds old `phase_history` into one digest line, shortens over-cap
  `decision`/`reasoning`/`rejected`/`alternatives` fields behind a `full` pointer, and drops
  `[SUPERSEDED]` glossary rows whose replacement is already present. Everything removed lands in
  `<CHANGE_DIR>/_archive/` (inside the baton write-fence, read by nothing). Dry-run by default;
  `--apply` writes, `--all` sweeps every active change, `--handoff` also archives handoff sections past
  the 5-section contract. Measured −34…−38% on the two worst live changes without touching a single
  judgement call. The orchestrator runs it after each `approve`.
- **`--global-ignore` — personal-layer ignore (recommended for teams).** Maintains a marker-bounded
  kit block in the MACHINE-level git ignore file (`core.excludesFile`, default `~/.config/git/ignore`)
  instead of any repo's committed `.gitignore`: one run covers every repo/branch/worktree/future clone
  on the machine, is never committed, and imposes nothing on teammates (ignore rules never affect
  already-tracked files). Includes the per-repo patterns plus an **OpenSpec state allowlist** — all of
  `openspec/changes/<change>/` ignored, team deliverables re-opened (proposal/design/tasks/openapi/
  stride/specs/release/QA workbooks/.openspec.yaml), `changes/archive/**` kept tracked — so the CPP
  baton and QA scratch (the cross-branch merge-conflict magnets users reported) never reach git while
  reviewed documents keep flowing. New pipeline state files are local automatically. See GUIDE.md
  §`--global-ignore` for the 3-layer model + the selective-untrack path for repos that already track
  kit machinery.
- **Claude Code target (`.claude/`).** Orchestrator runs as a dedicated `sdlc-full`/`sdlc-fast` agent
  that spawns one-shot role subagents; context via `@import`, skills auto-discovered. `--target
  kiro|claude|both` on `init` (per-target `.kit-manifest.json`; per-target `--check`/`--force` plans).
- **Role-aware security on Claude.** An `agent_type`-keyed PreToolUse hook enforces "only the developer
  writes code"; a bare main session (no `agent_type`) is your unrestricted workspace. Fail-closed.
- **Per-project code/test roots.** `sdlc.config.json.paths.{code_roots,test_roots}` extend the
  developer/qa write-fence (preserved across `--force`; interior-`**` globs supported).
- **`state-set.mjs` + `state-schema.mjs`.** Surgical, schema-validated `_state.json` writes; drift is
  rejected at write time and at `pipeline-guard` STEP 0 (was read-only/reactive — slipped through on
  terminal gates).
- **Role-memory write-back wired and gate-enforced.** Each role appends cross-spec lessons to
  `memory/<role>.md` at phase end and records the decision in `_state.json.memory_writeback.<role>`
  (`appended`/`nothing-reusable`); `cpp-guard` blocks the gate until set, and `sprint-retro` harvests at
  S6 as the safety net. Previously the read pointers existed but nothing ever wrote back.
- **Subagents granted their MCP tools.** intake/analyst/architect/qa frontmatter + `settings.json`
  allow `mcp__redmine` / `mcp__figma-legacy` / `mcp__bookstack` (Kiro `@figma` → `@figma-legacy`);
  fixes "No such tool available" when a subagent calls Redmine/Figma/BookStack.
- **`spike` + `tech-debt` pipeline types and a `fastapi` stack preset.** `spike` (S1+S2 → decision-doc,
  no code) and `tech-debt` (S3→S6, zero-behavior-change); `apply-stack fastapi` seeds context + skills.
- **Optional kit `.gitignore` block.** `init` ignores only kit-regenerated paths (`.claude/`, `.kiro/`,
  `/sdlc.config.json`, `/pipelines.json`); marker-bounded, refreshed in place, deletable to opt back in.
- **Intake plans the UI.** When a ticket has UI, intake writes one
  `docs/extra-docs/<ticket>-<slug>/ui/<screen>.md` per screen; the developer reads them at S4. New
  golden templates (`intake-example.md`, `ui-screen-example.md`).
- **Preservation net in the write hook.** Snapshots `context/**`/`memory/**` to `.snapshots/` (last 5)
  before any overwrite, and append-guards `memory/*.md` (a write dropping a `## ` section is blocked).
- **`ai/` reachable on Claude** — `developer`/`qa` point to `.claude/ai/sonar-policy.md` (+ `sonar-rules.md`).
- **A `scope` axis (`tiny`/`standard`) scales HOW MUCH a phase writes, independent of `type`/`rigor`.**
  `type` still picks which phases run and `rigor` how hard the gates squeeze; `scope=tiny` (set by
  whichever role first has real size evidence — analyst at S2, or developer at S4 for bugfix/hotfix)
  lets architect condense design.md sections the change doesn't touch to one line and skip an ADR's
  options table when only one approach is genuinely reasonable, and lets developer run
  affected-tests-only at intermediate checkpoints (the final checkpoint's depth — coverage, always —
  never shrinks; see `test_scope` below for its width). Default `standard` when unset; architect may
  escalate `tiny`→`standard`, never the reverse. Targets design.md ballooning to hundreds of lines and
  full test-suite reruns for a handful of changed lines.
- **A `test_scope` axis (`module`/`full`) controls WIDTH of the developer S4 final checkpoint AND the
  QA S5 independent re-run — both now read the same value instead of each defaulting to "the full test
  suite."** Resolved once at kickoff (runtime flag → `sdlc.config.json.tests.final_scope` → derive from
  `rigor`: full→full, lite→module) and persisted to `_state.json.test_scope`; validated by
  `state-schema.mjs`. `module` restricts the test AND lint/static-analysis commands to the
  module/directory containing every touched file (siblings included), instead of the whole app/repo.
  Fixes a real case: a 1-file, 25-AC Laravel change burned ~500k tokens at QA because `qa.md` said
  "re-run the full test suite yourself" with no scope awareness — QA re-ran the entire module's test
  suite AND a module-wide static-analysis pass on top of the developer's already-scoped final
  checkpoint, in addition to (not instead of) the correctly-scoped feature test. Neither role
  previously consumed `rigor` for test breadth — only for gate convergence and test-case format.
- **`memory/<role>/_index.md` — a one-line-per-change digest.** Every role-memory write-back now also
  appends one line to a per-role index; roles read the index FIRST (cheap, flat cost regardless of how
  much project history has accumulated) and open individual `memory/<role>/{change-name}.md` files
  only for entries that look relevant, instead of reading every past-change file on every run. `init`
  backfills the index from existing fragment files on upgrade (idempotent — safe to re-run). The
  write-fence append-guards `_index.md` the same way it already append-guards the fragment files
  (blocks a write that drops an existing digest line).
- **`scope=tiny` now applies to EVERY artifact, not just design.md.** Numeric floors that otherwise
  force padding — analyst's ≥10 edge cases and ≥3 happy/error ACs per story (`edge-case-enumerator`,
  `spec-auditor` C4, `openspec-rules.yaml`), architect's ≥2 tasks.md checkpoints — relax to ≥3, ≥1+1,
  and 1 (final only) respectively at `scope=tiny`; unset/`standard` keeps the original floors. A new
  universal rule in `sdlc-orchestration-core` SKILL.md states every golden example under
  `agents/examples/` shows required STRUCTURE, never a length target, and every role prompt now says
  so next to its own examples — a `scope=tiny` change's proposal.md/design.md/tasks.md/
  dev-test-report.md/qa-report.md should each be a fraction of the worked example's length while still
  hitting every required section.
- **CPP baton writes are batched, not per-decision** — the Kiro role prompts (analyst/architect/
  developer/qa) each had an "APPEND-AS-YOU-GO" rule instructing an immediate `_decisions.jsonl` write
  the moment any single AC/ADR/deviation/bug was finalized — a 25-decision phase meant 25 separate
  Write calls. Real cost: this is the literal Kiro-side mechanism behind a QA run that logged its bugs
  one Write at a time. Now each role accumulates decisions in-session and writes them in ONE batched
  pass (developer: per checkpoint segment, matching its existing multi-run structure; the other three:
  once per phase) — the CPP-completeness gate and stop-hook reminder already catch a genuinely missed
  entry, so immediate per-decision writes bought no real safety, only tool-call overhead. Claude target
  never had the AS-YOU-GO instruction, but batching wasn't explicit there either — both targets now
  explicitly say "accumulate, one batched Write" in all 4 role prompts, plus a terse-fields reminder
  (`decision`/`reasoning`: keyword/fragment, not full prose) right where each writes `_decisions.jsonl`.
  Also added a universal style rule in `sdlc-orchestration-core` SKILL.md restating this for the
  orchestrator's own awareness: CPP baton text fields are keyword/telegraphic by default at every
  scope — same information, fewer words — not just at `scope=tiny`.
- **`init --gitignore-only`** — refreshes JUST the kit-owned `.gitignore` block and exits, without
  `--force`'s full ~128-file `.claude`/`.kiro` recopy. Rolling out a new `GITIGNORE_PATTERNS` entry
  (e.g. the `memory/*/_index.md` / `/context/` additions above) previously meant either a full
  `--force` re-init — unrelated blast radius for what's a one-line pattern change — or hand-editing
  every project's `.gitignore`. Errors if combined with `--no-gitignore` (contradictory).

### Changed

- **Baton pass — the CPP baton is now bounded, so a spawn stops re-paying for what earlier phases
  wrote.** The prompt/context work above cut the fixed per-spawn cost to 24 KB; measuring the *other*
  half showed the baton had quietly become the bigger number (34–155 KB per spawn on live changes).
  None of it was agent misbehaviour — each cause was designed in:
  - **`_state.json` had no key allowlist**, so roles used it as a document store: 4.8–42 KB per file of
    keys no guard and no prompt reads (`staging_evidence` 10.7 KB, `regression` 6.6 KB, `gate_audit`
    5.5 KB, `s3_outputs`, `resolved_at_s3`, `rigor_downgrade`, `s4_checkpoint_2`, …). `state-schema.mjs`
    now defines `CANONICAL_KEYS` + `CAPS` and `auditState()`; **`state-set` refuses a write that
    introduces a non-canonical key or busts a cap**, while pre-existing drift only warns — so a change
    already mid-flight never deadlocks on state an older kit let through. `pipeline-guard` STEP 0 prints
    the same audit at every status/gate check.
  - **`terminology` and `active_concerns` were duplicates the kit itself asked for** — `terminology`
    restated `_glossary.md`, `active_concerns` restated `next_action.watch_items`, and both appeared in
    8/8 live changes because the templates and the analyst prompt prescribed them. Removed from the
    seed state, the template and every prompt.
  - **`_decisions.jsonl` was used for prose** (939 B average per line, 2.6 KB worst — a full root-cause
    write-up with before/after code). Now capped: `decision` ≤240 chars, `reasoning`/`rejected` ≤120,
    with the analysis pushed to the phase report that is read ONCE at its gate. The analyst's "log every
    `[CONFIRMED]` AC" rule — which alone produced 21–28 `requirement` entries per change, a second copy
    of spec deltas every role already reads — is now "log what the spec cannot show".
  - **`_handoff.md` was defined as append**, so it became an audit log (§1-5, then §6, §6a-6e, §7 across
    fix rounds). It is now explicitly REPLACE, exactly 5 sections, ≤6 KB, in all four role prompts and
    the template: a handoff carries what the next phase needs; git carries the history.
  - **Superseded glossary rows were kept beside their replacements** (append-only, "never delete a
    row"), so a term's dead meaning was paid for on every remaining spawn. Terms are now edited in
    place, definitions are one line ≤220 chars, and a row must earn its place by not being derivable
    from the spec.
  - **`cpp-guard` reports baton bloat at every gate** (`auditBaton()` — over-cap decision entries,
    handoff/glossary/progress size, superseded markers, whole-baton total in KB and tokens), advisory
    so it never blocks a gate, printed on pass and fail alike.
- **Context-loading pass — a Kiro role spawn now pays 24 KB of fixed context instead of 32 KB (−25%),
  and retrieval stopped serving archived specs as if they were current.** Five independent fixes; the
  first is a correctness fix that happens to also be the cheapest.
  - **`openspec/` is no longer indexed whole.** Every agent had `file://./openspec` as a
    `knowledgeBase` (`indexType: best`) — 3.7 MB on a mature repo, of which 1.2 MB was
    `changes/archive/`. Retrieval could therefore surface a chunk from a **superseded** change and it
    would read as current spec. The kb is now scoped to `openspec/specs` (the living capability specs,
    `autoUpdate: true`) + `openspec/config.yaml`; `openspec/changes/**` is never indexed — a role reads
    the ACTIVE change by explicit path, which every role prompt already instructs. `context-map.mjs`
    gained prefix-aware shared-root resolution (`openspec/**`, `context/**`) to support this.
  - **`.kiro/steering` was double-counted** — auto-included by Kiro *and* wired as a knowledgeBase in
    every agent.json. Removed from `always.knowledgeBase`.
  - **Steering split by `inclusion:`** (previously all 5 files were always-included, 14.2 KB on every
    spawn → now 8.1 KB). `sdlc-workflow.md` + `rules-registry.md` stay `always`; `security.md` and
    `12-rule.md` become `fileMatch` on source extensions (they bind code, so they load for dev/QA, not
    on an analyst/architect/orchestrator spawn); `commit-policy.md` becomes `manual` (only the
    developer commits, only at S4-end/S6). Every role prompt that relied on always-inclusion now names
    the file by path at the point it's needed, so nothing became unreachable.
  - **`12-rule.md` Rule 6 replaced.** It mandated "per-task: 4,000 tokens, per-session: 30,000" — a
    budget no real phase can meet, so the rule was either ignored or caused silent truncation. Now it
    says what was actually meant: scope reads to the files the task touches plus direct callers, don't
    sweep a directory "for context", and justify a wide sweep before doing one.
  - **QA's minimum-effort floor now scales with `rigor`/`scope`.** It was absolute — *read ALL test
    files, ≥3 risky sources, <15 min on ≥10 ACs is a red flag* — and applied identically to a 20-line
    `hotfix` at `rigor=lite`/`scope=tiny`. At `lite`/`tiny` it is now diff-scoped (test files of the
    modified module, files in the diff + direct callers, no time floor). AC-ID mapping against the spec
    deltas never relaxes, and the table is explicitly a floor, not a quota: a bug signal means read
    wider and say why.
  - **S4-FIX + S6 procedures moved out of the always-loaded developer prompt** into a new shared
    `release-and-fix` skill (3.6 KB, loaded only when the trigger is `/s4-fix` or `/s6`). A plain S4
    build run — the common case — stopped paying for them. Both targets point at it as Step 0 for those
    triggers. Kiro `developer.md` 18.3 KB → 16.2 KB; Claude `developer.md` 10.8 → 9.6.
  - Net per-spawn fixed context, Kiro developer: 32.5 KB → 24.3 KB. analyst/architect/qa each drop
    ~6 KB of steering; the orchestrator drops the same on top of its 25 KB skill.
- **Prompt-size pass — every hot file rewritten tighter (−95 KB, ~43% of the kit's per-spawn surface).**
  No rule, command, JSON shape, gate, or user-facing prompt string was dropped; what went was
  restatement, rationale-about-rationale, historical notes on superseded behavior, and the per-skill
  metadata blocks (Trigger/Input/Output/When/How ×10) that each role duplicated for skills whose own
  `SKILL.md` already says all of it — now one line per skill naming when to load it.
  - Kiro role agents, loaded in full on every spawn: `developer.md` 44 KB → 18 KB (−58%),
    `architect.md` 37 → 18 (−51%), `analyst.md` 36 → 18 (−48%), `qa.md` 30 → 18 (−39%). Each keeps its
    Kiro-specific machinery (sub-phase mini-gates, resume presentation, `/opsx:*`, `/agent swap`
    routing, checkpoint report blocks) and now leads with a single "đọc trước tiên" list instead of
    repeating the same input inventory across ROLE / CONTEXT / per-step sections. The 20+ item
    self-validation checklists that re-listed already-stated Hard Rules collapse to one short
    pre-gate paragraph.
  - `sdlc-orchestration-core/SKILL.md` (every orchestrator session) 43 KB → 25 KB (−41%): the
    `type`/`rigor`/`test_scope`/`scope` "don't confuse these" warnings — four separate callouts saying
    the same thing — become one table plus one line; the enforcement paragraphs shrink to the one
    sentence that says which guard blocks what.
  - `steering/sdlc-workflow.md` (always-included on Kiro, every role, every spawn) 8.5 → 6.0 KB: the
    git-isolation procedure now points at `sdlc-orchestration-core` §New Change Setup instead of
    restating it; the role-is-a-playbook-not-an-identity invariant stays verbatim in substance.
  - `targets/claude/CLAUDE.md` 4.6 → 4.0 KB, Kiro `onboarder.md` 20 → 19 KB.
- **Orchestrator may switch to an existing isolation branch on resume.** The shell guard now allows the
  orchestrator a plain `git switch <branch>` (no flags, one arg) in addition to the branch/worktree
  *create* it already permitted — so a resumed session that starts on the base branch can move onto the
  pipeline's isolation branch before delegating (§2 Load State does this automatically, comparing HEAD to
  `_state.json.isolation.branch`). `git switch` is file-safe (it cannot restore/overwrite a file the way
  `git checkout <path>` can); dangerous forms stay blocked — `git checkout <anything>`, any `git switch`
  with `-f`/`--discard-changes` or a trailing pathspec, and every chained command. Guard self-test 61/61.
- **Token-efficiency pass (per-spawn + per-phase cost).** Three independent cuts to what every pipeline burns:
  - **Dead MCP grants removed from `analyst` + `architect`** (both targets). Both roles read the
    normalized intake package under `docs/extra-docs/` (produced by `intake`, which alone owns
    `@redmine`/`@figma`); they never called `@redmine`/`@bookstack`, yet each spawn loaded the full
    schema surface (~40 BookStack tools + Redmine) whenever those servers were connected. Frontmatter
    (`tools:`) and Kiro `tools`/`allowedTools` narrowed to `read/write/shell`; Kiro `includeMcpJson`
    set `false` on both; the analyst's ticket-detection hint now points at the intake package instead
    of a `@redmine` fetch it can no longer perform.
  - **Model tiers rebalanced.** `analyst` → Sonnet, and the Claude `sdlc-full`/`sdlc-fast` orchestrators
    → Sonnet (matching Kiro, which already ran them on Sonnet). `architect` stays Opus (design
    reasoning); `developer`/`qa` already Sonnet. The longest-running / highest-frequency roles no longer
    default to Opus.
  - **`scope=tiny` now sized on evidence, not feature count.** The analyst's S2 scope call (and the
    developer's S4 call for bugfix/hotfix) judges by change *size* (~≤2–3 files, no new
    entity/schema/migration, no new integration, not security/data-integrity, no new design decision)
    and is a **mandatory recorded decision** in `_handoff.md`, so a small CR resolves to `tiny` instead
    of silently falling through to full-depth `standard`. Backstops unchanged: architect may still
    escalate `tiny`→`standard` at S3, and the developer's final checkpoint always runs full coverage.
- **Shared workspace + config are root-only** (no symlink); framework runtime stays per-platform. `init`
  migrates older per-platform copies/symlinks to the root and merges `.claude/settings.json` (unions
  permissions; preserves `enabledPlugins`/`env`/`model`) instead of clobbering it.
- **Orchestrator is a dedicated agent**, write-fenced to baton/state files — it cannot author a phase
  deliverable, forcing delegation to the role agent (Claude: Task spawn · Kiro: subagent / `/agent swap`).
  A bare main session on Claude is the unrestricted default workspace.
- **Kiro orchestrators delegate via real subagents** (gained the `subagent` tool); the delegated role
  runs under its own write-fence. `/agent swap` remains the manual fallback.
- `apply-stack`, both doctors, the mapper, `context-check`, and `agent-spawn-context` all resolve the
  shared workspace at the project root; `settings.json` allow-list widened for the orchestrator's routine
  ops (Task spawn, `Write/Edit(openspec/** + memory/**)`, branch-create git) — code writes stay prompted.
- **Role memory + cross-spec bridge are now one-file-per-change, not one shared file.** Every SDLC
  change runs on its own isolated branch/worktree; a shared `memory/<role>.md` or
  `openspec/_cross-spec-context.md` that every branch appends to guarantees a merge conflict the moment
  two changes are in flight at once. Now each write-back targets `memory/<role>/<change-name>.md` /
  `openspec/_cross-spec-context/<change-name>.md` — unique filenames never collide across branches, and
  reads glob+concat the directory instead of one file. `cpp-guard`'s trailing check and
  `check-write-path.py`'s write-fence/append-guard already matched on path *prefixes* (`memory/**`,
  `openspec/_*.md` with fnmatch spanning `/`), so no guard code changed — only the agent
  prompts/skill instructions and `cpp-guard`'s cross-spec existence check. Existing shared files in a
  deployed project are migrated automatically (split by `## ` section into the new per-change files;
  the original is kept as `<file>.pre-migration-backup`).
- **Legacy shared memory/cross-spec paths are now hard-blocked**, not just migrated. A role running
  under a stale cached agent definition (agent defs only reload at session start — a session opened
  before an upgrade keeps using the old prompt for its whole lifetime) could otherwise keep
  recreating `memory/<role>.md` / `openspec/_cross-spec-context.md` indefinitely, silently
  reintroducing the shared-file merge-conflict hazard the per-change split was meant to remove.
  `check-write-path.py` now denies a write to those five exact legacy paths outright with a message
  pointing at the new per-change path and naming the stale-session cause, instead of allowing it
  through `memory/**`.
- **The per-change-file migration in `init.mjs` no longer clobbers its own backup.** A second
  migration pass (e.g. triggered by a stale session recreating the legacy file after the first
  upgrade) used to `rename()` straight onto `<file>.pre-migration-backup`, silently overwriting the
  first pass's backup — the actual mechanism behind a real data-loss incident. Backups are now
  numbered (`.pre-migration-backup`, `.pre-migration-backup.2`, …) and never overwritten.

### Fixed

- **`init` no longer relocates your own `.gitignore` lines.** The kit block was maintained by stripping
  it and re-appending at EOF, so every user line that happened to sit *after* the block was silently
  moved above it (and its trailing whitespace trimmed) — a permanent `M .gitignore` whose entire diff
  was reshuffling. Worse on a file whose rules depend on order: a `!` negation only wins when it
  *follows* the pattern it overrides, so the reshuffle could change what git ignores. The block is now
  rewritten **in place**; only a first install appends, and bytes outside the markers are preserved
  exactly (missing final newline included). Duplicate blocks from a hand-edit still collapse to one.
  Nothing inside an already-installed project changes — `init.mjs` is never copied into a project, so
  the fix simply applies at the next `kiro-sdlc-init` run.
- **`init` now warns when a project line excludes the `.kiro` *directory*.** The kit's `!.kiro/specs/`
  cannot work if anything — at any position, in any layer — excludes `.kiro` itself, because git never
  descends into an excluded directory. Already-tracked specs keep working, so the breakage only shows
  up when a teammate adds a NEW spec file and `git status` never mentions it. `init` prints the
  offending line number and the one-character fix (`.kiro/` → `.kiro/*`) and **changes nothing**: the
  line lives outside the kit's markers, is often deliberate, and belongs to the project.
- **`.gitignore` block: `.kiro/` → `.kiro/*` + `!.kiro/specs/`.** Ignoring the *directory* stopped git
  from descending into `.kiro/`, which killed any `specs/` negation (even one in a higher-precedence
  ignore layer) and silently hid teammates' NEW Kiro spec docs — old ones stayed tracked, so the loss
  was invisible. The block now ignores contents and re-opens `.kiro/specs/`; run `init
  --gitignore-only` on existing projects to pick it up.
- **Hooks survive a mid-session `cd`** — every hook runs `cd "${CLAUDE_PROJECT_DIR}" && …` and the
  scripts self-locate the project root, so a `cd` into a subdir no longer bricks the session (cwd-poisoning).
- **Guards read config from the project root** (`./pipelines.json` / `./sdlc.config.json`), not the
  per-platform paths removed by the root-only refactor.
- **`CLAUDE.md` `@import` paths** fixed to `@steering/…` / `@context/…` (were `@.claude/…`, silently
  dropping all steering + context at runtime).
- **Shared skills no longer hardcode `.kiro/`** — a per-platform `{{PLATFORM_DIR}}` token; a claude-only
  install no longer fails the gate guard or the xlsx generator.
- **`check-write-path` follows the host** (Claude built-in policy vs Kiro JSON); platform-prefixed write
  targets are blocked; `src/**` stays developer-only on every non-developer role.
- **`doctor-claude`** validates the kit-managed `.claude/CLAUDE.md` (not a project's own root file).
- **Gate-rejection vocabulary unified to `nogo`** — `sdlc-orchestration-core` SKILL.md internally named
  the same action `reject`, diverging from every user-facing doc/agent prompt (both platforms already
  said `nogo <reason>`). GUIDE.md now documents `nogo`'s default per-phase routing (S2→analyst ·
  S3→architect · S4→developer · S5→qa), how to override it when root cause is already known to sit in
  an earlier phase, and `dispute bug #N`'s BUG/DESIGN GAP/SPEC GAP routing — previously undocumented
  outside the shared skill.
- **Kiro `analyst.json`/`architect.json` write-fence never got `memory/**`** when role-memory
  write-back shipped (they were narrowed to `openspec/**` only in an earlier, unrelated pass) —
  `cpp-guard` required the write-back decision but the Kiro host physically blocked the write it
  gates on. `developer.json` had the same drift for `pkg/**`/`internal/**`/`cmd/**`/`e2e/**`/
  `pyproject.toml`, present in the built-in policy but never ported to its JSON. Also fixed
  `check-write-path.py`'s own self-test, which could not have caught this: run from the kit source
  tree, its cwd-relocation landed one directory short of the repo root, so every "Kiro host" vector
  silently fell back to the built-in policy instead of reading the real per-agent JSON; added
  `memory/<role>.md` + the missing developer-path vectors so this class of drift fails loudly.
- **`openspec/config.yaml`'s kit-installed `rules:` block was write-once, then frozen forever.**
  `init` checked "does `rules:` exist at all" and skipped re-installing it on every subsequent
  `--force` — so any upgrade to `kit/shared/ai/openspec-rules.yaml` (including the `scope=tiny`
  exceptions above) silently never reached an already-onboarded project; `openspec instructions`
  kept emitting the stale rules text no role prompt could override. Now marker-bounded
  (`# --- kiro-sdlc-kit rules ... ---`), like the kit's `.gitignore` block: `--force` replaces only
  the content between the markers, so kit-side rule fixes always propagate, while anything a project
  hand-added outside the markers survives. A one-time migration replaces an old unmarked block (it
  was always appended last, so everything from `rules:` to EOF is the kit's own content).
- **`normalize_path()` tried the `specs/` marker before `openspec/`** — a git-worktree write to
  `openspec/changes/<name>/specs/<cap>/spec.md` (cwd-strip doesn't apply to a worktree, a sibling
  dir) truncated at the inner `specs/` marker and never reached `openspec/`, dropping the prefix the
  allow-list needs and wrongly blocking the analyst's spec-delta write. Marker order is now
  `openspec/` before `specs/` (specific-before-general, matching every other marker pair); added
  regression vectors for both worktree shapes.
- **`check-shell-command.py` false-positive-blocked plain reads for restricted roles**, from a real
  incident (a QA re-run retried repeatedly and burned tokens on retries alone): the guard scanned raw
  command TEXT with no notion of quoting, so a literal `>` inside a grep/sed pattern (`grep -o
  '<Tag>.*</Tag>' file.xml`) or a `->` inside a quoted `--execute="Foo::bar()->baz()"` string looked
  identical to a real shell redirect and got blocked; separately, `phpstan analyse A.php B.php` was
  misread as "interpreter `php` running script `B.php`" because the script-file regex matched the
  tail of `A.php`'s OWN extension as if it were the interpreter name. Fixed by (1) blanking the
  CONTENTS of `'...'`/`"..."` string literals before the `_DENY` scan — quoted text is inert shell-wise,
  verified empirically that an UNQUOTED `->` really is a redirect (`echo a->b` creates file `b`) so
  this had to be quote-aware, not a blanket exclusion, or it would have opened a real bypass; (2) a
  `(?<!\.)` lookbehind on the script-execution rule so an interpreter name glued directly after a `.`
  (i.e., someone else's file extension) is never treated as a real invocation. 9 new self-test vectors
  cover both the fixed false positives and that real redirects/mutations still block. `mkdir`/`tee`
  remain absolute blocks for restricted roles (by design, not a bug) — use the Write tool or let the
  target command create its own directory.
- **No way to update `_state.json` without a full-file round-trip for array fields.** `state-set.mjs`
  only supported `--set`/`--unset` on scalars/objects; appending one `phase_history` entry (the one
  update every role makes every phase) meant reading the whole array, splicing in one element, and
  passing the ENTIRE thing back as a `--set` value — or falling back to a raw `Write` of the whole
  file, the exact per-gate full-rewrite cost `state-set.mjs` was built to eliminate. Added `--append
  <path>=<json>` (creates the array if unset); all four role prompts (both targets) now append their
  own `phase_history` entry instead of rewriting `_state.json` wholesale. Also added a non-blocking
  length nudge: an appended entry's `note`/`result`/`summary` past ~400 chars prints a warning — detail
  belongs in `_handoff.md`/`memory/<role>/`, which are read selectively; `phase_history` is read in
  full by every later phase, forever.
- **QA had no resume path after being killed mid-run.** An interrupted QA pass (another real incident)
  had no way to signal "partially done" — a re-spawn regenerated test scenarios and re-ran already-
  passed tests from scratch, re-spending the whole prior run's tokens. QA (both targets) now checks for
  an existing partial `qa-report.md`/`qa/testcases.*` first and continues from what's missing instead
  of restarting.
- **`_progress.md` was written TWICE per gate — once by the role, once by the orchestrator — using
  two INCOMPATIBLE formats.** Every role already writes its own table row (the shape in
  `agents/examples/progress-example.md`) when finishing a phase. Separately, the orchestrator's
  "Progress Marking (MANDATORY on gate approval)" step had it hunt for a `## Overall Progress`
  checkbox-list heading and flip `- [ ] {phase}` → `- [x]` — a format NO role's actual output has ever
  produced (grep confirms it appears nowhere else in the kit); this dead pattern-match forced the
  orchestrator into an ad-hoc full-file rewrite every approval, duplicating information the role had
  already written, in a shape that never matched. `cpp-guard`'s actual check is a loose count
  (`[x]`/`✅` occurrences ≥ passed-gate count) that the role's own row already satisfies, so the
  orchestrator's second write bought nothing. Removed it — `_progress.md` is now the role's artifact
  only, everywhere the orchestrator prompts (both targets' `sdlc-full`/`sdlc-fast` +
  `sdlc-orchestration-core` SKILL.md) previously said otherwise. Also closed a real gap this surfaced:
  the Claude-target role prompts listed `_progress.md` as a required CPP artifact but never actually
  said how/when to write it (Kiro's did) — all four now carry the same row-format instruction Kiro
  already had.
- **A stale Hard Rule still told the orchestrator to hand-rewrite `_state.json`** (`"NEVER create
  duplicate JSON keys — READ → parse → modify in-memory → WRITE whole file"`), left over from before
  `state-set.mjs` existed and directly contradicting the "never hand-rewrite" rule earlier in the same
  file. Now says to always use `state-set.mjs`.
- **A systematic 3-agent sweep for the same "leftover from an older design" bug shape found 8 more
  confirmed instances, each verified with grep evidence before fixing:**
  - `qa-analysis`/`qa-test-design`/`cross-artifact-audit` all read a `## _Structured Extract` section
    from `proposal.md` as their FIRST, authoritative input — but only the Kiro-target analyst.md ever
    had a rule requiring the analyst to write it (`R5: Structured Extract — MANDATORY Section`); the
    Claude-target analyst.md had zero mention of it. Every Claude-target QA/architect run was hunting
    for a section the Claude-target analyst was never told to produce. Added the equivalent `R5` to
    Claude's `analyst.md`.
  - Kiro `architect.md`'s S3-A/B/C sub-phase transitions hand-wrote `_state.json` as a raw JSON
    literal 3× per S3 phase, two paragraphs below the file's own `state-set.mjs`-only rule (R12) —
    now all three use `state-set.mjs --set current_phase=…`.
  - S6/archive in BOTH targets' `developer.md` hand-wrote `_state.json` with 3 fields at once,
    *in the same paragraph* whose very next sentence correctly used `state-set.mjs` for a smaller
    follow-up write — backwards from every other instance in the kit. Both now use `state-set.mjs`.
  - Kiro `developer.md`'s S4-FIX exit hand-wrote `_state.json` the same way — same fix.
  - `sdlc-orchestration-core` SKILL.md's Dispute Resolution and Convergence-loop sections described
    `disputes[]` and `convergence.<PHASE>` as raw JSON shapes with no `state-set.mjs` call given,
    unlike `phase_history`/`gates`/`deploy_status` which each get a worked example — both now do too
    (`--append disputes=…`, `--set convergence.<PHASE>.rounds=… --set convergence.<PHASE>.stable=…`).
  - Claude `architect.md`'s own `_state.json` bullet ended with a dangling `"READ → modify → WRITE
    whole file."` sentence directly contradicting the `state-set.mjs` command two lines above it — a
    copy/paste leftover from the boilerplate shared with `_handoff.md`/`_decisions.jsonl` (where that
    phrase IS correct), never rescoped when reused for `_state.json`. Removed.
  - `cross-artifact-audit` SKILL.md flagged any `tasks.md` with `< 2 checkpoints` as a gap with no
    `scope=tiny` exception, while architect's own Hard Rule R3 (both targets) and `openspec-rules.yaml`
    already carry the exception (1 final checkpoint is enough at `scope=tiny`) — the audit gate would
    flag a legitimately-tiny change's own correctly-sized `tasks.md` as defective, forcing padding or
    blocking convergence from ever stabilizing. Added the matching exception to the audit rule.
  - Kiro `developer.md`'s R13 ("run type-check, lint, format-check, test, AND coverage" at every
    checkpoint) contradicted the file's own later, `test_scope`-aware checkpoint rules two sections
    down (intermediate = affected-tests-only, no coverage; final = full `test_scope`-width + coverage)
    — R13 was never updated when `scope`/`test_scope` shipped. Now points at the detailed rule instead
    of restating a stale blanket version of it.
  - `sdlc-orchestration-core` SKILL.md's own CPP Contract Checks section still named the pre-migration
    flat `memory/<role>.md` path in one blockquote, contradicting the per-change-file path
    (`memory/<role>/{change-name}.md`) correctly used everywhere else in the same file and by every
    role prompt. Fixed the reference.
- **`memory/<role>/_index.md` added to the kit's `.gitignore` block** — real conflict reported: it's
  the one `memory/` artifact every parallel branch/worktree appends to at the SAME path (unlike
  `memory/<role>/{change-name}.md`, one unique file per change, which is exactly why THAT split
  happened). `context/`, `openspec/`, `docs/`, and the per-change memory files stay tracked/committed
  as before — only this specific derived digest is now ignored, since `init --force`'s
  `backfillMemoryIndex()` already regenerates it in full from the `{change-name}.md` files' own `## `
  headers, so nothing is lost by not tracking it.
- **`context/*.md` merge conflicts across parallel branches — no gitignore fix exists here, unlike
  `memory/_index.md`, because `context/*.md` is hand-curated and NOT regenerable.** Real conflict
  reported: `onboarder`/`context-refresh` had zero guardrail against running on a per-change isolated
  branch/worktree — nothing stopped two feature branches from each independently drifting the SAME
  shared `context/*.md` a different way, guaranteeing a real content conflict on merge. Both agents
  (both targets) now check `git branch --show-current` against `sdlc.config.json →
  git.protected_branches` as their first step and warn + ask for confirmation before touching
  `context/` from a branch that isn't the shared base — the fix is procedural (don't diverge it in the
  first place), not file-exclusion (there's nothing to regenerate it from).
- **Corrected the above fix's recommendation**: "switch to the protected branch and do it there" is
  wrong advice for a repo where the protected branch (`main`/`master`) never takes direct commits at
  all (every change goes through a PR — a common, deliberate branch-protection policy, not a
  workflow gap). All four prompts now recommend **a fresh, dedicated branch cut from the latest
  protected branch, just for the context update** (`git checkout -b chore/context-refresh
  origin/<protected_branches[0]>`), merged back via its own small PR, independent of any feature
  branch — this respects "no direct commits to the protected branch" while still preventing the
  context update from tangling with (and diverging alongside) a long-lived feature branch.
- **`/context/` is now an opt-in gitignore exception (project choice, not a kit default).** After
  weighing it, the user judged the branch-discipline fix above too fragile (relies on every session
  remembering to check/ask) versus the certainty of just not tracking `context/*.md` in git at all.
  Since that content is hand-curated and NOT regenerable — unlike `memory/*/_index.md` — this is a
  real trade: zero merge conflicts, but no git history/shared source of truth for it either. Wired
  through: `init.mjs`'s `GITIGNORE_PATTERNS` gains `/context/`; a fresh `git worktree add` no longer
  populates it at all (untracked directories aren't checked out), so §New Change Setup in
  `sdlc-orchestration-core` now also symlinks `context/` into new worktrees alongside the existing
  `memory/` note; and `onboarder`/`context-refresh` (both targets) now probe `git check-ignore -q
  context/` FIRST and branch their Hard Rule accordingly — tracked project → the branch/PR discipline
  from the previous fix; ignored project → skip straight to editing the one shared (symlinked) copy,
  since there's nothing left to merge-conflict on. The same kit prompt now correctly serves both a
  default (tracked) project and one that opted into this trade.

- **`doctor-claude.mjs`** — structural health check for the Claude target: `CLAUDE.md` `@import`s
  resolve, all commands + subagents exist, the "only `developer` has `Edit`" invariant holds, and
  `settings.json` hooks point at installed scripts/tools.

## [1.1.0] — 2026-06-24

Three themes: a full skill audit, automatic git isolation per pipeline, and a working
per-pipeline test-case (`testcases.xlsx`) option. All changes are backward-compatible —
existing installs upgrade cleanly via `init --force` (kit-owned files are replaced; your
`openspec/` changes & specs, `memory/`, and filled `context/*.md` are preserved).

> **Upgrading:** run `node bin/init.mjs <project> --check` to preview, then `--force` to apply.
> ⚠️ `sdlc.config.json` is kit-owned and will be overwritten — diff first if you customized it.

### Added

- **Git isolation per pipeline.** When the orchestrator creates a new change it now auto-creates a
  dedicated **branch or worktree** before the first phase, so no pipeline ever codes on a protected
  branch or a previous feature's branch.
  - New `git` block in `sdlc.config.json`: `isolation` (`ask`/`branch`/`worktree`/`off`),
    `default_method`, `branch_naming` (`{type}/{ticket}-{slug}`), `worktree_path`, `protected_branches`.
  - The chosen method/branch is persisted to `_state.json.isolation`.
  - Orchestrators (`sdlc-full`/`sdlc-fast`) gain a narrowly-scoped `git` shell permission for
    branch/worktree creation only.
- **Per-pipeline test-case artifact option.** The `testcases.xlsx` deliverable for QA managers is now
  selectable **per change** (the knob existed but was orphaned — nothing produced or enforced it).
  - Resolved at kickoff: runtime flag (`--xlsx`/`--md`/`--no-xlsx`) → `qa.testcase_export` config seed
    → one kickoff question; the answer persists to `_state.json.testcase_export`.
  - Shipped a portable generator `kit/skills/qa-test-design/gen_testcases_xlsx.py` (Python + openpyxl,
    Status colour-coded; automatic **`.csv` fallback** when openpyxl is absent — no Node dependency).
  - The QA agent (S5) now actually produces the artifact (previously Phase 1 was forbidden).
- **Skill documentation in agent prompts.** Every wired skill is now documented (when/how to use) in
  its agent: `developer` +5 (`deployment-patterns`, `sonar-local`, `search-first`,
  `api-documentation-checker`, `agentic-engineering`), `architect` +1 (`search-first`), and
  `onboarder` gained a Skills section.
- `CHANGELOG.md` (this file); `__pycache__/` and `*.pyc` added to `.gitignore`.

### Changed

- **Test-case format** is now read from `_state.json.testcase_export` (the per-pipeline choice), not
  re-derived from config/rigor inside the skill.
- `sdlc-fast` no longer wires `spec-auditor` / `cross-artifact-audit` (those gates are S2/S3 and never
  run in fast-track); `sprint-retro` is kept (it runs at S6, which fast-track does reach).
- `R-SDLC-003` (branch policy) generalized from feature-only to **all** pipeline types, with the
  `{type}/{ticket}-{slug}` naming convention and a pointer to the `git` config block.
- Stack-coupled skills now defer to project conventions instead of hardcoding a stack:
  `api-design` and `cross-artifact-audit` defer to `context/conventions.md`; `security-audit` is
  stack-agnostic (Laravel/Next.js/zod equivalents alongside the NestJS examples); `verification-loop`
  uses the project's commands (`context/stack.md`) instead of literal `npm`/`vitest`/`tsc`.

### Fixed

- **S5 gate now enforces the test-case artifact** when selected: if `testcase_export ∈ {xlsx, md}`,
  `pipeline-guard.mjs` blocks the gate unless `qa/testcases.{xlsx|md|csv}` exists with ≥1 row
  (no auto-pass, even at 0 Critical/High). `none` and legacy state without the key skip the check.
- **Dead references removed** across skills: `search-first` (non-existent `planner`/`researcher`
  agents, `iterative-retrieval` skill), `agentic-engineering` (`tdd-workflow`),
  `api-documentation-checker` (phantom `api-doc-reminder` hook), `sonar-local` (phantom
  `scripts/sonar-local.sh` — `npx sonarqube-scanner` is now the primary path).
- **Phantom generator reference** in `qa-test-design` (`scripts/generate-test-excel.ts`) replaced with
  the shipped Python generator.
- Stale content fixes: `php-implicit-behavior-audit` de-branded (hardcoded vendor paths →
  `context/legacy-ref.md`); `context-mapper` example (`specs` key that doesn't exist);
  `assumption-detector` step number; `edge-case-enumerator` category list; `sprint-retro` gate table,
  cost model, and dead skill/agent references; `architect` description sync (`.md` ↔ `.json`).

### Security

- Hardened the orchestrator shell guard (`check-shell-command.py`): the new git permission is a tight
  allow-list — only `git checkout -b` / `git switch -c` / `git worktree add` (no command chaining or
  substitution); all other git working-tree mutations (`add`/`commit`/`checkout <file>`/`reset`/
  `merge`) stay blocked, and a pre-existing gap (`git branch -D/-m` delete/rename) is now closed.
  The "orchestrator never writes code" invariant is preserved.

[1.1.0]: https://github.com/your-org/kiro-sdlc-kit/releases/tag/v1.1.0
