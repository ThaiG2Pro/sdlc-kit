<!-- TODO: review and complete for your project — fill in actual versions and commands -->
# Stack: FastAPI

## Runtime
- Python 3.11+
- FastAPI 0.110+
- Uvicorn (ASGI server)

## Database
- SQLAlchemy 2.x async ORM (mapped columns, `AsyncSession`)
- Alembic (migrations)
- PostgreSQL (primary data store) / SQLite (dev/test)
- asyncpg driver

## Validation & Serialization
- Pydantic v2 (request/response models, `model_config`)
- pydantic-settings (`.env` config management)

## Authentication
- JWT via python-jose or PyJWT
- OAuth2PasswordBearer scheme

## Testing
- pytest + pytest-asyncio
- httpx `AsyncClient` (test HTTP client — no test server needed)
- pytest-mock / respx (async HTTP mocking)
- Coverage: pytest-cov (target ≥ 80% lines, ≥ 90% diff)

## Quality
- ruff (lint + format — replaces flake8/black/isort)
- mypy (type checking, strict mode recommended)

## Project Layout
```
app/
  main.py               # FastAPI app factory, router registration
  core/
    config.py           # pydantic-settings Settings class
    security.py         # JWT helpers, password hashing
    database.py         # engine, session factory, get_db dependency
  {domain}/
    router.py           # APIRouter for this domain
    service.py          # business logic (async methods)
    repository.py       # DB queries (SQLAlchemy)
    schema.py           # Pydantic request/response models
    model.py            # SQLAlchemy ORM model
  tests/
    conftest.py         # AsyncClient fixture, test DB setup
    test_{domain}.py    # pytest test files
alembic/
  env.py
  versions/
```

## Dev Commands
```bash
# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=term-missing

# Type check
mypy app/

# Lint
ruff check app/

# Format
ruff format app/

# New migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```
