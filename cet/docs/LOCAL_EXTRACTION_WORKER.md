# CAPFind Local Extraction Worker

## What it does

- Keeps the source PDF on the computer where the admin selects it.
- Uses CAPFind's existing Python cutoff and seat-matrix extractors locally.
- Persists the queue and source PDF under **data/local_worker/**.
- Sends the extracted CSV artifact and metadata to the authenticated CAPFind API.
- Leaves normalization, validation, duplicate comparison, PostgreSQL staging, review, and approval on the server.
- Runs independently of the browser tab after the PDF has been transferred to the local worker.

The worker binds only to **127.0.0.1:8765**. Do not change it to **0.0.0.0** or expose this port to a LAN or the internet.

## Start and stop

The environment used on the development PC is **~/.venvs/capfind-local-worker**. The start script runs the worker detached, so closing the terminal or browser does not stop extraction.

From the cet directory, run:

- **scripts/start_local_worker.sh**
- **scripts/stop_local_worker.sh**

A desktop autostart entry is installed for the current Linux user. On login, it starts the worker and recovers queued/running jobs. Logs are written to **~/.local/state/capfind-local-worker/worker.log**.

If creating the environment from scratch:

- **python3 -m venv ~/.venvs/capfind-local-worker**
- **~/.venvs/capfind-local-worker/bin/python -m pip install -r requirements-dev.txt**

## Controls and recovery

- **Pause** is cooperative and takes effect at the next page checkpoint.
- **Resume** continues the current in-memory extraction if the process is still alive.
- **Cancel** marks the job cancelled and stops it at the next page checkpoint.
- **Retry after extraction failure** restarts extraction from page one.
- **Retry after server validation failure** reuses the saved CSV artifact when available.
- If the worker process or computer restarts, queued/running jobs are re-queued from page one. The current extractors do not serialize all parser state, so this is a safe restart, not exact-page recovery.

The computer must remain powered on and logged in for desktop autostart to run. The worker does not depend on the browser remaining open after queueing finishes.

## OCR dependency

pytesseract is a Python wrapper, not the Tesseract OCR executable. If a PDF contains scanned pages, install the operating-system package **tesseract-ocr** and ensure **tesseract** is on PATH. Without it, the extractor continues using native PDF text, but OCR-only pages may not produce records.

## Security and data handling

- The browser must be signed in as an authorized CAPFind admin to create a job.
- Each job receives a random, job-scoped bearer token. The server stores only its SHA-256 hash; the local worker keeps the token in the user's local job state so it can upload/retry.
- The worker validates the source PDF's SHA-256 before extraction. The server verifies that fingerprint again when it receives the artifact.
- Local HTTP requests are origin-allow-listed and the worker binds to loopback only.
- The original PDF is not uploaded to Render. The extracted CSV and audit summary are uploaded for server-side validation and staging.
- The local queue and source PDFs are machine-local runtime data and are git-ignored.

## Known integration constraint

The current server pipeline's supported course-family classifier and validators are BCA, BBA, MBA, and MCA. This worker intentionally follows those existing rules rather than broadening the import scope as part of the extraction migration.
