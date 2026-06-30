---
name: fastapi-api-design
description: >
  FastAPI REST API design: endpoint structure, request/response schemas,
  OpenAPI spec, dependency injection patterns, and error handling aligned
  with the project's conventions.md. Use during S3 Design.
---

# FastAPI API Design

Design REST API endpoints for {{PROJECT_TITLE}} following FastAPI patterns and the project's `context/conventions.md`.

## When to Use

During S3 Design when the change includes new or modified HTTP endpoints.

## Router Structure

Each domain gets its own `APIRouter`. Register it in `app/main.py`:

```python
from app.users.router import router as users_router
app.include_router(users_router, prefix="/api/v1")
```

Router file (`app/users/router.py`):
```python
from fastapi import APIRouter, Depends, status
from app.users.schema import CreateUserRequest, UserResponse
from app.users.service import UserService
from app.core.deps import get_current_user, get_db

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
             summary="Create a new user")
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> UserResponse:
    return await UserService(db).create(body)
```

## Pydantic Schemas

One schema file per domain. Separate request from response:

```python
# app/users/schema.py
from pydantic import BaseModel, EmailStr, ConfigDict

class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
```

## Dependency Injection Patterns

```python
# app/core/deps.py
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    ...  # decode JWT, load user
```

## Error Responses

Raise `HTTPException` from service layer; never from repositories:

```python
from fastapi import HTTPException, status

# 404
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "USER_NOT_FOUND", "message": f"User {id} not found"})

# 409
raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "EMAIL_ALREADY_EXISTS", "message": "Email is taken"})
```

## Checklist for S3 Design

- [ ] All endpoints defined in `openapi.yaml` (OpenAPI 3.0)
- [ ] Every endpoint has `response_model`, `status_code`, `summary`
- [ ] Request schemas validated with Pydantic (no raw `dict` params)
- [ ] Paginated list endpoints use consistent `meta.page / meta.total` shape
- [ ] Auth endpoints documented with `securitySchemes`
- [ ] Error responses documented for 400/401/403/404/409/422
- [ ] All schemas follow naming convention: `{Action}{Resource}Request`, `{Resource}Response`

## OpenAPI spec

Write the `openapi.yaml` for the change — FastAPI also auto-generates one at `/openapi.json` but the kit requires a committed `openapi.yaml` for the S3 gate. Generate a draft from the running app:

```bash
python -c "
import json, yaml
from app.main import app
print(yaml.dump(app.openapi(), default_flow_style=False))
" > openspec/changes/{change-name}/openapi.yaml
```

Then review and clean up the generated YAML.
