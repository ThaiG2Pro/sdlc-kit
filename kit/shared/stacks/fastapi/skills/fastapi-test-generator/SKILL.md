---
name: fastapi-test-generator
description: >
  Generate pytest test files for FastAPI endpoints and service layer,
  using httpx AsyncClient, pytest-asyncio, and the project's test fixtures.
  Produces AC-ID-traced tests aligned with spec deltas.
---

# FastAPI Test Generator

Generates pytest tests for {{PROJECT_TITLE}} — endpoint tests via `AsyncClient` and service unit tests via mocked repositories. All tests MUST reference AC-IDs from the change's spec deltas.

## Test File Structure

```
app/tests/
  conftest.py                  # shared fixtures
  test_{domain}_api.py         # HTTP-level endpoint tests
  test_{domain}_service.py     # service unit tests (mocked repo)
```

## conftest.py Fixtures

```python
# app/tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import async_session_maker, Base, engine

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    # Create a test user + obtain JWT, set Authorization header
    ...
    return client
```

## Endpoint Tests

```python
# app/tests/test_users_api.py
import pytest

class TestCreateUser:
    async def test_creates_user_with_valid_data(self, auth_client, AC="AC-{ticket}-001"):
        """Happy path — valid payload returns 201 (AC-{ticket}-001)."""
        resp = await auth_client.post("/api/v1/users", json={"name": "Alice", "email": "alice@example.com"})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["email"] == "alice@example.com"

    async def test_rejects_invalid_email(self, auth_client, AC="AC-{ticket}-002"):
        """Validation error on malformed email returns 422 (AC-{ticket}-002)."""
        resp = await auth_client.post("/api/v1/users", json={"name": "Bob", "email": "not-an-email"})
        assert resp.status_code == 422

    async def test_rejects_duplicate_email(self, auth_client, AC="AC-{ticket}-003"):
        """Duplicate email returns 409 (AC-{ticket}-003)."""
        payload = {"name": "Carol", "email": "carol@example.com"}
        await auth_client.post("/api/v1/users", json=payload)
        resp = await auth_client.post("/api/v1/users", json=payload)
        assert resp.status_code == 409
```

## Service Unit Tests

```python
# app/tests/test_users_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.users.service import UserService
from app.users.schema import CreateUserRequest

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.find_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    return repo

class TestUserServiceCreate:
    async def test_creates_user_successfully(self, mock_repo, AC="AC-{ticket}-001"):
        """Service creates user when email is unique (AC-{ticket}-001)."""
        mock_repo.create.return_value = MagicMock(id=1, name="Alice", email="alice@example.com")
        service = UserService.__new__(UserService)
        service.repo = mock_repo
        result = await service.create(CreateUserRequest(name="Alice", email="alice@example.com"))
        assert result.email == "alice@example.com"
        mock_repo.create.assert_called_once()

    async def test_raises_conflict_on_duplicate_email(self, mock_repo, AC="AC-{ticket}-003"):
        """Service raises HTTPException 409 when email exists (AC-{ticket}-003)."""
        from fastapi import HTTPException
        mock_repo.find_by_email.return_value = MagicMock(id=2)
        service = UserService.__new__(UserService)
        service.repo = mock_repo
        with pytest.raises(HTTPException) as exc:
            await service.create(CreateUserRequest(name="Dup", email="dup@example.com"))
        assert exc.value.status_code == 409
```

## pytest.ini / pyproject.toml

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = app/tests
```

## Checklist

- [ ] Every test function name includes AC-ID in the docstring or function name
- [ ] `conftest.py` has an `autouse` fixture that resets the test DB between tests
- [ ] Endpoint tests use `AsyncClient` — no direct service calls in HTTP tests
- [ ] Service tests mock the repository — no real DB in unit tests
- [ ] Test file paths follow `test_{domain}_{layer}.py`
- [ ] `pytest --cov=app` passes with ≥ 80% coverage
