"""Tests for the per-course runtime-serving readiness probe cache."""

from sqlalchemy.exc import ProgrammingError

from src.cet_cap import queries


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Connection:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        self.engine.probes += 1
        if self.engine.error is not None:
            raise self.engine.error
        return _Result(self.engine.ready)


class _Engine:
    def __init__(self, ready=True):
        self.ready = ready
        self.error = None
        self.probes = 0

    def connect(self):
        return _Connection(self)


def setup_function():
    queries.invalidate_search_runtime_readiness_cache()


def test_readiness_is_cached_per_engine_and_course():
    engine = _Engine(ready=True)

    assert queries._search_runtime_is_ready(engine, "BCA") is True
    assert queries._search_runtime_is_ready(engine, "BCA") is True
    assert engine.probes == 1

    assert queries._search_runtime_is_ready(engine, "MCA") is True
    assert engine.probes == 2

    other_engine = _Engine(ready=False)
    assert queries._search_runtime_is_ready(other_engine, "BCA") is False
    assert other_engine.probes == 1


def test_expired_readiness_entry_is_rechecked(monkeypatch):
    engine = _Engine(ready=True)
    now = [100.0]
    monkeypatch.setattr(queries.time, "monotonic", lambda: now[0])

    assert queries._search_runtime_is_ready(engine, "BE") is True
    engine.ready = False
    now[0] += queries._RUNTIME_READINESS_TTL_SECONDS + 0.01

    assert queries._search_runtime_is_ready(engine, "BE") is False
    assert engine.probes == 2


def test_explicit_invalidation_forces_a_new_probe():
    engine = _Engine(ready=True)

    assert queries._search_runtime_is_ready(engine, "BBA") is True
    engine.ready = False
    queries.invalidate_search_runtime_readiness_cache()

    assert queries._search_runtime_is_ready(engine, "BBA") is False
    assert engine.probes == 2


def test_programming_error_is_not_cached():
    engine = _Engine()
    engine.error = ProgrammingError("SELECT", {}, RuntimeError("table missing"))

    try:
        queries._search_runtime_is_ready(engine, "BCA")
    except ProgrammingError:
        pass
    else:
        raise AssertionError("ProgrammingError should propagate to the legacy fallback")

    engine.error = None
    engine.ready = True
    assert queries._search_runtime_is_ready(engine, "BCA") is True
    assert engine.probes == 2
