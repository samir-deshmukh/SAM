"""Low-overhead, in-process SQLAlchemy pool telemetry.

Only bounded endpoint labels and aggregate timings are logged. No SQL,
connection strings, client addresses, or request parameters are recorded.
"""
from __future__ import annotations

import logging
import threading
import time
import weakref
from contextvars import ContextVar
from typing import Any

from sqlalchemy import Engine, event

log = logging.getLogger("cet-cap-db-pool")
log.setLevel(logging.INFO)
_request_endpoint: ContextVar[str] = ContextVar("cet_db_endpoint", default="background")


def endpoint_label(path: str) -> str:
    """Return a bounded route-family label with no dynamic path values."""
    clean_path = (path or "/").split("?", 1)[0].split("#", 1)[0]
    parts = [part for part in clean_path.split("/") if part]
    if not parts:
        label = "/"
    elif len(parts) == 1:
        label = "/" + parts[0][:32]
    else:
        # The first two path components identify the API/admin route family.
        # Dynamic IDs, filenames, and arbitrary trailing segments never become
        # metric labels, keeping the per-endpoint registry strictly bounded.
        label = "/" + parts[0][:16] + "/" + parts[1][:32]
        if len(parts) > 2:
            label += "/*"
    return label[:64]


def set_request_endpoint(path: str):
    """Set the current request route label and return its reset token."""
    return _request_endpoint.set(endpoint_label(path))


def reset_request_endpoint(token) -> None:
    _request_endpoint.reset(token)


class _PoolStats:
    def __init__(self, name: str):
        self.name = name
        self.lock = threading.Lock()
        self.checkouts = 0
        self.checkins = 0
        self.slow_holds = 0
        self.hold_total_ms = 0.0
        self.hold_max_ms = 0.0
        self.timeouts = 0
        self.last_summary = time.monotonic()
        self.by_endpoint: dict[str, dict[str, float | int]] = {}


_stats_by_engine: weakref.WeakKeyDictionary[Engine, _PoolStats] = weakref.WeakKeyDictionary()
_registry_lock = threading.Lock()


def attach_pool_telemetry(engine: Engine, name: str) -> Engine:
    """Attach listeners exactly once to an engine; leave pool settings intact."""
    with _registry_lock:
        stats = _stats_by_engine.get(engine)
        if stats is not None:
            return engine
        stats = _PoolStats(name)
        _stats_by_engine[engine] = stats

    def on_checkout(dbapi_connection: Any, connection_record: Any, connection_proxy: Any):
        now = time.monotonic()
        connection_record.info["cet_pool_checkout_at"] = now
        connection_record.info["cet_pool_checkout_endpoint"] = _request_endpoint.get()
        connection_record.info["cet_pool_checkout_thread"] = threading.current_thread().name[:48]
        with stats.lock:
            stats.checkouts += 1

    def on_checkin(dbapi_connection: Any, connection_record: Any):
        started = connection_record.info.pop("cet_pool_checkout_at", None)
        endpoint = connection_record.info.pop("cet_pool_checkout_endpoint", "background")
        thread_name = connection_record.info.pop("cet_pool_checkout_thread", "unknown")
        if started is None:
            return
        elapsed_ms = max(0.0, (time.monotonic() - started) * 1000.0)
        now = time.monotonic()
        summary = None
        with stats.lock:
            stats.checkins += 1
            stats.hold_total_ms += elapsed_ms
            endpoint_stats = stats.by_endpoint.setdefault(
                endpoint, {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "slow": 0}
            )
            endpoint_stats["count"] += 1
            endpoint_stats["total_ms"] += elapsed_ms
            endpoint_stats["max_ms"] = max(float(endpoint_stats["max_ms"]), elapsed_ms)
            if elapsed_ms >= 1000.0:
                endpoint_stats["slow"] += 1
            stats.hold_max_ms = max(stats.hold_max_ms, elapsed_ms)
            if elapsed_ms >= 1000.0:
                stats.slow_holds += 1
            if now - stats.last_summary >= 60.0:
                total = max(stats.checkins, 1)
                summary = {
                    "checkouts": stats.checkouts,
                    "checkins": stats.checkins,
                    "slow_holds_ge_1s": stats.slow_holds,
                    "avg_hold_ms": round(stats.hold_total_ms / total, 1),
                    "max_hold_ms": round(stats.hold_max_ms, 1),
                    "timeouts": stats.timeouts,
                    "by_endpoint": {key: dict(value) for key, value in stats.by_endpoint.items()},
                }
                stats.checkouts = stats.checkins = stats.slow_holds = stats.timeouts = 0
                stats.hold_total_ms = stats.hold_max_ms = 0.0
                stats.by_endpoint.clear()
                stats.last_summary = now
        if elapsed_ms >= 1000.0:
            log.warning(
                "DB_POOL_SLOW_HOLD pool=%s endpoint=%s thread=%s hold_ms=%.1f checked_out=%s",
                stats.name, endpoint, thread_name, elapsed_ms, engine.pool.checkedout(),
            )
        if summary is not None:
            log.info(
                "DB_POOL_SUMMARY pool=%s checked_out_at_checkin=%s checked_in_at_checkin=%s pool_size=%s overflow=%s "
                "checkouts=%s checkins=%s slow_holds_ge_1s=%s avg_hold_ms=%s "
                "max_hold_ms=%s timeouts=%s",
                stats.name,
                engine.pool.checkedout(),
                engine.pool.checkedin(),
                engine.pool.size(),
                engine.pool.overflow(),
                summary["checkouts"], summary["checkins"], summary["slow_holds_ge_1s"],
                summary["avg_hold_ms"], summary["max_hold_ms"], summary["timeouts"],
            )
            for endpoint, values in summary["by_endpoint"].items():
                count = max(int(values["count"]), 1)
                log.info(
                    "DB_POOL_ENDPOINT pool=%s endpoint=%s checkins=%s avg_hold_ms=%.1f "
                    "max_hold_ms=%.1f slow_holds_ge_1s=%s",
                    stats.name, endpoint, values["count"], float(values["total_ms"]) / count,
                    values["max_ms"], values["slow"],
                )

    event.listen(engine, "checkout", on_checkout)
    event.listen(engine, "checkin", on_checkin)
    return engine


def record_pool_timeout(engine: Engine, name: str | None = None, endpoint: str | None = None) -> None:
    """Record a QueuePool acquisition timeout and emit one bounded diagnostic."""
    with _registry_lock:
        stats = _stats_by_engine.get(engine)
    if stats is None:
        attach_pool_telemetry(engine, name or "unknown")
        with _registry_lock:
            stats = _stats_by_engine.get(engine)
    with stats.lock:
        stats.timeouts += 1
    log.error(
        "DB_POOL_TIMEOUT pool=%s endpoint=%s checked_out=%s pool_size=%s "
        "overflow=%s status=%s",
        stats.name, endpoint_label(endpoint) if endpoint else _request_endpoint.get(), engine.pool.checkedout(),
        engine.pool.size(), engine.pool.overflow(), engine.pool.status(),
    )
