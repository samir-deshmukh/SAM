# Request and Import Flow

## Public request
The browser loads static assets and calls FastAPI endpoints. The API validates parameters, applies rate limits, queries PostgreSQL, and returns bounded results. `/healthz` is lightweight liveness, not proof that every dependency is healthy.

## Server PDF import
1. Authenticated admin uploads a source PDF.
2. Preflight validates the file and records source/job metadata.
3. Worker claims a job lease and runs extraction/normalization.
4. Cutoff extraction uses ten-page chunks via `scripts/chunked_cutoff_extractor.py`.
5. Results are validated and staged with findings/events.
6. Admin reviews and explicitly approves.
7. Approved data is committed to a release and published; derived runtime data is refreshed as required.

## Recovery
If durable staging/results exist after lease expiry, preserve them and route to review rather than blindly rerunning. If no durable output exists and the source remains available, a controlled requeue may start over. Missing source must result in explicit failure.

CSV imports skip PDF parsing but still require validation, staging, review, and approval. This is a repository-backed outline, not a live production trace.
