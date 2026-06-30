---
name: fastapi-tdd-workflow
description: >
  Test-driven development workflow for FastAPI + pytest-asyncio: red-green-refactor
  cycle, fixture design, mock strategy, and coverage gate aligned with S4 Build.
---

# FastAPI TDD Workflow

Red → Green → Refactor cycle for {{PROJECT_TITLE}} using pytest + pytest-asyncio.

## TDD Cycle for FastAPI

**Write the test first, then the implementation.** Each AC-ID gets a failing test before any production code is written.

```
1. Write a failing test that names the AC-ID
2. Run pytest → confirm it fails (Red)
3. Write the minimum code to make it pass (Green)
4. Refactor — no new tests go Red
5. Mark tasks.md checkbox [x]
```

## Step-by-Step for a New Endpoint

### 1. Write the failing test

```python
# app/tests/test_orders_api.py
import pytest

class TestCreateOrder:
    async def test_creates_order_with_valid_items(self, auth_client):
        """Happy path — order created returns 201 with id (AC-{ticket}-001)."""
        resp = await auth_client.post("/api/v1/orders", json={
            "items": [{"product_id": 1, "quantity": 2}]
        })
        assert resp.status_code == 201       # <-- fails: endpoint doesn't exist yet
        assert "id" in resp.json()["data"]
```

### 2. Run to confirm Red

```bash
pytest app/tests/test_orders_api.py::TestCreateOrder::test_creates_order_with_valid_items -v
# Expected: FAILED — 404 Not Found (endpoint not yet registered)
```

### 3. Write minimum production code

Only write what makes THIS test pass:
- `app/orders/model.py` — ORM model
- `app/orders/schema.py` — `CreateOrderRequest`, `OrderResponse`
- `app/orders/repository.py` — `create()` method
- `app/orders/service.py` — `create()` method
- `app/orders/router.py` — POST `/` endpoint
- Register router in `app/main.py`

### 4. Run until Green

```bash
pytest app/tests/test_orders_api.py -v
# Expected: PASSED
```

### 5. Add error path tests before refactoring

```python
    async def test_rejects_empty_items(self, auth_client):
        """Empty items list returns 422 (AC-{ticket}-002)."""
        resp = await auth_client.post("/api/v1/orders", json={"items": []})
        assert resp.status_code == 422

    async def test_requires_authentication(self, client):
        """Unauthenticated request returns 401 (AC-{ticket}-003)."""
        resp = await client.post("/api/v1/orders", json={"items": [{"product_id": 1}]})
        assert resp.status_code == 401
```

## Scope: What to Test Where

| Scenario | Where to test | Why |
|----------|--------------|-----|
| HTTP status codes + response shape | `test_{domain}_api.py` (endpoint test) | Tests the full stack |
| Business rules + error conditions | `test_{domain}_service.py` (unit test) | Faster, isolated |
| DB query correctness | Integration test or repository test | Only when query is complex |
| Auth guards, permission checks | Endpoint test | Tests the wiring, not the logic |
| Data validation (Pydantic) | Endpoint test (422 path) | Pydantic runs in the HTTP layer |

## Mock Strategy

**Unit tests (service layer)** — mock the repository, never the DB:

```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_order_repo():
    repo = AsyncMock()
    repo.find_by_id.return_value = None     # default: not found
    repo.create.return_value = MagicMock(id=1, status="pending")
    return repo

async def test_get_order_raises_404_when_missing(mock_order_repo):
    """(AC-{ticket}-004)"""
    from fastapi import HTTPException
    service = OrderService(mock_order_repo)
    with pytest.raises(HTTPException) as exc:
        await service.get_or_404(user_id=99)
    assert exc.value.status_code == 404
```

**Integration tests** — use real test DB (from conftest fixture), no mocks:

```python
async def test_full_order_flow(self, auth_client, setup_db):
    """End-to-end: create order → fetch → verify (AC-{ticket}-005)."""
    create_resp = await auth_client.post("/api/v1/orders", json={...})
    order_id = create_resp.json()["data"]["id"]
    get_resp = await auth_client.get(f"/api/v1/orders/{order_id}")
    assert get_resp.status_code == 200
```

## Running Tests During S4

```bash
# Single test (fast feedback during TDD)
pytest app/tests/test_orders_api.py::TestCreateOrder::test_creates_order -v

# Module scope (after each service file)
pytest app/tests/test_orders_service.py -v

# Full suite (before each checkpoint)
pytest -x   # stop on first failure

# With coverage (final checkpoint only)
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

## Coverage Rules

- Target: ≥ 80% lines, ≥ 90% diff (changed lines)
- Exclude from coverage in `pyproject.toml`:
  ```toml
  [tool.coverage.run]
  omit = ["app/tests/*", "alembic/*", "app/main.py"]
  ```
- Never add an exclude for a module that has business logic
- If coverage drops below threshold → add tests before marking S4 done

## Checkpoint Self-Check

Before presenting each checkpoint to the orchestrator:

```bash
ruff check app/          # lint — 0 errors
ruff format --check app/ # format — 0 diffs
mypy app/                # types — 0 errors
pytest -x                # tests — all pass
```
