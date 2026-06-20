# AI Rules — {{PROJECT_TITLE}} (Node.js)

## Rule Priority (highest → lowest)
1. **Security** — no secrets, no injection, no PII leaks
2. **Correctness** — business logic matches PHP system exactly
3. **API Contract** — response parity with PHP (identical format)
4. **DDD Boundaries** — domain layer has zero external dependencies
5. **Simplicity** — minimal code, clear intent
6. **Performance** — efficient queries, proper caching
7. **Style** — naming conventions, formatting

## General Behavior
- Read ROADMAP.md for spec-driven vertical slices
- Read docs/design/ for architecture constraints, error model, anti-patterns
- Read docs/knowledge/SPEC-XX.md for PHP logic details per spec
- Read docs/domain-guidelines.md before writing domain code
- Preserve existing patterns — do not refactor unless explicitly asked
- Make minimal, safe changes
- Do not invent business behavior not present in PHP source or spec

## Code Generation Rules
- Match DDD 4-layer structure exactly
- Domain files MUST NOT import from infrastructure/ or interface/
- VoucherAggregate = state + behavior only, no DB access, no API shape
- Aggregate methods self-validate invariants (Option B — assert private)
- BudgetService does NOT self-commit — Application layer manages transactions
- Auth/BruteForce live in Merchant Access BC (domain/merchant-access/), produce MerchantContext via NestJS Guard
- 3 Command Use Cases (*.command.ts) + 1 Query Use Case (*.query.ts)
- Query Use Case: NO transaction, NO lock, errors as DATA not exceptions
- All external service calls go through Adapters (Infrastructure)
- VoucherCoreService: Prisma queries + HTTP call (not just DB)
- gotit-event: bridge worker for PHP serialize compat

## Backend Rules
- NestJS controllers + Zod validation (via Pipes) at Interface layer
- Prisma parameterized queries only — no raw SQL string concat
- Redis for cache — key format MUST match PHP system
- Pino for logging — redact sensitive fields

## Database Rules
- Existing MySQL gotit DB — schema KHÔNG thay đổi
- `prisma db pull` to introspect, no manual migrations
- Use Prisma Client for all queries

## Cache Rules
- Redis key format: `{PREFIX}{key}_{APP_ENV}` with MD5 fallback
- Must be cross-compatible with PHP cache (read/write both directions)
- Budget counters: Redis HINCRBY (atomic)

## Security Reference
- See `/.kiro/steering/security-enforcement.md`
- See `/.kiro/ai/security-rules.md`
- See `/docs/design/error-model.md` for error categories + mapping
- See `/docs/design/implementation-constraints.md` for 38 hard rules
- See `/docs/design/anti-patterns.md` for what NOT to do
