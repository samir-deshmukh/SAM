from pathlib import Path

from devtools.code_explorer.trace_runtime import TraceSession


def _branch_example(value: int) -> int:
    if value > 3:
        return value * 2
    return value + 1


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


def test_trace_redacts_secret_like_local_names():
    from devtools.code_explorer.trace_runtime import _safe_value

    assert _safe_value("api_key", "do-not-store") == "[REDACTED]"
    assert _safe_value("ordinary_count", 7) == 7
