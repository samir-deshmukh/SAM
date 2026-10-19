"""Loopback-only CAPFind PDF extraction worker.

The worker owns the source PDF and temporary extraction files on this PC.
Only validated CSV artifacts are sent to the Render API. Jobs are persisted
under data/local_worker so closing the browser does not stop extraction.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.admin.pipeline import (
    SUPPORTED_COURSE_FAMILIES,
    detect_data_type,
    extract_pdf_metadata,
    identify,
    security_check,
)
from scripts.cutoff_extractor import process_single_pdf as extract_cutoffs
from scripts.seat_matrix_extractor import process_single_pdf as extract_seats

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "local_worker"
DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(DATA, 0o700)
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_ARTIFACT_BYTES = 150 * 1024 * 1024
ALLOWED_HOSTS = {"cetfind.onrender.com", "cetfind-backend.onrender.com", "localhost", "127.0.0.1"}
ALLOWED_ORIGINS = {
    "https://cetfind.onrender.com",
    "https://cetfind-backend.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}
TERMINAL = {"DONE", "FAILED", "CANCELLED"}
LOCK = threading.RLock()
JOBS: dict[int, dict] = {}
ACTIVE_JOB: int | None = None

class LocalNetworkCORSMiddleware(CORSMiddleware):
    """Add Chrome's Private Network Access opt-in to CORS preflight replies."""
    async def __call__(self, scope, receive, send):
        async def send_with_private_network(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-private-network", b"true"))
                message["headers"] = headers
            await send(message)
        await super().__call__(scope, receive, send_with_private_network)


app = FastAPI(title="CAPFind Local Extraction Worker", docs_url=None, redoc_url=None)
app.add_middleware(
    LocalNetworkCORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Length"],
)


def _origin_ok(request: Request) -> None:
    origin = request.headers.get("origin", "")
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(403, "Origin is not allowed to use the CAPFind local worker")


def _backend_ok(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    ):
        raise HTTPException(400, "Backend URL must use HTTPS")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(400, "Backend host is not allow-listed")
    return value.rstrip("/")


def _write_state(job_id: int, state: dict) -> None:
    folder = DATA / f"job_{job_id}"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    tmp = folder / "job.json.tmp"
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(folder / "job.json")
    JOBS[job_id] = state


def _load_state(job_id: int) -> dict:
    with LOCK:
        state = JOBS.get(job_id)
        if state:
            return state
        path = DATA / f"job_{job_id}" / "job.json"
        if not path.exists():
            raise HTTPException(404, "Local job not found")
        state = json.loads(path.read_text(encoding="utf-8"))
        JOBS[job_id] = state
        return state


def _remote(state: dict, suffix: str, *, payload=None, files=None, data=None):
    url = state["backend_url"] + f"/admin/api/local-imports/{state['job_id']}/{suffix}"
    response = requests.post(
        url,
        headers={"Authorization": "Bearer " + state["upload_token"]},
        json=payload,
        files=files,
        data=data,
        timeout=(15, 300),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"CAPFind server returned {response.status_code}: {response.text[:800]}")
    return response.json() if response.content else {}


def _status(state: dict, status: str, message: str, **extra):
    state.update({"status": status, "message": message, "updated_at": time.time(), **extra})
    _write_state(state["job_id"], state)


def _progress(state: dict, page: int, total: int, worker_state: str = "RUNNING"):
    _remote(state, "progress", payload={"page": page, "total": total, "state": worker_state})


def _process_job(job_id: int):
    global ACTIVE_JOB
    state = _load_state(job_id)
    folder = DATA / f"job_{job_id}"
    pdf_path = folder / Path(state["filename"]).name
    if not pdf_path.exists() and (folder / "source.pdf").exists():
        # Recover jobs created by early local-worker builds without losing the source.
        pdf_path = folder / "source.pdf"
    control = folder / "control"
    control.mkdir(exist_ok=True)
    try:
        _status(state, "EXTRACTING", "Checking the PDF on this PC")
        size, actual_sha = security_check(pdf_path)
        if actual_sha != state["sha256"] or size != state["size_bytes"]:
            raise RuntimeError("The local PDF fingerprint does not match the queued import")
        _, filename_family, filename_year, filename_round, _ = identify(state["filename"])
        data_type = detect_data_type(pdf_path, state["filename"], use_ocr=True)
        pdf_family, pdf_year, pdf_round = extract_pdf_metadata(
            pdf_path, state["filename"], use_ocr=True
        )
        # The document's own title and CAP metadata are authoritative. Names
        # are often generic or misleading, so use them only when PDF text did
        # not provide a value (for example, for a scanned document).
        family = pdf_family or filename_family
        year = pdf_year or filename_year
        round_name = pdf_round or filename_round
        if family not in SUPPORTED_COURSE_FAMILIES or not year:
            raise RuntimeError(
                "Could not identify the course family or academic year from the PDF text, "
                "OCR, or filename. Check that the document contains a readable CAP course "
                "heading and academic year, then retry."
            )
        if data_type == "CUTOFFS" and round_name not in {"C1", "C2", "C3", "C4"}:
            raise RuntimeError(
                "Could not identify CAP round C1-C4 from the PDF text, OCR, or filename. "
                "Check that the document contains a readable CAP round heading, then retry."
            )
        _status(state, "EXTRACTING", f"Extracting {data_type} locally · {family} · {year}",
                data_type=data_type, family=family, year=year, round_name=round_name)
        os.environ["CAPFIND_JOB_CONTROL_DIR"] = str(control)
        outdir = folder / "artifacts"
        outdir.mkdir(exist_ok=True)
        monitor_stop = threading.Event()
        def monitor_progress():
            last_sent = 0.0
            while not monitor_stop.wait(1.0):
                progress_path = control / "progress.json"
                if not progress_path.exists():
                    continue
                try:
                    progress = json.loads(progress_path.read_text(encoding="utf-8"))
                    state.update(page=int(progress.get("page", 0)), total=int(progress.get("total", 0)))
                    if time.time() - last_sent >= 3:
                        _progress(state, state["page"], state["total"], str(progress.get("state", "RUNNING")))
                        last_sent = time.time()
                    if progress.get("state") == "PAUSED":
                        state.update(status="PAUSED", message=f"Paused at page {state['page']} of {state['total']}")
                    elif state.get("status") == "PAUSED":
                        state.update(status="EXTRACTING", message=f"Resumed at page {state['page']} of {state['total']}")
                    _write_state(job_id, state)
                except Exception:
                    # Progress reporting is best-effort; it must never interrupt parsing.
                    pass
        monitor = threading.Thread(target=monitor_progress, daemon=True, name=f"capfind-progress-{job_id}")
        monitor.start()
        try:
            if data_type == "CUTOFFS":
                summary = extract_cutoffs(pdf_path=pdf_path, outdir=outdir, dpi=300, lang="eng", use_camelot=False)
                artifact = outdir / f"{pdf_path.stem}_cutoffs.csv"
                artifact_type = "CUTOFFS"
            else:
                summary = extract_seats(pdf_path=pdf_path, outdir=outdir, dpi=200, lang="eng",
                                        use_ocr=True, force_ocr=False)
                artifact = outdir / f"{pdf_path.stem}_seats_long.csv"
                artifact_type = "SEATS"
        finally:
            monitor_stop.set()
            monitor.join(timeout=2)
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise RuntimeError("The extractor did not produce a non-empty CSV artifact")
        if artifact.stat().st_size > MAX_ARTIFACT_BYTES:
            raise RuntimeError("Extracted CSV exceeds the 150 MiB transfer limit")
        _status(state, "UPLOADING", "Uploading extracted CSV to CAPFind for validation",
                artifact_bytes=artifact.stat().st_size, summary=summary)
        with artifact.open("rb") as handle:
            _remote(
                state, "artifact",
                files={"file": (artifact.name, handle, "text/csv")},
                data={
                    "data_type": artifact_type,
                    "family": family,
                    "year": str(year),
                    "round_name": round_name or "",
                    "source_sha256": actual_sha,
                    "summary_json": json.dumps(summary, ensure_ascii=False),
                },
            )
        _status(state, "DONE", "Extraction uploaded; CAPFind is validating and staging the records",
                summary=summary)
    except Exception as exc:
        if "CAPFIND_WORKER_CANCELLED" in str(exc) or (control / "CANCEL").exists():
            _status(state, "CANCELLED", "Extraction cancelled by the administrator")
            try:
                _remote(state, "cancel")
            except Exception:
                pass
        else:
            _status(state, "FAILED", str(exc)[:3000])
            try:
                _remote(state, "fail", payload={"error": str(exc)[:3000]})
            except Exception:
                pass
    finally:
        os.environ.pop("CAPFIND_JOB_CONTROL_DIR", None)
        with LOCK:
            ACTIVE_JOB = None


def _recover_jobs():
    for path in sorted(DATA.glob("job_*/job.json")):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            job_id = int(state["job_id"])
            JOBS[job_id] = state
            if state.get("status") in {"QUEUED", "EXTRACTING", "UPLOADING"}:
                # The extractor does not serialize all in-memory parser state;
                # after a worker crash, safely restart the PDF from page one.
                control = DATA / f"job_{job_id}" / "control"
                (control / "PAUSE").unlink(missing_ok=True)
                (control / "CANCEL").unlink(missing_ok=True)
                state["status"] = "QUEUED"
                state["message"] = "Recovered after worker restart; extraction will restart from page one"
                _write_state(job_id, state)
        except Exception:
            # A corrupt local job record should not prevent the other jobs starting.
            continue


@app.on_event("startup")
def startup():
    _recover_jobs()
    threading.Thread(target=_queue_loop, daemon=True, name="capfind-local-queue").start()


def _queue_loop():
    global ACTIVE_JOB
    while True:
        with LOCK:
            if ACTIVE_JOB is None:
                queued = sorted(
                    (job_id for job_id, state in JOBS.items() if state.get("status") == "QUEUED")
                )
                if queued:
                    ACTIVE_JOB = queued[0]
                    job_id = ACTIVE_JOB
                else:
                    job_id = None
            else:
                job_id = None
        if job_id is not None:
            _process_job(job_id)
        else:
            time.sleep(0.5)


@app.get("/health")
def health():
    with LOCK:
        return {"ok": True, "worker": "CAPFind Local Extraction Worker", "active_job": ACTIVE_JOB,
                "queued_jobs": sum(s.get("status") == "QUEUED" for s in JOBS.values())}


@app.get("/jobs/{job_id}")
def job_status(request: Request, job_id: int):
    _origin_ok(request)
    state = _load_state(job_id)
    return {k: state.get(k) for k in ("job_id", "status", "message", "page", "total", "updated_at", "error")}


@app.post("/jobs", status_code=202)
async def enqueue_job(
    request: Request,
    file: UploadFile = File(...),
    job_id: int = Form(...),
    backend_url: str = Form(...),
    upload_token: str = Form(...),
    expected_sha256: str = Form(...),
    expected_size: int = Form(...),
):
    _origin_ok(request)
    backend_url = _backend_ok(backend_url)
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise HTTPException(400, "Invalid PDF SHA-256")
    if expected_size < 5 or expected_size > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF size is invalid or exceeds 50 MiB")
    if not upload_token or len(upload_token) > 256:
        raise HTTPException(400, "Invalid one-job authorization token")
    folder = DATA / f"job_{job_id}"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    safe_filename = Path(file.filename or "source.pdf").name
    pdf_path = folder / safe_filename
    tmp_path = folder / (safe_filename + ".upload")
    digest = hashlib.sha256()
    total = 0
    try:
        with tmp_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise HTTPException(413, "PDF exceeds 50 MiB")
                digest.update(chunk)
                out.write(chunk)
        if total != expected_size or digest.hexdigest() != expected_sha256.lower():
            raise HTTPException(400, "PDF size or fingerprint does not match the CAPFind import")
        with tmp_path.open("rb") as inp:
            if inp.read(5) != b"%PDF-":
                raise HTTPException(400, "File is not a valid PDF")
        os.chmod(tmp_path, 0o600)
        tmp_path.replace(pdf_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    state = {
        "job_id": job_id, "filename": Path(file.filename or "source.pdf").name,
        "backend_url": backend_url, "upload_token": upload_token,
        "sha256": expected_sha256.lower(), "size_bytes": expected_size,
        "status": "QUEUED", "message": "Saved locally; queued for extraction",
        "created_at": time.time(), "updated_at": time.time(),
    }
    with LOCK:
        if job_id in JOBS and JOBS[job_id].get("status") not in TERMINAL:
            raise HTTPException(409, "This local job is already queued or running")
        _write_state(job_id, state)
    return {"ok": True, "job_id": job_id, "status": "QUEUED"}


@app.post("/jobs/{job_id}/pause")
def pause_job(request: Request, job_id: int):
    _origin_ok(request)
    state = _load_state(job_id)
    if state.get("status") not in {"QUEUED", "EXTRACTING"}:
        raise HTTPException(409, "Only queued or extracting jobs can be paused")
    control = DATA / f"job_{job_id}" / "control"
    control.mkdir(exist_ok=True)
    (control / "PAUSE").touch()
    _status(state, "PAUSED", "Pause requested; the worker will stop at the next page checkpoint")
    return {"ok": True, "status": "PAUSED"}


@app.post("/jobs/{job_id}/resume")
def resume_job(request: Request, job_id: int):
    _origin_ok(request)
    state = _load_state(job_id)
    if state.get("status") != "PAUSED":
        raise HTTPException(409, "Only paused jobs can be resumed")
    control = DATA / f"job_{job_id}" / "control"
    (control / "PAUSE").unlink(missing_ok=True)
    # A paused job that has not entered its first page checkpoint is still queued.
    resume_status = "QUEUED" if state.get("page") is None else "EXTRACTING"
    _status(state, resume_status, "Resume requested")
    return {"ok": True, "status": resume_status}


@app.post("/jobs/{job_id}/retry")
def retry_job(request: Request, job_id: int):
    _origin_ok(request)
    state = _load_state(job_id)
    if state.get("status") not in {"FAILED", "CANCELLED", "DONE"}:
        raise HTTPException(409, "Only failed/cancelled extraction jobs or completed extractions can be retried")
    control = DATA / f"job_{job_id}" / "control"
    (control / "PAUSE").unlink(missing_ok=True)
    (control / "CANCEL").unlink(missing_ok=True)
    try:
        if state.get("status") == "DONE":
            _remote(state, "revalidate")
            state.update(status="DONE", message="Server validation retry started using the saved extracted CSV",
                         updated_at=time.time())
            _write_state(job_id, state)
            return {"ok": True, "status": "DONE"}
        _remote(state, "restart")
    except Exception as exc:
        raise HTTPException(502, str(exc)[:800])
    state.update(status="QUEUED", message="Retry queued; extraction restarts from page one",
                 page=0, total=0, error=None, updated_at=time.time())
    _write_state(job_id, state)
    return {"ok": True, "status": "QUEUED"}


@app.delete("/jobs/{job_id}")
def delete_local_job(request: Request, job_id: int):
    _origin_ok(request)
    state = _load_state(job_id)
    if state.get("status") not in TERMINAL:
        raise HTTPException(409, "Cancel or finish the local job before deleting its source PDF")
    with LOCK:
        shutil.rmtree(DATA / f"job_{job_id}", ignore_errors=True)
        JOBS.pop(job_id, None)
    return {"ok": True, "job_id": job_id, "deleted": True}


@app.post("/jobs/{job_id}/cancel")
def cancel_job(request: Request, job_id: int):
    _origin_ok(request)
    state = _load_state(job_id)
    if state.get("status") in TERMINAL:
        raise HTTPException(409, "Job is already finished")
    control = DATA / f"job_{job_id}" / "control"
    control.mkdir(exist_ok=True)
    (control / "CANCEL").touch()
    _status(state, "CANCELLED", "Cancellation requested; the worker will stop at the next page checkpoint")
    # A queued job may not enter the extractor loop, so notify Render here as well.
    try:
        _remote(state, "cancel")
    except Exception as exc:
        state["message"] = "Stopped locally; server cancellation sync will need a retry: " + str(exc)[:300]
        _write_state(job_id, state)
        raise HTTPException(502, state["message"])
    return {"ok": True, "status": "CANCELLED"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.local_worker:app", host="127.0.0.1", port=8765, log_level="info")
