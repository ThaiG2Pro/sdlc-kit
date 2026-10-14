---
name: release-and-fix
description: >
  The developer's S4-FIX (fix bugs QA reported) and S6 (release + OpenSpec archive) procedures.
  Load this when the trigger is /s4-fix or /s6. Not needed on a plain /s4 build run — which is why
  it lives here instead of in the always-loaded developer prompt.
---

# S4-FIX and S6 — developer procedures

Only the **developer** role runs these. `{PLATFORM_DIR}` = `.kiro` or `.claude`; `{CHANGE_DIR}` =
`openspec/changes/<change-name>/`. Your role's Hard Rules still apply in full — this file adds the
per-trigger steps, it does not replace them.

## S4-FIX — QA found bugs (`/s4-fix {change-name}`)

1. Query bugs from engine: `bin/sdlc-ctx bug list --change-id "{change-name}"` → bug list (severity + AC-ID).
2. Present the fix plan as `| # | Bug | AC-ID | File | Root Cause |` and wait for "go".
3. In order Critical → High → Medium: write a **failing test that reproduces the bug** (tagged with its
   AC-ID) → fix → regression run over that module.
4. Type-check + lint clean, coverage still ≥ threshold. **APPEND** to the existing
   `dev-test-report.md` — never create a new file, because QA's retest reads the SAME file:
   ```
   ## Bug Fixes (S4-FIX — {date})
   | Bug # | AC-ID | Fix | Test | Status |
   ```
5. Exit checklist before handing back to QA:
   - type-check / lint / test pass
   - `dev-test-report.md` §Bug Fixes appended
   - Mark bugs resolved:
     `bin/sdlc-ctx bug retest --bug-id <BUG_ID> --status resolved --verification-notes "<fix summary>"`
   - Record fix decision:
     `bin/sdlc-ctx baton decision --change-id "{change-name}" --phase S4-FIX --role developer --title "Bug fixes S4-FIX" --decision "<summary>" --rationale "<details>"`
   - Record handoff:
     `bin/sdlc-ctx baton handoff --change-id "{change-name}" --from-phase S4-FIX --to-phase S5 --from-role developer --to-role qa --summary "Fixed bugs, ready for retest"`
   - Transition & export:
     ```bash
     bin/sdlc-ctx change transition --change-id "{change-name}" --to S4-FIX
     bin/sdlc-ctx sync export --change-id "{change-name}" --dir ./openspec/changes/{change-name}
     ```

## S6 — Release (`/s6 {change-name}`)

1. **Prerequisites** — verify via `bin/sdlc-ctx gate inspect --change-id "{change-name}" --gate QA` (0 Critical/High open).
   Otherwise STOP.
2. **Migration review** — `design.md` §DB Schema plus every migration created in S4: each has both
   `up()` and `down()`, and no destructive change lacks a backup plan.
3. **`{CHANGE_DIR}/release.md`** — fill `release-template.md` using the `deployment-patterns` skill
   (release notes by AC-ID, migration checklist, rollback plan, post-deploy smoke, deploy strategy).
4. **Archive** — `openspec archive "{change-name}"` (or `/opsx:archive`): merges the spec deltas into
   the living spec and moves the change to `openspec/changes/archive/`. NEVER merge by hand. Archive
   runs **before** the real deploy on purpose — it keeps the living spec fresh for other specs in
   flight, and the RELEASE gate does not wait on post-deploy.
5. **Handoff** — transition state in the Context Engine:
   ```bash
   bin/sdlc-ctx change transition --change-id "{change-name}" --to S6
   bin/sdlc-ctx sync export --change-id "{change-name}" --dir ./openspec/changes/archive/{change-name}
   ```
   Tell the user to review `release.md`, then deploy.

   If a promotion is rejected: forward-fixable → open a NEW `bugfix`/`hotfix` pipeline, never reopen an
   archived change; a real rollback → `git revert` the archive commit (undoes code and living-spec together,
   see `release.md` §"If Rejected After Archive"), and never hand-edit the living spec.
