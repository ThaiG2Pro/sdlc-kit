---
name: fastapi-database-migrations
description: >
  Alembic migration patterns for FastAPI + SQLAlchemy 2.x async projects.
  Covers autogenerate workflow, async env.py setup, data migrations,
  rollback safety rules, and the S3/S4 gate checklist.
---

# FastAPI Database Migrations (Alembic)

Alembic migration workflow for {{PROJECT_TITLE}} using SQLAlchemy 2.x async ORM.

## async env.py Setup

Alembic's `env.py` must run the async engine in a sync context for autogenerate:

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.core.database import Base
from app.core.config import settings
import app.models  # import all models so Base.metadata is populated

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

def run_migrations_offline():
    context.configure(url=settings.DATABASE_URL, target_metadata=Base.metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations():
    engine = async_engine_from_config(config.get_section(config.config_ini_section),
                                       prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## Workflow

```bash
# 1. Make changes to SQLAlchemy models
# 2. Generate migration
alembic revision --autogenerate -m "add users table"

# 3. Review generated file — NEVER commit an autogenerate without reviewing it
# 4. Apply
alembic upgrade head

# 5. Verify
alembic current

# 6. Rollback one step
alembic downgrade -1
```

## Migration File Rules

Every migration MUST have both `upgrade()` and `downgrade()`:

```python
# alembic/versions/abc123_add_users_table.py
def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
```

## Data Migrations

For backfill / data transformation — use `op.execute()` with raw SQL; avoid ORM in migrations (models change, migrations should be stable):

```python
def upgrade() -> None:
    # schema change
    op.add_column('orders', sa.Column('status_v2', sa.String(50), nullable=True))
    # data backfill
    op.execute("UPDATE orders SET status_v2 = status WHERE status_v2 IS NULL")
    # make non-nullable after backfill
    op.alter_column('orders', 'status_v2', nullable=False)

def downgrade() -> None:
    op.drop_column('orders', 'status_v2')
```

## Safety Rules (S3 Gate Checklist)

- [ ] Every migration has `upgrade()` AND `downgrade()` implemented
- [ ] `downgrade()` is the true inverse of `upgrade()` — not a no-op
- [ ] No destructive `DROP COLUMN` / `DROP TABLE` without confirming the column is unused
- [ ] Destructive changes: add a 2-step migration (step 1: stop writing; step 2: drop)
- [ ] `NOT NULL` columns added to existing tables: provide `server_default` OR backfill data first
- [ ] Migration reviewed by team (never committed untouched from autogenerate)
- [ ] `alembic upgrade head` runs clean on a fresh DB in CI
- [ ] `alembic downgrade -1` runs clean (test in dev before committing)

## S4 Developer Steps

1. Create migration: `alembic revision --autogenerate -m "{description}"`
2. Review the generated file — fix any autogenerate errors
3. Run `alembic upgrade head` locally — verify schema matches design.md § DB Schema
4. Add the migration file to the task's `[x]` checkbox
5. Include migration filename in `dev-test-report.md` § Migrations

## Production Deploy (S6)

Include in `release.md`:
- Migration file name and revision hash
- `upgrade` command: `alembic upgrade head`
- `downgrade` command: `alembic downgrade -1`
- Estimated duration for large tables
- Whether the migration requires downtime (locking)
