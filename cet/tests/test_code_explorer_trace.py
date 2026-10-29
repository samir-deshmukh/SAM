from pathlib import Path

import pandas as pd
from fastapi import Response
from starlette.requests import Request

import backend.api as api
from devtools.code_explorer.trace_runtime import TraceSession


def _branch_example(value: int) -> int:
    if value > 3:
        return value * 2
    return value + 1


def _request_for(ip="127.0.0.1"):
    return Request({
        "type": "http", "method": "GET", "path": "/api/search",
        "query_string": b"", "headers": [], "client": (ip, 12345), "scheme": "http",
    })


def test_trace_records_actual_lines_and_source(tmp_path):
    cet_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "trace.json"

    with TraceSession(output, root=cet_root, max_events=500) as trace:
        result = _branch_example(5)

    assert result == 10
    assert output.exists()
    assert trace.events
    events = [event for event in trace.events if event["function"] == "_branch_example"]
    assert any(event["event"] == "call" for event in events)
    assert any(event["event"] == "line" for event in events)
    assert any("value > 3" in event["source"] for event in events)
    assert all("source_context" in event for event in events)


def test_trace_captures_real_cetfind_search_handler_with_synthetic_dependencies(monkeypatch, tmp_path):
    """Trace the real route and uncached handler while keeping all data synthetic."""
    cet_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "cetfind-search-trace.json"

    class FakeEngine:
        pass

    summary = pd.DataFrame([{
        "institution_code": "TEST01",
        "institution_name": "Synthetic Test College",
        "city": "Amravati",
        "website": "https://example.invalid",
        "highest_cutoff": 80.0,
        "years_on_record": 2,
    }])
    monkeypatch.setattr(api, "get_active_engine", lambda: FakeEngine())
    monkeypatch.setattr(api, "available_public_courses", lambda engine: ["BBA"])
    monkeypatch.setattr(api, "search_college_summary_page", lambda *args, **kwargs: (summary, 1))
    monkeypatch.setattr(
        api, "_search_metadata",
        lambda *args: ({}, {"TEST01": {"cutoff": 1200, "percentile": 75.0, "history": [], "graph_history": []}}, {"TEST01": False}),
    )
    api._request_history.clear()
    api._PUBLIC_CACHE.clear()

    with TraceSession(output, root=cet_root, max_events=10000) as trace:
        result = api.search_colleges(
            _request_for("10.0.0.99"), course="BBA", percentile=82.0, city=None,
            sort="comp", page=1, page_size=25,
        )

    assert result.total == 1
    assert result.results[0].institution_code == "TEST01"
    assert output.exists()
    traced_functions = {event["function"] for event in trace.events}
    assert "search_colleges" in traced_functions
    assert "_search_colleges_uncached" in traced_functions
    assert any(event["file"] == "backend/api.py" and event["event"] == "line" for event in trace.events)


def test_trace_redacts_secret_like_local_names():
    from devtools.code_explorer.trace_runtime import _safe_value

    assert _safe_value("api_key", "do-not-store") == "[REDACTED]"
    assert _safe_value("ordinary_count", 7) == 7
