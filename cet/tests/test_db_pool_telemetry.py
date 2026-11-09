import logging
import time

from sqlalchemy import create_engine

from backend.admin import db_telemetry


def test_pool_telemetry_tracks_checkout_checkin_and_endpoint(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pool.db'}", pool_size=2, max_overflow=1)
    db_telemetry.attach_pool_telemetry(engine, "test")
    token = db_telemetry.set_request_endpoint("/api/search/12345")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        stats = db_telemetry._stats_by_engine[engine]
        assert stats.checkouts == 1
        assert stats.checkins == 1
        assert "/api/search/*" in stats.by_endpoint
        assert stats.by_endpoint["/api/search/*"]["count"] == 1
        assert engine.pool.checkedout() == 0
    finally:
        db_telemetry.reset_request_endpoint(token)
        engine.dispose()


def test_pool_telemetry_attaches_only_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pool-once.db'}")
    db_telemetry.attach_pool_telemetry(engine, "test")
    first = db_telemetry._stats_by_engine[engine]
    db_telemetry.attach_pool_telemetry(engine, "renamed")
    assert db_telemetry._stats_by_engine[engine] is first
    with engine.connect():
        pass
    assert first.checkouts == 1
    assert first.checkins == 1
    engine.dispose()


def test_endpoint_label_does_not_include_query_or_numeric_identifiers():
    token = db_telemetry.set_request_endpoint("/api/search?secret=not-logged")
    try:
        assert db_telemetry._request_endpoint.get() == "/api/search"
    finally:
        db_telemetry.reset_request_endpoint(token)


def test_pool_timeout_is_counted_and_logs_pool_state(tmp_path, caplog):
    engine = create_engine(f"sqlite:///{tmp_path / 'pool-timeout.db'}", pool_size=1, max_overflow=0)
    db_telemetry.attach_pool_telemetry(engine, "test")
    token = db_telemetry.set_request_endpoint("/api/search/123")
    try:
        db_telemetry.record_pool_timeout(engine, endpoint="/api/search/123")
        stats = db_telemetry._stats_by_engine[engine]
        assert stats.timeouts == 1
        assert "DB_POOL_TIMEOUT" in caplog.text
        assert "endpoint=/api/search/*" in caplog.text
    finally:
        db_telemetry.reset_request_endpoint(token)
        engine.dispose()


def test_pool_summary_emits_endpoint_aggregates(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="cet-cap-db-pool")
    engine = create_engine(f"sqlite:///{tmp_path / 'pool-summary.db'}", pool_size=1, max_overflow=0)
    db_telemetry.attach_pool_telemetry(engine, "test")
    stats = db_telemetry._stats_by_engine[engine]
    stats.last_summary = time.monotonic() - 61
    token = db_telemetry.set_request_endpoint("/api/search/234")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        assert "DB_POOL_SUMMARY pool=test" in caplog.text
        assert "DB_POOL_ENDPOINT pool=test endpoint=/api/search/*" in caplog.text
        assert "checked_in_at_checkin=0" in caplog.text
        assert engine.pool.checkedout() == 0
    finally:
        db_telemetry.reset_request_endpoint(token)
        engine.dispose()
