---
name: sprint-retro
description: >
  Sprint/Feature retrospective: đánh giá SDLC execution, SDLC cost violations,
  AI detection rate, loop-backs, và action items cụ thể cho lần sau.
  Dùng sau khi hoàn thành một feature (S6) hoặc cuối sprint.
---

# Sprint Retro — {{PROJECT_TITLE}} AI-Augmented SDLC

Retrospective tool cho AI-Augmented SDLC, aligned với `{{PLATFORM_DIR}}/steering/sdlc-workflow.md`.

## When to Activate

- Sau S6 Release Prep của mỗi feature
- Cuối sprint (weekly/bi-weekly)
- Sau incident hoặc major bug từ production

## How to Use

```
Dùng skill sprint-retro để review feature: cms-product-management
Dùng skill sprint-retro để review sprint: Sprint 2026-W14
```

Cung cấp context nếu có:
- Link đến `specs/` của feature
- Git log range: `git log --oneline origin/main..HEAD`
- Test coverage report
- Số bugs/issues được tạo trong sprint

## Retro Framework: SDLC-Aware 4Ls + Gate Audit

### 1. Gate Compliance Check

Kiểm tra lịch sử và trạng thái từng SDLC gate qua Context Engine:
```bash
bin/sdlc-ctx gate list --change-id "{change-name}"
```

| Gate | Expected Output | Actual | Notes |
|------|-----------------|--------|-------|
| S1 → S2 | Requirement Pack với ACs | ✅/❌ | |
| 🔒 S2 SPEC LOCK | spec-auditor PASS + `bin/sdlc-ctx gate inspect --gate SPEC_LOCK` | ✅/❌ | |
| 🔍 S3 DESIGN REVIEW | cross-artifact-audit 0 CRITICAL + `bin/sdlc-ctx gate inspect --gate DESIGN_REVIEW` | ✅/❌ | |
| S4 → S5 | Tests pass + coverage ≥ `coverage.min` + `bin/sdlc-ctx gate inspect --gate BUILD_VERIFY` | ✅/❌ | |
| S5 → S6 | QA GO + 0 Critical bugs + `bin/sdlc-ctx gate inspect --gate QA` | ✅/❌ | |

**Gate violations** = Late-stage changes = Cost multiplier applied.

### 2. Cost Escalation Audit

Dựa trên SDLC cost model (authoritative table in `sdlc-workflow.md`):

```
S3 sketch → S2 (spec gap)  → 3×
S4 → S3 (design gap)       → 5×
S4 → S2 (spec gap)         → 5-8×
S5 → S3 (design gap)       → 20×
S5 → S2 (spec gap)         → 25×
```

Liệt kê:
- Số lần loop-back (S4→S2, S5→S3...)
- Nguyên nhân: Requirement unclear? Design gap? Dev mistake?
- Estimated waste cost multiplier

### 3. AI Performance Metrics

```markdown
| Metric | Target | Actual | Trend |
|--------|--------|--------|-------|
| AI-detectable bugs caught by AI | ≥ 90% | ? | |
| Logic bugs missed by AI | 0 | ? | |
| Spec adherence (no unauthorized deviation) | 100% | ? | |
| Test coverage on new code | ≥ 80% | ? | |
| Hooks fired correctly (architect + qa) | ✅ | ? | |
```

### 4. Standard 4Ls

**What went WELL (Liked)**
- [ ] AI-generated drafts quality
- [ ] Gate process efficiency
- [ ] Test coverage achieved
- [ ] Deployment smoothness

**What we LEARNED (Learned)**
- Requirements ambiguities discovered late
- Design decisions that changed in S4
- New patterns found

**What we LACKED (Lacked)**
- Missing skills/patterns in `{{PLATFORM_DIR}}/skills/`
- Gaps in agents prompts
- Hooks not triggered as expected

**What we LONGED FOR (Longed For)**
- Process improvements needed
- New tools/skills to add
- Workflow automation opportunities

### 5. Action Items Template

```markdown
## Retro Action Items — {Feature/Sprint}

### Process (SDLC)
- [ ] [Owner] Add AC template to analyst.md for edge case coverage by {date}
- [ ] [Owner] Update architect review hook to catch {specific pattern}

### Skills/Knowledge Base
- [ ] [Owner] Add pattern X to coding-standards/SKILL.md
- [ ] [Owner] Create new skill for Y

### Team/AI
- [ ] [Owner] Clarify scope definition in S1 intake checklist
- [ ] [Owner] Add missing test templates to test-generator/SKILL.md
```

## Output Format

```markdown
## Sprint Retro: {Feature/Sprint Name}

### Gate Compliance: X/5 gates passed (Y violations)
**Violations:**
- S2 SPEC LOCK broken: 2 requirement changes after S4 started
  → Cost impact: estimated 2×5× = 10× wasted effort on 2 tasks

### AI Performance
- AI-detectable bugs caught: 8/10 (80%) — target 90%
  → Missed: null check in order.service.ts, missing auth guard on /admin endpoint
- Test coverage: 83% (target 80%) ✅
- Unauthorized spec deviations: 1 (payment endpoint URL changed without update)

### 4Ls Summary
- Liked: AI-generated DTO boilerplate saved ~2h
- Learned: Scope ambiguity in "archive" vs "delete" requirements
- Lacked: No skill for pagination response validation
- Longed For: Automated spec lock enforcement in hooks

### Action Items (3 max per retro)
1. [ ] Add "archive vs delete" disambiguation to S1 intake template [Analyst] [+1wk]
2. [ ] Create pagination-response skill [Developer] [+1wk]
3. [ ] Add spec lock warning to sdlc-full orchestrator hook [DevOps] [+2wk]

### Trend: Sprint Health Score: 72/100 (prev: 65) ↑
```

## Persist lessons to role memory (HARVEST — do this last)

The retro above is a one-time report. Its **Learned** / **Lacked** items are exactly the cross-spec
lessons that the role agents read at the top of every future run (`memory/<role>/*.md` — one file per
change, so parallel changes on separate branches never touch the same path). The per-phase write-back is
advisory and easy to skip in the heat of a build — so the retro is the **safety net** that makes sure
nothing reusable is lost before the change is archived.

For each Learned/Lacked item that is **reusable and not specific to this one change**, route it to the
role most likely to re-encounter it and record it in Context Engine role memory:

```bash
bin/sdlc-ctx role remember --role <role> --change-id "{change-name}" --title "{one-line lesson}" --content "{pattern + how to avoid it next time}"
```

Dual-layer sync will automatically mirror this into `memory/<role>/{change-name}.md` and update `memory/<role>/_index.md`:

| Lesson type | Target Role |
|---|---|
| recurring bug pattern · validation/sync trap · framework gotcha | `developer` |
| hollow-assertion pattern · coverage gap · 5xx/validation bug pattern · smoke-checklist item | `qa` |
| recurring ADR trade-off · cross-feature constraint · design anti-pattern | `architect` |
| requirement-ambiguity pattern · domain edge case easy to miss · clarification trap | `analyst` |

Section format in markdown: `## {ISO-date} — {change-name}: {one-line lesson}` followed by 1–4 bullets (the pattern +
how to avoid it next time). Rules:

- **Append-only within the file.** If that role already wrote to `memory/<role>/{change-name}.md` earlier
  in THIS change's pipeline, READ it first — never delete or overwrite an existing `## ` section (the
  write-path hook blocks a write that drops one). Add new sections; leave old ones intact.
- **De-dup across the role's whole directory.** Before writing, skim every `memory/<role>/*.md` file (not
  just this change's) — if a near-identical lesson already exists in an earlier change's file, don't add a
  twin; skip it (or note the refinement in this change's file instead).
- **No filler.** A clean change with no reusable lesson writes nothing to memory. Process/tooling action
  items (e.g. "add a skill", "fix a hook") are NOT role memory — leave those in the retro's Action Items.

This is the only place the orchestrator itself writes `memory/**`; the role agents write their own
change-scoped file inline at end of phase.
