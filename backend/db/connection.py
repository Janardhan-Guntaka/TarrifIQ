"""PostgreSQL connection pool (Supabase)."""

from contextlib import contextmanager
from typing import Generator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.config.settings import get_settings

_pool: ConnectionPool | None = None


def _configure_connection(conn: Connection) -> None:
    """Register pgvector types on each new connection."""
    try:
        from pgvector.psycopg import register_vector

        register_vector(conn)
    except ImportError:
        pass


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        settings.require_database()
        _pool = ConnectionPool(
            conninfo=settings.resolved_database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            configure=_configure_connection,
        )
    return _pool


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
