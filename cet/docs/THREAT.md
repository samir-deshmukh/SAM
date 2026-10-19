# Threat Model

Assets: cutoff/seat integrity and provenance, database credentials, admin sessions/CSRF tokens, source files, staging/release/audit records, API and worker availability.

Trust boundaries: public browser/API; admin/API; upload/parser; backend/database; backend/storage; resolver/external websites; CI/dependencies/release.

- Malformed/large PDFs can exhaust memory. Upload limits, serialized processing, and ten-page chunks help, but worst-case peak-RSS and row-accounting tests remain necessary.
- Parser output can be wrong. Validate, stage, review, approve, and reconcile every input row.
- Retry can duplicate/erase data. Preserve durable output and test interruption points.
- Unauthorized admin actions require authentication, role checks, and CSRF; verify negative tests and deployed config.
- Process-local rate limiting is not distributed across instances.
- DNS checks alone do not fully prevent SSRF rebinding; network egress restrictions are stronger.
- Local host filesystems may be ephemeral; verify actual source-storage backend and retention.
- Audit exact release dependencies and scan the release for secrets.

MFA, shared rate limiting, egress enforcement, and source retention remain open risks until verified.
