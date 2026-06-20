---
title: API Standards
version: 1.1.0
scope: greenfield endpoints only — see Scope section
status: descriptive
last_reconciled: 2026-05-07
---

# API Standards

## Scope

**Applies to**: New endpoints (e.g., `/v1/admin/*`, `/v1/internal/*`).

**Does NOT apply to**: Legacy parity ports under `/v6.0/*` — `checkmultiple`, `reserved`, `unreserved`, `usemultiple`. These follow PHP source contract:
- HTTP 200 always (success AND business errors)
- Response shape: `{success, return_code, message_en, message_vi, data, ...}` (NOT `{data, meta}` / `{errors, meta}`)
- See per-spec ADR for evidence: 71143 ADR-005, 71280 ADR-004

**Why this scope exists**: Parity contract is locked by production POS clients. Cannot be changed without coordinated multi-month POS migration. See `governance-priority.md` for priority chain.

When in doubt: any endpoint NOT under `/v6.0/` follows this doc strictly.

## Response Format

### Success (2xx)
```json
{
  "data": {},
  "meta": { "timestamp": "", "path": "", "method": "" }
}
```

### Success + Pagination
```json
{
  "data": [],
  "meta": {
    "timestamp": "", "path": "", "method": "",
    "pagination": { "page": 1, "limit": 20, "total": 150, "totalPages": 8 }
  }
}
```

### Error (4xx, 5xx)
```json
{
  "errors": [{ "code": "", "message": "", "field": "" }],
  "meta": { "timestamp": "", "path": "", "method": "", "statusCode": 400 }
}
```

## HTTP Status Codes
- `200` OK (GET, PUT, PATCH)
- `201` Created (POST)
- `204` No Content (DELETE)
- `400` Bad Request
- `401` Unauthorized
- `403` Forbidden
- `404` Not Found
- `409` Conflict
- `422` Unprocessable Entity
- `429` Too Many Requests
- `500` Internal Server Error

## Critical Rules
- ❌ NEVER return 200 for errors
- ❌ NEVER return error messages in `data` field
- ✅ ALWAYS use appropriate HTTP status codes
- ✅ ALWAYS include `errors` array for error responses

## URL Conventions
- Resource naming: plural nouns, kebab-case
- Nested resources: max 2 levels
- Versioned: `/v1/`, `/v2/`
