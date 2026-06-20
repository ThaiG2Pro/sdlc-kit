# Backend Rules — NestJS + Fastify + Prisma + DDD

## API Design
- Zod 4 schemas for all request/response validation (via NestJS Pipes)
- Thin controllers: validate → delegate to command/query → serialize response
- Consistent error format: `{ success, return_code, message_en, message_vi, data }`
- Response must be IDENTICAL to PHP system (response parity)
- PHP returns HTTP 200 for business errors — giữ nguyên

## Use Case Rules
- 3 Command Use Cases (*.command.ts): ReserveVoucher, UseVoucher, UnreserveVoucher
- 1 Query Use Case (*.query.ts): CheckVoucherQuery
- Commands: have transaction + lock, throw domain errors
- Query: NO transaction, NO lock, errors as DATA not exceptions
- Commands KHÔNG gọi Query. Cả hai gọi domain services trực tiếp.

## DDD Layer Rules
- Domain services: pure logic, no Prisma/Redis/HTTP imports
- Application commands/queries: orchestrate domain services, manage transactions
- Infrastructure: implement port interfaces, repository pattern for DB access
- Interface: Zod schemas, serializers, NestJS Guards/Interceptors/Pipes
- Merchant Access BC: produce MerchantContext via NestJS Guard

## Aggregate Rules
- VoucherAggregate: state + behavior only, no DB access
- Aggregate methods self-validate invariants (Option B — assert private)
- State change ONLY through public command methods (reserve, unreserve, markUsed)
- 8 invariants defined in docs/aggregate-design.md

## Port Rules
- 7 ports defined in docs/ports-design.md
- Port interfaces in application layer, implementations in infrastructure
- Don't add port methods without a use case calling them

## Error Handling
- Domain errors → Use Case catch → map to API error code
- Query errors → return as DATA, not exceptions
- Lock fail → 503 retryable (NOT domain error)
- See docs/design/error-model.md for complete mapping

## Performance
- Async/await for all I/O operations
- Redis for caching, distributed locks, budget counters
- Cache key format MUST match PHP system exactly
- Events dispatch AFTER transaction commit (async, non-blocking)

## Concurrency
- Redis SETNX for distributed locks per product (budget)
- SELECT FOR UPDATE for voucher row lock (in transaction)
- BudgetService: Redis atomic HINCRBY, Application layer commits
- Lock BEFORE transaction, release in finally block

## Observability
- Pino structured JSON logging (nestjs-pino)
- OpenTelemetry tracing (@opentelemetry/sdk-node)
- Prometheus metrics (prom-client)
- Mask sensitive data: pin, codes, bill_number

## References
- docs/design/dependency-rules.md — layer boundaries
- docs/design/transaction-and-consistency.md — atomic vs eventual
- docs/design/implementation-constraints.md — 38 hard rules
- docs/design/anti-patterns.md — what NOT to do
