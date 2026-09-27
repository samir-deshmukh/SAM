#!/usr/bin/env python3
"""Run one bounded website-resolver step outside the FastAPI web process."""
from __future__ import annotations

import argparse
import logging
import sys

from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from backend.admin.db import connect
from backend.admin.resolver import resolve_import_job

log = logging.getLogger("resolver_worker")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

LOCK_KEY = 73829104


def acquire_lock(conn):
    # PostgreSQL advisory locks serialize resolver children on the single
    # low-memory Render instance. SQLite/local test databases simply skip it.
    try:
        row = conn.execute("SELECT pg_try_advisory_lock(?) AS locked", (LOCK_KEY,)).fetchone()
        return bool(row and row["locked"])
    except Exception:
        return True


def release_lock(conn):
    try:
        conn.execute("SELECT pg_advisory_unlock(?)", (LOCK_KEY,))
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", type=int)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    with connect() as conn:
        if not acquire_lock(conn):
            log.info("resolver already running; deferring job %s", args.job_id)
            return 0
    try:
        result = resolve_import_job(args.job_id, limit=max(1, min(args.limit, 1)))
        print(result, flush=True)
        return 0 if result.get("ok") else 1
    except Exception:
        log.exception("resolver worker failed for job %s", args.job_id)
        return 1
    finally:
        try:
            with connect() as conn:
                release_lock(conn)
                conn.commit()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
