"""PostgreSQL-only database engine for the CET CAP portal."""
from __future__ import annotations
import os
from sqlalchemy import Engine, create_engine


def get_engine(db_url: str | None = None) -> Engine:
    """Return the single authoritative PostgreSQL engine.

    SQLite is deliberately unsupported. Keeping a second local database path
    can make admin-approved data differ from what the public site reads.
    """
    url = (db_url or os.getenv("DATABASE_URL", "")).strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required; PostgreSQL is the only supported database.")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    if not url.startswith("postgresql+psycopg2://"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
    return create_engine(url, pool_pre_ping=True, future=True)
