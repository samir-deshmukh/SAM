# Alternatives and Trade-offs

- **Server vs local extraction:** server processing simplifies workflow but competes for constrained memory; local processing keeps parsing on the user's machine but requires a running worker and secure transfer. Do not silently switch data paths.
- **Ten-page vs larger chunks:** smaller chunks reduce per-call page count and failure blast radius; larger chunks may reduce overhead but increase memory. Change only after benchmarking RSS, wall time, failures, and exact row counts.
- **PostgreSQL vs static artifacts:** database facts are authoritative; generated files are faster but can be stale. Verify publish consistency.
- **Process-local vs shared rate limiting:** local limiter avoids extra infrastructure but is not globally consistent across instances.
- **Local filesystem vs object storage:** local is simple but may be ephemeral; object storage adds configuration/cost. Never claim durability before verifying the backend.
- **Automatic retry vs review:** retry only when no durable output exists; preserve existing output for review otherwise.

Choose based on integrity, privacy, reliability, and zero-added-cost constraints—not intuition alone.
