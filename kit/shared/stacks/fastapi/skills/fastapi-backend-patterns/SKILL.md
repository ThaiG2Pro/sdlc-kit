---
name: fastapi-backend-patterns
description: >
  FastAPI service and repository layer patterns: async SQLAlchemy 2.x,
  repository abstraction, background tasks, exception handling, and
  dependency injection conventions for {{PROJECT_TITLE}}.
---

# FastAPI Backend Patterns

Standard patterns for the service and repository layers in {{PROJECT_TITLE}}.

## Repository Pattern

Keeps DB queries out of service logic. One repository per ORM model:

```python
# app/users/repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.users.model import User

class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, name: str, email: str, hashed_password: str) -> User:
        user = User(name=name, email=email, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.commit()
```

## Service Layer

Business logic only — no direct DB access, no HTTP concerns:

```python
# app/users/service.py
from fastapi import HTTPException, status
from app.users.repository import UserRepository
from app.users.schema import CreateUserRequest, UserResponse

class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    async def create(self, body: CreateUserRequest) -> UserResponse:
        if await self.repo.find_by_email(body.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "EMAIL_ALREADY_EXISTS", "message": f"Email {body.email!r} is taken"},
            )
        user = await self.repo.create(name=body.name, email=body.email,
                                       hashed_password=hash_password(body.password))
        return UserResponse.model_validate(user)

    async def get_or_404(self, user_id: int) -> UserResponse:
        user = await self.repo.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail={"code": "USER_NOT_FOUND", "message": f"User {user_id} not found"})
        return UserResponse.model_validate(user)
```

## Wiring in Router

```python
# app/users/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.users.repository import UserRepository
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(body: CreateUserRequest, svc: UserService = Depends(get_user_service)):
    return await svc.create(body)
```

## SQLAlchemy Model (mapped columns, 2.x style)

```python
# app/users/model.py
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, func

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                  onupdate=func.now())
```

## Background Tasks

For fire-and-forget work (emails, webhooks) — use FastAPI `BackgroundTasks`:

```python
from fastapi import BackgroundTasks

@router.post("/users/{id}/send-welcome")
async def send_welcome(id: int, background_tasks: BackgroundTasks,
                       svc: UserService = Depends(get_user_service)):
    user = await svc.get_or_404(id)
    background_tasks.add_task(send_welcome_email, user.email, user.name)
    return {"queued": True}
```

For heavy/distributed work, use Celery or arq — not `BackgroundTasks`.

## Pagination

```python
# app/core/pagination.py
from pydantic import BaseModel
from dataclasses import dataclass

@dataclass
class PaginationParams:
    page: int = 1
    per_page: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

class PaginatedResponse(BaseModel):
    data: list
    meta: dict  # {"page": N, "per_page": N, "total": N}
```

## Error Handling — Global Handler

```python
# app/main.py
from sqlalchemy.exc import IntegrityError
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409,
                        content={"error": {"code": "CONFLICT", "message": "Resource already exists"}})
```

## Checklist for S4 Implementation

- [ ] Repository never raises HTTPException — only returns None or raises DB-level errors
- [ ] Service layer owns all business rules and raises HTTPException
- [ ] Router functions contain only: parse body, call service, return response
- [ ] All DB calls are `await`ed; no sync SQLAlchemy calls
- [ ] `async_session_maker` used for session creation — no `sessionmaker` (sync)
- [ ] ORM models use SQLAlchemy 2.x `Mapped[T]` syntax
- [ ] `model_validate` (not `from_orm`) used on Pydantic v2 response schemas
