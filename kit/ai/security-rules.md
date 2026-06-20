# Security Rules — {{PROJECT_TITLE}}

## Authentication
- PIN-based authentication (backward compatible with PHP)
- PIN stored plaintext in DB (deferred: hash migration Phase 2)
- Brute force protection: IP + store-based lockout
- API Key + HMAC auth: deferred Phase 2

## Rate Limiting
- @nestjs/throttler with Redis backend
- Global: 1000 req/min per IP
- Per-endpoint configurable
- Return 429 with Retry-After header

## Input Validation
- Zod schemas on ALL request bodies
- Reject unknown fields (strict mode)
- Enforce Content-Type: application/json
- Sanitize string inputs (trim whitespace)

## PII & Sensitive Data
- NEVER log: passwords, PINs, voucher codes (plaintext), tokens
- Pino redact config: `['pin', 'codes', 'codes.*', 'bill_number']`
- Mask emails in logs: `u***@example.com`
- Use request_id for log correlation

## SQL Injection Prevention
- Prisma parameterized queries by default
- NEVER use string concatenation for queries
- No raw SQL unless absolutely necessary (use Prisma.$queryRaw with parameters)

## External Service Calls
- HTTP Adapters for all external services
- Validate response schemas
- Timeout + retry with exponential backoff
- Use crypto.randomUUID() for request IDs (not md5/uniqid)

## Security Headers
- helmet middleware (via NestJS)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-Request-Id on all responses

## Secrets Management
- All secrets via environment variables
- .env.example with placeholder values only
- .env in .gitignore
- No secrets in logs, error messages, or responses
