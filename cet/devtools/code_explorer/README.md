# CETFind Code Explorer

This is a local developer-learning tool. It is not part of the public CETFind website and is not enabled in production.

## Start with the guided tour

If you do not understand traces or backend code yet, start with **[guided.html](./guided.html)**. It walks through Search Colleges from browser input to FastAPI, cache branches, PostgreSQL query boundary, response construction, and browser rendering. Click a step to see the code pattern, plain-English explanation, and what changes the path.

Run a local static server from `cet/`:

```bash
python -m http.server 8765 --directory devtools/code_explorer
```

Open `http://127.0.0.1:8765/guided.html`.

The guide is **source-guided**, not a recording of a request that just ran. It documents the normal path and important branches; it does not claim that every listed step ran for a particular request.

## Then inspect a Python runtime trace

See [USAGE.md](./USAGE.md) for the opt-in trace test and event viewer. The test calls the real FastAPI route with synthetic dependencies; it does not access production data.

## Current limits

- Python tracing only. Browser JavaScript and frontend events are not runtime-traced.
- The test replaces the database query dependency with synthetic data. It does not trace SQL execution.
- The event viewer displays observed Python events in order; that sequence is not a complete control-flow graph.
- The guide and viewer are an initial learning foundation, not yet a complete end-to-end interactive debugger.
- Trace files can contain local values. Secret-name redaction is heuristic, so review files before sharing them.
- Do not deploy or enable this tool on Render. No production files or settings are changed by using it locally.
