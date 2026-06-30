<!-- TODO: adapt URL versioning and error shape to your project's actual conventions -->
# Conventions: FastAPI

## URL Structure
- Versioned prefix: `/api/v{N}/{resource}`
- Plural nouns: `/api/v1/users`, `/api/v1/orders`
- Nested resources: `/api/v1/users/{user_id}/orders/{order_id}`
- Kebab-case for multi-word resources: `/api/v1/order-items`

## Response Shape

### Success (single resource)
```json
{ "data": { "id": 1, "name": "..." } }
```

### Success (paginated list)
```json
{
  "data": [ ... ],
  "meta": { "page": 1, "per_page": 20, "total": 145 }
}
```

### Error
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "User with id 42 not found",
    "details": []
  }
}
```

Validation errors (422) use the `details` array:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      { "field": "email", "message": "value is not a valid email address" }
    ]
  }
}
```

## HTTP Status Codes
- 200 OK — read operations, updates
- 201 Created — resource created; include `Location` header
- 204 No Content — delete
- 400 Bad Request — semantic validation failure (business rule)
- 401 Unauthorized — missing or invalid auth token
- 403 Forbidden — authenticated but lacks permission
- 404 Not Found — resource not found
- 409 Conflict — duplicate resource or state conflict
- 422 Unprocessable Entity — Pydantic / field-level validation failure
- 500 Internal Server Error — unexpected; never expose stack trace

## Dependency Injection
- DB session: `db: AsyncSession = Depends(get_db)` — one session per request, auto-closed
- Current user: `current_user: User = Depends(get_current_user)`
- Pagination: `pagination: PaginationParams = Depends()` (page + per_page)
- Repository pattern: `UserRepository(db)` — inject db, not the repo itself
- Never import services/repos directly in routers — always via `Depends`

## Async Rules
- ALL route handlers, service methods, and repository methods MUST be `async def`
- Use `await` for every DB call; never call `.all()` / `.first()` without await on async queries
- Background tasks via `BackgroundTasks` or Celery — never `asyncio.create_task` in request handlers

## Naming Conventions
| File | Pattern |
|------|---------|
| Router | `{domain}_router.py` |
| Schema | `{domain}_schema.py` |
| Service | `{domain}_service.py` |
| Repository | `{domain}_repository.py` |
| ORM model | `{domain}_model.py` |
| Test file | `test_{domain}_{layer}.py` |

## Pydantic Models
- Request schema: `{Action}{Resource}Request` (e.g. `CreateUserRequest`)
- Response schema: `{Resource}Response` (e.g. `UserResponse`)
- Use `model_config = ConfigDict(from_attributes=True)` on response schemas for ORM compatibility
- Never expose ORM models directly as responses

## Error Handling
- Raise `HTTPException(status_code=..., detail=...)` from services — routers catch and return
- Create custom exception classes for domain errors; add a global exception handler in `main.py`
- Never let SQLAlchemy exceptions bubble to the client — catch `IntegrityError` → 409

## OpenAPI
- Tag every router: `router = APIRouter(prefix="/users", tags=["Users"])`
- Add `summary=` and `description=` to complex endpoints
- Use `response_model=` on all route decorators
