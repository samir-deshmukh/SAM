# Running the local explorer

Run commands from the repository's `cet/` directory. This tool is local-only; no Render deployment is required.

## 1. Start with the guided tour

If you are new to the project, open the source-guided tour first:

```bash
cd /path/to/SAM/cet
python -m http.server 8765 --directory devtools/code_explorer
```

Then open `http://127.0.0.1:8765/guided.html`.

Click each step in **Search Colleges** to see the code pattern, plain-English explanation, and alternative branches. The guide is derived from source code; it is not claiming that a particular live request executed every step.

## 2. Generate a trace of the Python route

Activate the same virtual environment you use for CETFind, with the repository's test dependencies installed. This test calls the real `backend.api.search_colleges` route and its real cache/uncached control flow, but replaces database dependencies with a synthetic engine and a synthetic one-row DataFrame. It does not connect to production or read real candidate data.

```bash
cd /path/to/SAM/cet
CET_CODE_EXPLORER_TRACE_OUT="$PWD/devtools/code_explorer/search-trace.json" \
  pytest -q tests/test_code_explorer_trace.py::test_trace_captures_real_cetfind_search_handler_with_synthetic_dependencies
```

Only trust the generated trace if the test passes. The test has **not been run by the authoring environment**; run it locally and inspect any failure before relying on the output.

## 3. Open the event viewer

Keep the local server running and open `http://127.0.0.1:8765/`. Select **Load trace JSON**, then choose `devtools/code_explorer/search-trace.json`.

- **Execution events:** ordered Python call/line/return/exception events.
- **Execution graph:** a clickable sequence of observed events; it does not invent call edges.
- **Original source & state:** source context, file/line, call stack, and shallow local-variable snapshots.

## Current limits

- The runtime tracer covers Python frames on the current thread. It does not trace browser JavaScript.
- The route test substitutes the database query with synthetic data; it does not trace the actual SQL query execution.
- The event list is not a complete control-flow graph, and the test exercises only its chosen input/branch.
- Local-variable snapshots are shallow. Containers are represented by type and size to avoid dumping large data structures.
- Secret-name redaction is heuristic and cannot guarantee every sensitive value is removed. Review trace files before sharing them.
- The tracer is not wired into production. Do not enable it on Render.
