# Engineering Constraints and Invariants

- Confirm repository, branch, commit, and diff before editing; preserve existing work in an isolated worktree.
- Tests must use a disposable database through `TEST_DATABASE_URL`, never production `DATABASE_URL`.
- Import sequence: preflight → extract/normalize → validate → stage/review → explicit approval → commit/publish.
- Every source row must be accepted, quarantined, explicitly skipped with a reason, or failed with a reason. No silent loss.
- Retries must not duplicate committed rows or erase durable staging/results. Restart never implicitly approves an import.
- Keep original source files until validation, review, and reconciliation are complete.
- Server cutoff extraction currently uses ten-page chunks. Do not increase chunk size without measuring peak RSS, duration, failures, and exact row accounting on representative PDFs. A page-count limit is not a hard memory cap.
- Treat PDFs, CSVs, extracted text, filenames, URLs, and request fields as untrusted.
- Preserve authentication, authorization, CSRF, upload validation, path safety, and SSRF controls. Trust forwarded IP headers only from configured proxies.
- Do not claim source durability until the active storage backend is verified; do not add paid services without approval.
- **Meaningful comments are required:** explain why a guard, retry rule, resource bound, or invariant exists; do not merely restate the code.
- Ship gate: tests, full diff review, secret/dependency scan, row reconciliation, isolated publish/rollback test, and verified rollback trigger.
