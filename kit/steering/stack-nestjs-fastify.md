---
title: NestJS + Fastify Conventions
stack: nestjs-fastify
status: descriptive
last_reconciled: 2026-05-07
reconciled_against_specs: [71086, 71143, 71194, 71280]
---

# NestJS + Fastify Conventions

## Naming

- Files: `kebab-case.ts` (`user-profile.service.ts`)
- Classes: `PascalCase` (`UserService`, `OrderController`)
- Interfaces: `I` prefix (`IUserRepository`)
- Types: `PascalCase` (`UserRole`)
- Functions/Variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE`
- Enums: `PascalCase` name, `UPPER_SNAKE_CASE` values
- DB tables/columns: `snake_case`
- Indexes: `idx_{table}_{columns}`
- Foreign keys: `fk_{table}_{ref_table}`

## API Prefix

Host đã có `/api` prefix. Controller chỉ khai báo từ sau `/api`:

```typescript
// ✅ Đúng — greenfield
@Controller('internal/v1/brands')   // → {host}/api/internal/v1/brands
@Controller('v1/products')          // → {host}/api/v1/products

// ✅ Đúng — legacy parity ports
@Controller('v6.0/reserved')        // → {host}/api/v6.0/reserved
@Controller('v6.0/checkmultiple')   // → {host}/api/v6.0/checkmultiple

// ❌ Sai — double prefix
@Controller('api/internal/v1/brands')
```

## OpenAPI (Bắt buộc)

```typescript
@ApiTags('products')
@Controller('internal/v1/products')
export class ProductController {
  @Get()
  @ApiOperation({ summary: 'Get all products' })
  @ApiResponse({ status: 200, type: [ProductDto] })
  async findAll() {}
}
```

DTOs phải có `@ApiProperty`:
```typescript
export class CreateProductDto {
  @ApiProperty({ description: 'Product name', example: 'iPhone 15' })
  @IsString()
  @IsNotEmpty()
  name: string;
}
```

## Validation

```typescript
app.useGlobalPipes(new ValidationPipe({
  whitelist: true,
  forbidNonWhitelisted: true,
  transform: true,
}));
```

## Database

- ORM: **Prisma** (corrected 2026-05-07 reconcile — was incorrectly listed as TypeORM; actual codebase uses Prisma per 71086 ADR-001)
- Schema source: `prisma db pull` from existing MySQL `gotit` database (legacy schema)
- Schema is **FROZEN** for legacy tables — DO NOT alter via Prisma migrations
- For new tables (greenfield only): Prisma migrations via `prisma migrate dev` + manual SQL review
- Mọi schema change qua migration — không SQL thủ công
- Migration không edit sau deploy — tạo mới nếu cần sửa

## Testing

- Framework: Jest + SWC
- Coverage: ≥ 80%
- Unit tests: mock external deps
- Integration tests: real DB, KHÔNG mock database

## Architecture

- Controllers thin — chỉ validate + delegate
- Business logic trong services
- Persistence trong repositories
- Config qua `ConfigService` / `process.env`
