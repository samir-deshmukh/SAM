# CETFind Engineering Handover

Scope: defense documentation and verification only; no production deployment or database changes.

## Current architecture
Static frontend → FastAPI backend → PostgreSQL. Admin imports pass through preflight, extraction/normalization, validation, staging/review, explicit approval, and release publishing. PostgreSQL is the runtime source of truth; generated runtime data is derived.

## Source-backed locations
- API/application: `backend/api.py`, `backend/main.py`
- Import pipeline: `backend/admin/pipeline.py`, `backend/admin/processing.py`
- Publishing: `backend/admin/publishing.py`
- Schemas: `db/schema_postgres.sql`, `db/admin_schema_postgres.sql`
- Chunk extraction: `scripts/chunked_cutoff_extractor.py`
- Recovery tests: `tests/test_import_recovery_preserves_staging.py`
- Chunk-limit test: `tests/test_chunked_cutoff_extractor.py`

## Safety rules
Preserve user edits; use isolated branches/worktrees; never run tests against production DB; never auto-publish extracted data; never delete durable staging as a generic retry fix; keep source files until reconciliation/review; do not add paid services without permission. Meaningful code comments are required for non-obvious safety rules, retry behavior, resource limits, and data invariants.

## Verification still required
Live Render commit/config, production storage durability, PostgreSQL integration tests, worst-case PDF peak RSS/time, exact source-to-output row reconciliation, and retry idempotency across interruption boundaries are not certified by this documentation.