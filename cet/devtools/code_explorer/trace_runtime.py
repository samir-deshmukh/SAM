"""Opt-in local Python execution tracer for CETFind tests and controlled reproductions.

Usage inside a test or local script:
    from pathlib import Path
    from devtools.code_explorer.trace_runtime import TraceSession

    with TraceSession(Path("trace.json"), root=Path.cwd() / "cet", max_events=10000):
        result = function_under_test(...)

This traces Python frames entered while the session is active on the current thread.
It is not a production middleware, does not trace browser JavaScript, and does not
automatically capture SQL internals. Run only with synthetic/local test data.
"""
from __future__ import annotations

import inspect
import json
import linecache
import os
import re
import sys
import threading
import time
from pathlib import Path
from types import FrameType
from typing import Any

_SECRET_NAME = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|cookie|session|credential|private[_-]?key)",
    re.IGNORECASE,
)
_MAX_REPR = 160
_MAX_EVENTS_DEFAULT = 20_000


def _safe_value(name: str, value: Any) -> Any:
    """Convert a local variable to bounded JSON-safe text, redacting likely secrets."""
    if _SECRET_NAME.search(name):
        return "[REDACTED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_REPR] + ("…" if len(value) > _MAX_REPR else "")
    if isinstance(value, (bytes, bytearray)):
        return f"<{type(value).__name__} length={len(value)}>"
    if isinstance(value, (list, tuple, set, dict)):
        try:
            size = len(value)
        except Exception:
            size = "?"
        return f"<{type(value).__name__} length={size}>"
    return f"<{type(value).__name__}>"


class TraceSession:
    """Capture call/line/return/exception events for repository Python files."""

    def __init__(
        self,
        output_path: str | Path,
        *,
        root: str | Path,
        max_events: int = _MAX_EVENTS_DEFAULT,
        capture_locals: bool = True,
        context_lines: int = 2,
    ) -> None:
        self.output_path = Path(output_path)
        self.root = Path(root).resolve()
        self.max_events = max(1, int(max_events))
        self.capture_locals = capture_locals
        self.context_lines = max(0, int(context_lines))
        self.events: list[dict[str, Any]] = []
        self.truncated = False
        self._previous_trace = None
        self._previous_frame_trace = None
        self._caller_frame: FrameType | None = None
        self._active = False

    def __enter__(self) -> "TraceSession":
        if self._active:
            raise RuntimeError("TraceSession cannot be entered twice")
        self._active = True
        self._caller_frame = inspect.currentframe().f_back if inspect.currentframe() else None
        self._previous_trace = sys.gettrace()
        if self._caller_frame is not None:
            self._previous_frame_trace = self._caller_frame.f_trace
            self._caller_frame.f_trace = self._trace
        sys.settrace(self._trace)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        sys.settrace(self._previous_trace)
        if self._caller_frame is not None:
            self._caller_frame.f_trace = self._previous_frame_trace
        self._active = False
        self._write()
        return False

    def _in_scope(self, filename: str) -> bool:
        try:
            Path(filename).resolve().relative_to(self.root)
            return True
        except (ValueError, OSError):
            return False

    def _source_context(self, filename: str, line_number: int) -> list[dict[str, Any]]:
        first = max(1, line_number - self.context_lines)
        last = line_number + self.context_lines
        result = []
        for number in range(first, last + 1):
            text = linecache.getline(filename, number)
            if text:
                result.append({"line": number, "text": text.rstrip("\n")})
        return result

    def _stack(self, frame: FrameType) -> list[str]:
        stack = []
        current = frame.f_back
        while current is not None and len(stack) < 40:
            filename = current.f_code.co_filename
            if self._in_scope(filename):
                try:
                    short = str(Path(filename).resolve().relative_to(self.root))
                except (ValueError, OSError):
                    short = filename
                stack.append(f"{short}:{current.f_lineno} in {current.f_code.co_name}")
            current = current.f_back
        stack.reverse()
        return stack

    def _trace(self, frame: FrameType, event: str, arg: Any):
        if event == "call":
            frame.f_trace_lines = True
            frame.f_trace_opcodes = False
        filename = frame.f_code.co_filename
        if not self._in_scope(filename):
            return self._trace
        if len(self.events) >= self.max_events:
            self.truncated = True
            return self._trace

        try:
            relative_file = str(Path(filename).resolve().relative_to(self.root))
        except (ValueError, OSError):
            relative_file = filename
        line_number = frame.f_lineno
        source = linecache.getline(filename, line_number).rstrip("\n")
        item: dict[str, Any] = {
            "index": len(self.events),
            "event": event,
            "file": relative_file,
            "line": line_number,
            "function": frame.f_code.co_name,
            "caller": frame.f_back.f_code.co_name if frame.f_back else None,
            "thread_id": threading.get_ident(),
            "timestamp": round(time.perf_counter(), 6),
            "source": source,
            "source_context": self._source_context(filename, line_number),
            "stack": self._stack(frame),
        }
        if event == "exception" and isinstance(arg, tuple) and len(arg) >= 2:
            exception_type, exception_value = arg[0], arg[1]
            item["exception"] = {
                "type": getattr(exception_type, "__name__", "Exception"),
                "message": str(exception_value)[:_MAX_REPR],
            }
        if self.capture_locals and event in {"call", "line", "return", "exception"}:
            item["locals"] = {
                str(name): _safe_value(str(name), value)
                for name, value in list(frame.f_locals.items())[:80]
            }
        self.events.append(item)
        return self._trace

    def _write(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "cetfind-execution-trace-v1",
            "root": str(self.root),
            "created_at_unix": time.time(),
            "event_count": len(self.events),
            "max_events": self.max_events,
            "truncated": self.truncated,
            "notes": [
                "Local opt-in trace; not a production observation.",
                "Only Python frames under the configured root are recorded.",
                "Secret-like local variable names are redacted; inspect output before sharing.",
                "Objects are represented by type and size rather than serialized recursively.",
            ],
            "events": self.events,
        }
        self.output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
