---
name: assumption-detector
description: >
  Scan requirements/user input for hidden assumptions and cognitive blind spots.
  Filters out generic infrastructure boilerplate. Outputs actionable tagged list:
  [RISKY:KNOWN_UNKNOWN] (questions to resolve), [RISKY:UNKNOWN_UNKNOWN_RISK] (latent edge hazards),
  and [SAFE] (documented facts). Use during S1 after gathering knowledge, before writing proposal.md.
---

# Assumption Detector (Cognitive Blind-Spot Hunter)

## When to Use
- S1 Step 4a (after gathering knowledge in Step 2, before clarification)
- When user provides vague, brief, or deceptively simple requirements

## Input
- User's feature description / ticket payload
- Existing domain specs & `context/glossary.md`
- Target codebase entity definitions

## Process & Detection Passes

Scan input across these 5 domain-critical categories (Prioritize **High-Risk**: Money, Auth, Data Integrity, Concurrency):

1. **Permission & Actor Assumptions** — "only admin can do this", "authenticated user owns resource"
   - Check: what happens if role changes mid-session? Can user A access user B's resource?
2. **Data & State Assumptions** — "status is always active/pending", "user email is unique"
   - Check: what if record is soft-deleted? What if parent entity is archived?
3. **Concurrency & Timing Assumptions** — "user clicks once", "operations happen sequentially"
   - Check: double-submit, race conditions on balance/inventory, webhook delivered out of order.
4. **Integration & Third-Party Boundaries** — "external API returns success", "token never expires"
   - Check: rate limits, partial responses, timeout retry storms.
5. **Business Rule Extremes** — "discount cannot exceed 100%", "start date is before end date"
   - Check: boundary values (0, negative, max INT), localized timezones, conflicting coupons.

## 🚫 Anti-Boilerplate Mandate (Strict Negative Filter)
**NEVER output generic infrastructure or trivial boilerplate:**
- ❌ *"Assumption: Network connection might drop"* (Banned)
- ❌ *"Assumption: Database server might crash"* (Banned)
- ❌ *"Assumption: User has a modern browser"* (Banned)
Every detected assumption MUST point to a **concrete business domain hazard** or **state inconsistency**.

## Output Format

```markdown
## Assumptions Detected

### [RISKY:KNOWN_UNKNOWN] — Direct Questions needing User Decision
- A1: {domain assumption} — Impact: {business failure if wrong} — Question: {concrete question to ask}
- A2: ...

### [RISKY:UNKNOWN_UNKNOWN_RISK] — Latent Hazards to Harden in Architecture/QA
- R1: {concurrency/state hazard} — Impact: {data corruption/security breach} — Proposed Guard: {architect/dev action}
- R2: ...

### [SAFE] — Documented & Confirmed
- S1: {assumption} — Source: {file path / table definition / existing spec}
```

## Rules
- Maximum 5-7 assumptions total (quality & impact over volume).
- High-Risk domains (Auth, Money, DB Schema) MUST have zero unaddressed `[RISKY]` tags before Spec Lock.
- Low-Risk domains (UI styling, minor helpers) apply Sensible Defaults instead of blocking.
