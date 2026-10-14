"""
SQLite Database Connection & Schema Manager for SDLC Context Engine.
Zero external dependencies (uses standard library `sqlite3`).
"""

import os
import sqlite3
from typing import Optional, Generator
from contextlib import contextmanager

DEFAULT_DB_PATH = os.path.join(os.getcwd(), ".sdlc", "session.db")
SCHEMA_SQL_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and configure a SQLite connection with Foreign Keys and Row factory."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA cache_size = -64000;")  # 64MB RAM page cache
    conn.execute("PRAGMA temp_store = MEMORY;")  # In-memory temporary tables & sorts

    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")  # Optimal & safe with WAL
        conn.execute("PRAGMA mmap_size = 268435456;")  # 256MB memory-mapped I/O
    return conn


def init_db(db_path: Optional[str] = None, schema_path: Optional[str] = None) -> sqlite3.Connection:
    """Initialize database by executing the schema.sql DDL."""
    if schema_path is None:
        schema_path = SCHEMA_SQL_PATH

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    conn.executescript(schema_sql)
    conn.commit()
    return conn


@contextmanager
def transaction(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for atomic database transactions."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
