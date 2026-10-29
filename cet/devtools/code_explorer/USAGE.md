# Running the local explorer

Run commands from the repository's `cet/` directory. Use a local checkout; no Render deployment is required.

## 1. Install the project's existing test dependencies

Activate the same virtual environment you use for CETFind, then install the repository's requirements if needed.

## 2. Generate a trace of the actual search handler

This test calls the real `backend.api.search_colleges` route function and its real cache/uncached control flow, while replacing database dependencies with a synthetic engine and a synthetic one-row DataFrame. It does **not** connect to production or read real candidate data.

```bash
cd /path/to/SAM/cet
CET_CODE_EXPLORER_TRACE_OUT="$PWD/devtools/code_explorer/search-trace.json" \
  pytest -q tests/test_code_explorer_trace.py::test_trace_captures_real_cetfind_search_handler_with_synthetic_dependencies
```

The test should pass before you trust the trace. If it fails, do not use the generated file as proof of a successful trace.

## 3. Open the visual explorer

In another terminal, from `cet/`:

```bash
python -m http.server 8765 --directory devtools/code_explorer
```

Open `http://127.0.0.1:8765/`, select **Load trace JSON**, and choose `devtools/code_explorer/search-trace.json`.

The viewer's three panels are:

- **Execution events:** ordered Python call/line/return/exception events.
- **Execution graph:** a clickable sequence of observed events; it does not invent call edges.
- **Original source & state:** source context, file/line, call stack, and redacted local-variable snapshot.

Use Previous/Next or the left/right arrow keys to step through events. Search filters the event list and graph.

## Scope of this first iteration

- The current trace proves the route/cache/uncached-handler path for the test's specific synthetic input. It does not prove every possible branch.
- The database query implementation is replaced by a synthetic function in this first test; the next integration step is to trace the actual `search_college_summary_page` implementation against a disposable local PostgreSQL database.
- Python runtime tracing does not trace browser JavaScript. Frontend click/fetch tracing and browser-to-backend correlation are a separate phase.
- Local-variable snapshots are deliberately shallow. Containers are represented by type and size to avoid dumping large data structures.
- Review trace files before sharing them. Secret-like names are redacted, but no heuristic can guarantee that all sensitive values are removed.
- The tracer is not wired into production, and it must not be enabled on Render.
