---
title: Git Commit Policy
version: 1.2.0
scope: all-projects
inclusion: manual
---

<!-- Not always-included: only the developer commits, and only at S4-end/S6. developer.md names
this file by path at those two points; `commit-message-helper` skill covers message drafting. -->

# Git Commit Policy

## Format

With ticket ID:
```
<type>(<scope>): <ticket-id> <subject>
```

Without ticket ID:
```
<type>(<scope>): <subject>
```

Optional body and footer:
```
[optional body]

[optional footer]
```

## Types

`feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert`

## Rules

- Subject: lowercase, imperative mood, no period, ≤ 100 chars
- Body: explain WHAT and WHY, not HOW
- Ticket ID: placed right after scope (e.g., `feat(order): GFT-123 add bulk import`)
- Scopes: project-specific (see `CLAUDE.local.md` → Commit)

## Pre-commit Checklist (AI Agent MUST follow)

### 1. Security Scan (BLOCKER)

```bash
git diff --unified=5
```

Check for:
- Hardcoded secrets: `API_KEY=`, `SECRET=`, `PASSWORD=`, `Bearer `, `sk_`, `AKIA`, `ghp_`, `eyJ`
- Dangerous patterns: `eval()`, `Function()`, `innerHTML =`, SQL string concat
- PII in logs
- `console.log` in production code

If BLOCKER found → **STOP**, do NOT commit.

### 2. Commit Message Format

Must follow conventional commits format.

### 3. Verify

- [ ] No unrelated files staged
- [ ] No `.env`, secrets, or build artifacts committed
- [ ] Commit message follows format

### 4. Pre-push

- [ ] Branch is NOT `main`/`master`/`production` — work on the pipeline's isolation branch/worktree (`{type}/{ticket}-{slug}`, see R-SDLC-003)
- [ ] Tests pass
