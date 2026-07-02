---
name: release-template
description: >
  Template for {CHANGE_DIR}/release.md — the S6 release artifact the developer writes before
  `openspec archive`. Contains: release notes (ref AC-IDs), migration checklist, rollback plan,
  post-deploy smoke test, deploy strategy.
---

# Release — {ticket_id} ({change-name})
Date: {ISO date}
Deploy strategy: {direct | canary | blue-green}

## Release Notes
**Features**
- {feature} (AC-{ticket}-{NNN}, …)

**Bug fixes**
- {fix} (AC-{ticket}-{NNN})

**Breaking changes**
- {none, or describe + migration note}

## Migration Checklist
| Order | Migration | up() | down() | Destructive? | Backup step |
|-------|-----------|------|--------|--------------|-------------|
| 1 | {migration name} | ✅ | ✅ | {no / yes} | {n/a or backup plan} |

## Rollback Plan
1. {step to revert the deploy}
2. {step to roll back migrations (run down() in reverse order)}
3. {how to confirm the system is back to the prior good state}

## Post-Deploy Smoke Test
- [ ] {critical path 1} → {expected}
- [ ] {critical path 2} → {expected}
- [ ] Health endpoint returns success + dependency checks green
- [ ] Error rate / latency within budget for {N} min

## Archive
- [ ] `openspec archive "{change-name}"` run — spec deltas merged into the living spec, change moved to openspec/changes/archive/
- [ ] `_state.json.deploy_status` initialized (one entry per real promotion env, e.g. `{"dev":"pending","stg":"pending","master":"pending"}`) — updated later, out-of-band, as each promotion actually completes (`state-set --set deploy_status.<env>=pass|fail`). Not a gate — a breadcrumb so a bug found in dev/stg/master traces back here.

## If Rejected After Archive (Revert Playbook)
Archive already ran BEFORE this reaches dev/stg/master — a bug caught downstream does NOT mean re-opening this change:
- **Forward-fixable** (bug found in dev/stg, or in master but no rollback needed): open a new `bugfix` (or `hotfix` if already in master) pipeline. Do not touch this archived change or hand-edit the living spec.
- **Real rollback** (the deploy itself gets reverted, not just patched forward): `git revert <archive-merge-commit>` — `openspec archive` is a plain-file commit (moves the change folder + edits the living spec.md), so reverting it undoes the code AND the spec fold atomically. Never hand-edit `openspec/specs/**` back to the old state — let `git revert` do both at once, then re-run the fix as its own pipeline.
