# Code and Data Rollback Runbook

Code rollback and data rollback are separate operations.

## Before shipping
Record intended and last-known-good commit SHAs. For imports, record job/release IDs, source fingerprint, and pre-publish row-accounting totals. Test recovery in isolation.

## Code rollback
Stop rollout on failed health checks or incorrect behavior. Redeploy the verified last-known-good SHA through normal hosting controls, then verify health, search, details, admin authentication, and DB connectivity. Do not assume local branch tip equals deployed SHA.

## Data rollback
Identify the release/job/audit trail and inspect release-owned rows. Use the authenticated admin release rollback workflow with an explicit reason. Verify release state, removed rows, preserved earlier rows, audit event, derived data, and public results. Do not use ad hoc production DELETE statements.

## Partial extraction
Preserve staged rows/results. Requeue only when there is no durable output and the source is available. Keep original source files until reconciliation/review is complete.

Acceptance test: in a disposable DB, exercise import → approval → publish → rollback and prove row ownership, audit trail, and derived-data consistency. Not claimed as run here.
