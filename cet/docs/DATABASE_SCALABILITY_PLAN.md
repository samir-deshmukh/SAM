# CETFind Database Scalability Plan

## Goal

Keep public search fast as CAP data grows by 10x–50x without exposing PostgreSQL publicly or adding infrastructure before the workload requires it.

## Current architecture

`cutoffs` and `seats` are authoritative source tables. Public search currently aggregates `cutoffs` in PostgreSQL and joins `institutes`, `programs`, and `cutoff_college_year_summary`. Runtime detail data is already precomputed into:

- `cutoff_trend_points`
- `cutoff_college_year_summary`
- `cutoff_filter_options`
- `seat_matrix_runtime`
- `college_search_runtime`
- `college_search_cutoff_points`

This is the correct general direction: raw data remains authoritative; serving data is optimized for reads.

## Target architecture

```text
Official CAP PDFs
      |
      v
validated staging
      |
      v
raw authoritative tables
  cutoffs / seats
      |
      +----> ANALYZE / statistics
      |
      v
controlled derived-data build
      |
      +--> search serving data
      +--> trend serving data
      +--> seat serving data
      |
      v
PostgreSQL
      |
      v
FastAPI public API
      |
      v
CETFind frontend
```

## Phase 1 — do now

1. Keep PostgreSQL private.
2. Keep server-side pagination and projection.
3. Keep the 30-second metadata caches.
4. Treat derived runtime tables as the public serving layer.
5. Run `ANALYZE` after large/bulk imports and derived-data rebuilds so PostgreSQL has current statistics.
6. Capture representative search latency at p50/p95/p99.
7. Obtain `EXPLAIN (ANALYZE, BUFFERS)` from inside the private backend network before changing production indexes.

## Phase 2 — when raw cutoffs become materially larger

Do not blindly add indexes. Test candidate indexes against the real plan.

Primary candidates to evaluate:

```sql
-- Existing and important
(program_id, percentile, institution_code)

-- Candidate only after EXPLAIN proves it useful
(program_id, percentile, institution_code) INCLUDE (rank_number)
```

A covering index may reduce heap access for a read-mostly query, but it also increases index size. It must therefore be benchmarked rather than assumed to be an improvement.

City filtering should be evaluated separately. The current `%city%` predicate is not naturally served by a normal B-tree prefix index. If city search becomes a measured bottleneck, first consider normalizing city to a canonical lookup key and using equality; only then consider a specialized text-search index if the product actually needs substring search.

## Phase 3 — dedicated search serving tables (triggered by the November 2026 load test)

Implemented design:

```text
college_search_runtime
----------------------
program_family
institution_code
lowest_rank

college_search_cutoff_points
----------------------------
program_family
institution_code
percentile (exact, unbucketed)
```

The summary table holds one row per college/course. The cutoff-point table holds every distinct raw percentile and its composite primary key supports an indexed per-college lookup. The derived-data rebuild refreshes both tables in the same transaction as the other serving tables. Public search uses a lateral index lookup and retains the raw-table query as a rollout fallback until the course index is populated.

Local comparative validation used a clone of the local 330,281-cutoff database (not the live Render database): BE median query time fell from 378.56 ms to 17.53 ms (21.6x), BCA from 46.44 ms to 12.41 ms (3.7x), while the already-fast MCA query was effectively unchanged. Twenty concurrent unique BE searches completed without errors; the slowest was approximately 151 ms. PostgreSQL used a backward index-only scan on the cutoff-point primary key for the per-college lookup. These are local comparative measurements, not a production capacity guarantee; repeat the bounded test against Render after the serving tables are populated.

Optionally add only fields proven necessary for the public search response.

The table would collapse repeated category/round/section rows from `cutoffs` into the smallest representation required to answer the public search. It should be rebuilt transactionally from the authoritative tables during publication.

The public search would then perform a bounded indexed lookup against this serving table instead of repeatedly aggregating the full raw fact table.

Important: this table must preserve exact percentile semantics. Do not bucket percentiles unless the UI explicitly accepts approximate results.

## Phase 4 — partitioning

Do **not** partition `cutoffs` now.

Partitioning becomes a candidate only when measurements show that the raw table/indexes are large enough that a single relation is materially hurting cache locality, maintenance, or query execution.

If partitioning is eventually justified, the partition key must match the real workload. A year-only partition is not automatically useful because the primary public search does not currently filter by year.

Potential future designs to benchmark:

```text
RANGE(year)
HASH(program_family)
RANGE(year) + HASH(program_family)
```

Choose only after workload simulation. PostgreSQL's own guidance emphasizes partition pruning and warns that excessive or poorly chosen partitions can increase planning time and memory use.

## Phase 5 — database maintenance

After bulk publication:

```sql
ANALYZE cutoffs;
ANALYZE seats;
ANALYZE cutoff_trend_points;
ANALYZE cutoff_college_year_summary;
ANALYZE cutoff_filter_options;
ANALYZE seat_matrix_runtime;
```

Use targeted column statistics later only if `EXPLAIN` shows poor cardinality estimates.

## Benchmark matrix

Before each major schema change, test:

- 1x current data
- 2x
- 5x
- 10x
- 25x
- 50x synthetic scale

Workloads:

- percentile 50 / 80 / 95
- all cities
- common city
- uncommon city
- page 1
- deep page
- alpha / city / rank / competitiveness sort
- 1 / 3 / 5 concurrent requests

Record:

- p50 / p95 / p99
- DB query time
- connection acquisition time
- rows examined/returned
- shared buffers hit/read
- execution plan

## Decision gates

### Green
p95 remains stable as data grows. Make no schema change.

### Yellow
DB execution time rises materially while API/connection time stays low. Investigate query plan, statistics, and serving-table/index design.

### Orange
A serving-table redesign gives a repeatable improvement in a production-like benchmark. Implement it behind the existing derived-data publication process.

### Red
Single-table/index architecture no longer fits the database size or maintenance window. Benchmark partitioning and/or infrastructure scaling.

## Non-goals

- Do not expose PostgreSQL to the internet for diagnostics.
- Do not disable public rate limiting for capacity tests.
- Do not claim a maximum user count from one-client burst tests.
- Do not add indexes solely because they sound faster.
- Do not partition merely because the row count increased.

## Current recommendation

The November 9, 2026 production load test demonstrated that raw cutoff aggregation is the immediate bottleneck: concurrent unique searches drove PostgreSQL CPU to approximately 0.098 of its 0.10 limit, query execution ranged from approximately 1.1 to 6.1 seconds, and the API exhausted its 10-connection pool. The dedicated search serving tables above are therefore the next measured optimization. Before increasing pool size or adding more API instances, validate the new path with result-parity tests, a private `EXPLAIN (ANALYZE, BUFFERS)`, and bounded production load tests. The Render MCP database connection was unavailable because its external IP is not allowlisted; do not expose PostgreSQL to work around this.
