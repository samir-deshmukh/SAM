"""Small PostgreSQL-only SQL helper for runtime exporters."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text

_ENGINE = None


def get_engine(url: str | None = None):
    global _ENGINE
    if _ENGINE is not None and url is None:
        return _ENGINE

    url = (url or os.getenv("DATABASE_URL", "")).strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required; PostgreSQL is the only supported data source."
        )
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    if not url.startswith("postgresql+psycopg2://"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")

    engine = create_engine(url, pool_pre_ping=True, future=True)
    if url == os.getenv("DATABASE_URL"):
        _ENGINE = engine
    return engine


def qmark_sql(sql: str, params=()):
    params = tuple(params or ())
    output = []
    index = 0
    for char in sql:
        if char == "?":
            output.append(f":p{index}")
            index += 1
        else:
            output.append(char)
    if index != len(params):
        raise ValueError(f"Expected {index} params, got {len(params)}")
    return "".join(output), {f"p{i}": value for i, value in enumerate(params)}


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, sql, params=()):
        converted, values = qmark_sql(sql, params)
        self.result = self.connection.execute(text(converted), values)
        return self

    def fetchall(self):
        return [tuple(row) for row in self.result.fetchall()]

    def fetchone(self):
        row = self.result.fetchone()
        return tuple(row) if row is not None else None


def open_cursor(url=None):
    connection = get_engine(url).connect()
    return connection, Cursor(connection)
