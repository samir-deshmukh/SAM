# Data Model and Integrity

Schema sources: `db/schema_postgres.sql` and `db/admin_schema_postgres.sql`. Verify the live schema before migrations or destructive changes.

Candidate-facing data includes institutions, programs, controlled categories/sections/stages, cutoff facts, seat facts, and derived runtime tables. PostgreSQL is the runtime source of truth; derived summaries/assets must be rebuildable from approved source facts.

Admin control/audit tables track import jobs/steps/events/errors/results, staging records, data releases/release items, and administrative audit actions.

Invariants:
1. Preserve source row grain (course, round, category, stage, year, and source fields).
2. Retain source/page/chunk provenance where supported.
3. Keep invalid rows visible with reasons; no silent drops.
4. Reconcile input = accepted + quarantined + explicitly skipped + failed.
5. Retries cannot duplicate committed facts.
6. Rollback removes only rows attributable to the target release and preserves earlier releases.
7. Schema changes update migration/release documentation and tests.

This file does not claim current production row counts, backups, retention, or live schema parity.
