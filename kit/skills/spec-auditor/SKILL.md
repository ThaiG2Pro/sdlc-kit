---
name: spec-auditor
description: >
  Audit requirements.md before SPEC LOCK gate. Checks AC completeness, testability,
  no TBD/UNCLEAR tags, Figma URL, edge cases count, AC-ID format.
  Read-only — produces PASS/FAIL report, no file edits.
  Run by SDLC orchestrator when user approves S2 gate.
---

# Spec Auditor

## Scope
Audit ONLY `requirements.md`. Does NOT touch design.md, openapi.yaml, tasks.md, or code.

## Input
- `{SPEC_DIR}/requirements.md`

## Checks

### C1: No open tags (BLOCKER)
Scan for: `[TBD]`, `[UNCLEAR]`, `[MISSING]`
- Any found → FAIL, list line numbers

### C2: AC testability (BLOCKER)
For each AC, check description has:
- Concrete input/output or condition/result
- No vague words: "should work", "should be fast", "user-friendly", "appropriate"
- Any vague AC → FAIL, list AC-IDs

### C3: AC-ID format (BLOCKER)
All AC-IDs must match: `AC-{ticket_id}-{NNN}` (3-digit zero-padded)
- Wrong format → FAIL, list offenders

### C4: Edge cases count (WARNING)
Count items under "Edge Cases" section
- < 10 → WARNING (not blocker, but flag)

### C5: Figma URL (WARNING)
Check for "Figma Design" section
- Missing AND no "Figma: N/A" → WARNING

### C6: Scope closed (BLOCKER)
Check for "Out of Scope" section
- Missing → FAIL

## Output Format

```
## Spec Audit — {ticket_id}-{feature-slug}

### Result: PASS ✅ / FAIL ❌

| Check | Status | Detail |
|-------|--------|--------|
| C1: No open tags | ✅/❌ | {list or "None"} |
| C2: AC testability | ✅/❌ | {list or "All clear"} |
| C3: AC-ID format | ✅/❌ | {list or "All correct"} |
| C4: Edge cases | ✅/⚠️ | {count} found |
| C5: Figma URL | ✅/⚠️ | {present/missing} |
| C6: Scope closed | ✅/❌ | {present/missing} |

### Blockers (must fix before SPEC LOCK)
- {list or "None"}

### Warnings (recommended to fix)
- {list or "None"}
```

FAIL = any BLOCKER check fails. WARNING does not block gate.
