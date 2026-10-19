# Assumptions Requiring Evidence

| Claim | Status | Evidence needed |
|---|---|---|
| Render runs the current main SHA | Unverified | Compare deployment history and commit SHA |
| Live DB schema matches repository | Unverified | Read-only schema/version check |
| Source PDFs survive deploy/restart | Unverified | Confirm storage backend and retention |
| Ten-page chunks fit memory for largest PDFs | Unverified | Peak RSS/time benchmark under actual service limit |
| Every source row is accounted for | Not proven end-to-end | Reconcile pages, chunk outputs, staging, errors, and release rows |
| All retries are idempotent | Partially covered | Fault-injection tests at each durable-write boundary |
| Rollback preserves earlier releases | Not verified here | Isolated PostgreSQL integration test |
| Dependencies have no known exploitable CVEs | Unverified | Audit resolved release environment |
| MFA is enabled in production | Not established | Inspect deployed auth config/implementation |
| DNS checks alone prevent rebinding | Unsafe assumption | Verify network-level egress restriction |
| PostgreSQL integration tests pass | Unverified in this branch | Run against disposable DB |

Close each item with dated evidence, commit/config version, and test/query used.
