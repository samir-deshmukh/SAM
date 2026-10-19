# CETFind Whiteboard Defense

CETFind helps Maharashtra CET candidates explore college/course options using cutoff and related admission data. Exact live coverage must be checked against the deployed database.

**Architecture:** static frontend → HTTPS → FastAPI → PostgreSQL. Admin imports are preflighted, extracted/normalized, validated, staged, reviewed, explicitly approved, then committed/published. Derived runtime data comes from approved facts.

**Why staging exists:** source PDFs/CSVs are untrusted. Staging separates parser output from public facts; release/audit records explain who approved which change.

**Resource controls:** public search is bounded with SQL aggregation/pagination; server PDF extraction uses ten-page chunks. Neither proves worst-case memory safety or extraction completeness.

**Main threats:** request floods, admin session compromise, malformed PDFs, bad extracted fields, retry duplication, DB outages, source loss, SSRF, dependency compromise.

**Recovery:** code rollback restores a known-good commit; data rollback uses release ownership/audit. Inspect state first, preserve partial staging, retain original files, and verify public results after recovery.

**Evidence still required:** deployed SHA/config, disposable-DB integration tests, large-PDF RSS and row reconciliation, import/review/publish/rollback exercise, auth/CSRF/SSRF checks, dependency and secret audits.
