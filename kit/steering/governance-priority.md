---
title: Governance Priority Chain
version: 1.0.0
scope: all-projects
status: authoritative — read this BEFORE any rule conflict
last_reconciled: 2026-05-07
reconciled_against_specs: [71086, 71143, 71194, 71280]
---

# Governance Priority Chain

When rules, docs, and parity requirements conflict, apply this priority order:

| # | Concern | Source | Yieldable? |
|---|---------|--------|-----------|
| 1 | **Security / data safety** | `R-SEC-001` to `R-SEC-003` | ❌ Never — zero tolerance |
| 2 | **Correctness / PHP parity** | Per-spec ADRs, `requirements.md` | ❌ For `/v6.0/*` endpoints — parity is contract |
| 3 | **API contract** | Locked at SPEC LOCK | ❌ Once locked, downstream follows |
| 4 | **DDD boundaries** | `dependency-rules.md`, `domain-guidelines.md` | ⚠️ Yieldable to parity (see exceptions) |
| 5 | **Architectural style** | `aggregate-design.md`, `ports-design.md` | ⚠️ Yieldable to parity (procedural vs aggregate) |
| 6 | **Code style / formatting** | Linters, conventions | ⚠️ Last priority |

## Source of Truth Hierarchy

This is a **parity port project**. Two distinct sources of truth coexist:

### WHAT — Behavior contract (for `/v6.0/*` endpoints)

| Tier | Source | Path |
|------|--------|------|
| 1 (ultimate) | Live PHP code | `{{LEGACY_REF_PATH}}` (separate repo) |
| 2 (digest) | PHP behavior docs | `docs/knowledge/SPEC-*.md` per endpoint |
| 3 (snapshot) | Per-spec requirements | `specs/<ticket>/requirements.md` at SPEC LOCK time |
| 4 (audit) | ADRs with PHP cites | per-spec design.md ADR sections citing `file:line` |

**Conflict rule**: When tier 2-4 conflict with tier 1 → PHP wins. Update tier 2 (digest) and re-validate tier 3-4.

### HOW — Node implementation patterns

| Tier | Source | Path |
|------|--------|------|
| 1 (code) | Live Node code | `src/` current state |
| 2 (descriptive) | Implementation docs | `docs/aggregate-design.md`, `docs/ports-design.md`, `docs/php-to-nodejs-mapping.md`, `docs/domain-guidelines.md` |
| 3 (cross-spec) | Established patterns | `specs/_cross-spec-context.md` § Established Patterns |
| 4 (governance) | This doc + rules-registry | `.kiro/steering/governance-priority.md`, `.kiro/steering/rules-registry.md` |

**Update rule**: When tier 1 evolves → update tier 2-4 per `_governance-reconcile-plan.md` cadence.

### CRITICAL: never confuse the two

The Established Patterns in `_cross-spec-context.md` are **labeled** as either **WHAT** (parity-frozen) or **HOW** (Node-evolvable). Example:
- Pattern E2 "HTTP 200 + body errors for /v6.0/*" = **WHAT** — PHP behavior, do NOT change
- Pattern E7 "ITransactionManager port for write use cases" = **HOW** — Node implementation choice, may evolve

Mixing the two leads to silent governance drift: someone "improves" a HOW pattern thinking it's a WHAT contract (or vice versa). When in doubt, check the pattern's WHAT/HOW label.

## When to invoke this

- **During /s3 design**: architect cites this doc when writing ADRs that accept rule deviation
- **During /s4 implementation**: developer cites this doc when code looks "wrong" per a rule
- **During /s5 QA**: tester cites this doc when a filed bug actually represents accepted deviation
- **During /s1-/s2 analyst**: analyst cites this doc when defining ACs that deviate from greenfield rule (must reference PHP source per Tier 2)

## Doc status taxonomy

Every governance doc carries a `Status:` header:

| Status | Meaning | Trust level |
|--------|---------|-------------|
| **authoritative** | Authoritative source — must follow (e.g., this doc, `governance-priority.md`) | High |
| **descriptive** | Describes actual codebase pattern as of last reconcile | High (within reconcile scope) |
| **aspirational** | Describes target/idealized state — codebase may not match | Reference only |
| **stale** | Known out-of-sync — DO NOT trust until reconciled | None |

When you see `aspirational` or `stale`, the codebase is NOT obligated to match. Reconcile cadence: see `_governance-reconcile-plan.md`.

## Legacy parity port endpoints

These 4 endpoints follow **PHP source contract**, NOT greenfield rules:

- `POST /v6.0/checkmultiple` — 71143 (standard) + 71194 (conditional)
- `POST /v6.0/reserved` — 71280
- `POST /v6.0/usemultiple` — SPEC-05 (pending)
- `POST /v6.0/unreserved` — SPEC-06 (pending)

For these endpoints, **parity > rule**. Each spec's ADRs document the accepted deviations from greenfield rules. New `/v1/*` endpoints (when added) MUST follow rules strictly.

## Established conflict patterns (with resolutions)

| Pattern | Greenfield rule | Legacy parity behavior | Resolution |
|---------|-----------------|------------------------|------------|
| HTTP status for errors | `R-API-001`: 4xx/5xx + `{errors, meta}` | All HTTP 200 + `{success, return_code, ...}` | ADR per spec accepting deviation. See 71143 ADR-005, 71280 ADR-004. |
| Command calling Query | `dependency-rules.md`: forbidden | Reserve/Use/Unreserve internally call Check via `callInternal=true` | ADR per spec. See 71280 ADR-003, 71194 ADR-001. Scope = post-processing toggle only, NOT brute-force skip. |
| Lock fail mapped to domain error | "Lock fail ≠ domain error" | Lock exhaustion → `UNDEFINED (999)` (catalog frozen, no new codes) | ADR per spec. See 71280 ADR-005, 71086 BR-71086-014. |
| Aggregate as class | `aggregate-design.md` prescribes `VoucherAggregate.reserve()` | 4 specs in a row built procedural services | Aspirational doc reconcile post-71280. See 71280 ADR-001. |
| Bounded context calls | "Cross-context calls đi qua Application layer" | `RedeemConditionInfo` is local `const` passed as parameter | Inherited from 71194 ADR. |

## Reconcile cadence

After each spec ships:
1. Add 1-block entry to `_cross-spec-context.md` (Dependencies, Decisions, Exports, Constraints)
2. Re-verify `php-to-nodejs-mapping.md` against actual file paths (add to `pending reconcile` list if drifted)
3. Run quarterly (or every 3 specs): full Phase 1-3 of `_governance-reconcile-plan.md` (~2 hours)

## When this doc is wrong

If `governance-priority.md` itself ever conflicts with a SPEC LOCK decision: spec wins, then this doc must be updated to record the new pattern as established.

If team disagrees with the "parity > DDD style" priority: open discussion with stakeholders. Do NOT silently override — this doc is authoritative until updated.

## See also

- `_governance-reconcile-plan.md` — execution plan for keeping rules/docs in sync with codebase
- `rules-registry.md` — index of all canonical rule IDs
- `_cross-spec-context.md` — per-spec dependencies and exports
