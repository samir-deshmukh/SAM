# Engineering Change Log

This log records verified changes made during the CETFind engineering rebuild. Keep entries short and auditable; link each entry to its exact commit. A commit records a source change, not production deployment or release approval.

## 2026-10-20

### Establish rebuild baseline
- **Commit:** `ebb03f28163d147058eaa78e02cf588dec688847`
- **Scope:** Added `docs/REBUILD_PLAN.md` and created isolated branch `rebuild/cetfind-engineering-baseline` from the known `main` baseline.
- **Purpose:** Record verified architecture, non-negotiable data/security/performance constraints, commit discipline, discovery sequence, and unresolved questions before implementation changes.
- **Validation:** GitHub confirmed the branch creation and file commit. This was a documentation-only change; application tests were not run because no application code changed and this connector session cannot execute the repository's local test suite.
- **Production impact:** None. No Render settings, deployment, database, or production data were changed.
- **Known limitation:** The repository has not yet been fully inventoried or locally tested. The baseline plan explicitly treats the OOM root cause as unproven.

### Record initial repository inventory
- **Commit:** `47bcc8536d0fb11feea03394a08b0478cb3a9640`
- **Scope:** Added `docs/REPOSITORY_INVENTORY.md` based on inspected repository files.
- **Findings:** Identified high-risk memory candidates in whole-file seat comparison and page-audit accumulation, a missing child-process timeout, duplicate CSV reading for progress totals, stale Streamlit-era instructions, and a CI workflow that does not trigger on the new branch's pushes.
- **Validation:** Documentation-only change; source files and production were not modified. Findings are explicitly labeled for further review and measurement, not asserted as confirmed production root causes.
- **Production impact:** None.

### Enable CI push checks on the rebuild branch
- **Commit:** `bcb4f84b977eda63503d97764b29d9cd9aef2bc9`
- **Scope:** Added the isolated rebuild branch to the existing backend-test workflow's push trigger.
- **Purpose:** Make subsequent branch pushes eligible for the repository's existing test workflow without changing the test command or dependencies.
- **Validation:** Workflow file inspected after update. No GitHub Actions run or commit status was returned for this commit, so CI execution is **not verified**; do not treat this as a passing test run.
- **Production impact:** None.

### Align contributor instructions with current architecture
- **Commit:** `9956ca5bb97357f0299b2dd1216bca2298d02764`
- **Scope:** Replaced outdated Streamlit-first contributor instructions with current static frontend + FastAPI + PostgreSQL guidance, data-safety invariants, test commands, security rules, and one-change-per-commit requirements.
- **Validation:** Documentation reviewed against the inspected current architecture and workflow files. Application tests were not run because this was a documentation-only change.
- **Production impact:** None.
