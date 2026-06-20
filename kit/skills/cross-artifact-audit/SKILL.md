---
name: cross-artifact-audit
description: >
  Cross-artifact consistency audit between requirements.md, design.md, openapi.yaml, and tasks.md.
  Inspired by SpecKit's speckit.analyze. Detects: coverage gaps (AC without task), orphan tasks
  (task without AC), terminology drift, API contract mismatches, DB schema gaps.
  Run between S3→S4 (before build) or S4→S5 (before QA). Read-only — produces report, no file edits.
---

# Cross-Artifact Audit

## When to Use
- After S3 (architect) completes design.md + tasks.md — before S4 build starts
- After S4 (developer) completes — before S5 QA starts
- When suspecting spec-code drift

## Execution

### Step 1: Load Artifacts
Read from SPEC_DIR (`specs/{ticket_id}-{feature-slug}/`):
- `requirements.md` — extract all AC-IDs, BR-IDs, INT-IDs from Structured Extract
- `design.md` — extract API endpoints, DB tables, error mappings
- `openapi.yaml` — extract paths, methods, request/response schemas
- `tasks.md` — extract all task items with AC-ID references and file paths

### Step 2: Build Coverage Matrix

| AC-ID | In requirements? | In design? | In openapi? | In tasks? | In code? | Status |
|-------|-----------------|------------|-------------|-----------|----------|--------|

For each AC-ID from requirements.md:
- Check if design.md references it
- Check if tasks.md has at least 1 task referencing it
- Check if openapi.yaml covers the endpoint (for API-related ACs)

### Step 3: Detection Passes

**A. Coverage Gaps** (CRITICAL)
- AC with 0 tasks → requirement will not be implemented
- AC with 0 design reference → requirement not designed

**B. Orphan Tasks** (HIGH)
- Task referencing no AC-ID → untraceable work
- Task referencing non-existent AC-ID → typo or stale reference

**C. API Contract Mismatch** (HIGH)
- Endpoint in design.md but missing from openapi.yaml
- Endpoint in openapi.yaml but not in design.md
- Response format not matching `{ data, meta }` / `{ errors, meta }` convention

**D. Terminology Drift** (MEDIUM)
- Same entity named differently across files (e.g., "product" vs "item")
- Inconsistent field names between design.md DB schema and openapi.yaml

**E. Task Ordering Issues** (MEDIUM)
- Test task before code task it tests
- Controller task before service task it depends on
- Missing checkpoint tasks (< 2 checkpoints)

### Step 4: Severity Assignment
- CRITICAL: AC with zero coverage, API contract mismatch
- HIGH: Orphan tasks, missing design reference
- MEDIUM: Terminology drift, ordering issues
- LOW: Style inconsistencies

### Step 5: Output Report

```markdown
## Cross-Artifact Audit Report — {ticket_id}
Date: {date}

### Coverage Matrix
| AC-ID | requirements | design | openapi | tasks | Status |
|-------|-------------|--------|---------|-------|--------|

### Findings
| # | Category | Severity | Location | Summary | Recommendation |
|---|----------|----------|----------|---------|----------------|

### Metrics
- Total ACs: {N}
- Covered (all artifacts): {X} ({X/N}%)
- Partial coverage: {Y}
- Zero coverage: {Z} ← BLOCKERS

### Recommendation
- {PROCEED / STOP — fix before continuing}
```

## Rules
- READ-ONLY — never modify artifacts
- Report findings, do not fix them
- If CRITICAL findings → recommend STOP before next phase
- Reference exact AC-IDs and file locations
