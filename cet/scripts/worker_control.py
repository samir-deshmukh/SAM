"""Cooperative pause/cancel checkpoints for the optional local CAPFind worker.

No-op unless CAPFIND_JOB_CONTROL_DIR is set, so the trusted extractor output
is unchanged for existing CLI/server callers.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _write_progress(directory: Path, payload: dict) -> None:
    temp = directory / "progress.json.tmp"
    temp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temp.replace(directory / "progress.json")


def checkpoint(page: int, total: int) -> None:
    raw_dir = os.environ.get("CAPFIND_JOB_CONTROL_DIR", "").strip()
    if not raw_dir:
        return
    directory = Path(raw_dir)
    directory.mkdir(parents=True, exist_ok=True)
    cancel = directory / "CANCEL"
    pause = directory / "PAUSE"
    if cancel.exists():
        raise RuntimeError("CAPFIND_WORKER_CANCELLED")
    _write_progress(directory, {"page": int(page), "total": int(total), "state": "RUNNING", "updated_at": time.time()})
    while pause.exists():
        if cancel.exists():
            raise RuntimeError("CAPFIND_WORKER_CANCELLED")
        _write_progress(directory, {"page": int(page), "total": int(total), "state": "PAUSED", "updated_at": time.time()})
        time.sleep(0.5)
    _write_progress(directory, {"page": int(page), "total": int(total), "state": "RUNNING", "updated_at": time.time()})
