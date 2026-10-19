# Failure Modes and Recovery

- **PDF/chunk fails:** preserve source/output; record page/chunk and reason; retry only after checking durable writes. Never publish partial output.
- **Lease expires/restart occurs:** preserve existing staging/results for review; requeue only if no durable output exists and the source is available.
- **Database outage:** inspect job/transaction state before retrying. Never run tests against production DB.
- **Validation anomaly:** preserve rejected rows/reasons, compare the source page, add a regression fixture; do not widen a whitelist merely to pass input.
- **Commit/publish failure:** establish whether production rows committed before choosing retry or rollback. Code rollback does not revert data.
- **Missing source/checksum mismatch:** verify configured storage and keep the original source until reconciliation.

Measure or verify job age, expired leases, chunk progress, peak RSS, CPU/time, accepted/quarantined/skipped/failed row counts, DB connection usage, publish verification, and storage errors.
