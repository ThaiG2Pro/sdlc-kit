---
title: Security & Logging Rules
version: 1.2.0
scope: all-projects
enforcement: CRITICAL — violation = code rejection
inclusion: fileMatch
fileMatchPattern: '**/*.{ts,tsx,js,jsx,mjs,cjs,vue,php,py,go,rb,java,kt,sql}'
---

<!-- Not always-included: these rules bind CODE, so they load when a source file is in context
(dev/QA), not on every analyst/architect/orchestrator spawn. developer.md R6 and qa.md R4 also
name this file explicitly, so a role that needs it can always read it by path. -->


# Security & Logging Rules

## 🔴 Zero Tolerance — NEVER Generate

- Hardcoded secrets (API keys, tokens, passwords, connection strings)
- Passwords/tokens in logs
- `eval()`, `Function()`, `innerHTML =` in production code
- SQL string concatenation

### Secret Pattern Blacklist

```
AWS keys:      AKIA[0-9A-Z]{16}
GitHub tokens: ghp_[A-Za-z0-9]{36}
JWT tokens:    eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+
Generic:       (password|secret|api[_-]?key|token)\s*[:=]\s*["'][^"']{8,}
```

## ✅ Required Patterns

- ALL secrets via environment variables
- ALL external input validated at boundary
- Parameterized queries (no string concat for SQL)
- `.env` in `.gitignore`
- `.env.example` with placeholder values only

## Logging

JSON structured logging. Required fields: `request_id`, `timestamp`, `level`, `message`, `context`

Optional: `user_id`, `action`, `duration_ms`, `error_stack`, `metadata`

Log levels: `error` (immediate attention), `warn` (warning), `info` (business events), `debug` (dev only)

❌ NEVER log: passwords, tokens, credit cards, PII (unless masked)

✅ PII masking required:
```
logger.info('User login', { user_id: user.id, email: maskEmail(user.email) })
```

## OWASP Top 10 Compliance

- A01: Broken Access Control → RBAC
- A02: Cryptographic Failures → HTTPS, encrypt sensitive data
- A03: Injection → parameterized queries, validate input
- A04: Insecure Design → security-by-design
- A05: Security Misconfiguration → secure defaults, no debug in prod
- A06: Vulnerable Components → dependency updates, Trivy scan
- A07: Authentication Failures → strong password policy
- A08: Software Integrity → verify dependencies
- A09: Logging Failures → structured logging, monitor security events
- A10: SSRF → validate URLs, whitelist domains

## AI Self-Check Before Code Generation

1. No hardcoded secrets
2. All sensitive config uses env vars
3. No passwords/tokens in logs
4. Input validation present
5. Parameterized queries for SQL
6. `.env.example` has no real secrets
