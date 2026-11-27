---
type: guide
title: "Troubleshooting: Errors, Crashes, OOM and Non-Deterministic Behavior"
description: Entry point for common DuckDB problems — file lock errors, out-of-memory errors (OutOfMemoryException vs. the Linux OOM killer), crashes (termination signals, internal errors, corrupted database/WAL files) and WAL recovery, isolating crashes (disable_optimizer, decomposing queries), CSV inference and extension/S3 issues, and expected non-deterministic results with workarounds.
tags: [troubleshooting, errors, crashes, out-of-memory, wal, file-lock, non-determinism]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-ee32a0d730f7b7637cfaea87
    resource: repo://docs/2.0/guides/troubleshooting/crashes.md
  - id: openwiki-source-67a439937f662c9d7eac608c
    resource: repo://docs/2.0/guides/troubleshooting/oom_errors.md
  - id: openwiki-source-4368e1534682e2cbf2141e72
    resource: repo://docs/2.0/operations_manual/non-deterministic_behavior.md
  - id: openwiki-source-28b1eec55931a453e0841144
    resource: repo://docs/2.0/troubleshooting.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Troubleshooting: Errors, Crashes, OOM and Non-Deterministic Behavior

This page routes the most common DuckDB problems to their fixes and explains crash handling and non-deterministic results.

## Common issues at a glance

| Symptom | Cause / where to look |
| --- | --- |
| `Could not set lock on file` | Only one process may write a database file at a time; another process (editor, notebook kernel, second CLI) still holds it. See [Connecting, Persistence and Concurrency](../connect/connecting-and-concurrency.md). |
| `Out of Memory Error: ...` or `Killed` | See [Out-of-memory errors](#out-of-memory-errors) and [File Formats, Bulk Import, Huge Databases and Out-of-Memory](../performance/file-formats-and-large-data.md). |
| CSV columns have the wrong type or rows fail to parse | [CSV Auto-Detection and Reading Faulty CSV Files](../data/csv/auto-detection-and-faulty-files.md) |
| Extension installation fails (offline, restricted networks) | [Extensions](../configuration/extensions.md); backup repositories are used automatically on 5xx errors |
| S3 / cloud storage access | `httpfs` plus credentials via the [Secrets Manager](../configuration/secrets-manager.md) |
| CLI prints Markdown tables when piped | Agent mode — see [CLI Client](../clients/cli/overview-and-arguments.md) |
| `Current transaction is aborted (please ROLLBACK)` | Since 2.0 any error aborts an explicit transaction — see [Installation, Migration and Footprint](installation-migration-and-footprint.md) |
| `Division by zero in expression (1 // 0)` | Changed in 2.0; use `TRY(1 // 0)` |

## Out-of-memory errors

DuckDB's out-of-core engine spills to disk for larger-than-memory processing, but memory can still run out in two ways:

1. **`OutOfMemoryException`** — an error from DuckDB's allocator, for example:

```console
Out of Memory Error: failed to pin block of size 256.0 KiB (476.7 MiB/476.8 MiB used)
```

2. **Linux OOM killer/reaper** — the OS kills the process to avoid memory overcommitment; you only see `Killed`. Confirm with `sudo dmesg`, which shows an entry such as:

```console
Out of memory: Killed process 54400 (duckdb) total-vm:1037911068kB, anon-rss:770031964kB, ...
```

Remedies (lower `memory_limit` or `threads`, set `preserve_insertion_order = false`, configure `temp_directory`, avoid memory-hungry aggregates) are described in [File Formats, Bulk Import, Huge Databases and Out-of-Memory](../performance/file-formats-and-large-data.md). Note that the memory limit covers only the buffer manager.

## Crashes

DuckDB is thoroughly tested, but bugs can still crash it. Types:

- **Termination signals** (`SIGSEGV`, `SIGABRT`, …) — should never happen; please submit an issue.
- **Internal errors**, e.g. `INTERNAL Error: Attempted to access index 3 within vector of size 3`. Afterwards the database enters a restricted mode and every operation fails with:

```console
FATAL Error:
Failed: database has been invalidated because of a previous fatal error.
The database must be restarted prior to being used again.
```

- **Out of memory** — sometimes a crash is the OS killing the process (see above).
- **Corrupted database or WAL file** — `Corrupt database file: computed checksum [...] does not match stored checksum [...]` or `Failure while replaying WAL file "[...].wal": Corrupt WAL file: ...`. Further calls return a `FATAL` error. Checksum errors are most often a **faulty disk**: run a disk check and try to reproduce on another machine before reporting.

### Recovering data after a crash

If DuckDB was writing to a persistent database, a write-ahead log `⟨database_filename⟩.wal` may sit next to the file. Simply **open the database again**: DuckDB replays the WAL and performs a [checkpoint](../sql/statements/transactions-and-maintenance.md), restoring the state before the crash.

### Isolating a crash

1. **Upgrade**: try the latest stable build (2.0.1), then the preview (nightly) build; or build from source with an open pull request applied.
2. **Search existing issues** in the GitHub tracker for the error message.
3. **Disable the optimizer** to see whether an optimizer rule is responsible, then narrow it down:

```sql
PRAGMA disable_optimizer;
SET disabled_optimizers = 'filter_pushdown,statistics_propagation';   -- selective
```

4. **Reproduce in plain SQL** with the CLI — if it does not reproduce there, the client library is likely involved.
5. **Try different hardware** — overheating drives or overclocked CPUs cause a share of crashes.
6. **Decompose the query** — e.g. download S3 files manually, load them, then run each join separately; the failing step is a good minimal reproducible example.

Submit issues with a minimal reproducible example to the GitHub issue tracker.

## Non-deterministic behavior

Several results are **expected** to vary between runs, threads, compilers, operating systems or architectures, because SQL uses set semantics and DuckDB exploits that for parallelism.

- **Set semantics:** `SELECT * FROM (SELECT 'A' AS x UNION SELECT 'B' AS x);` may return `A, B` or `B, A` — both are correct.
- **Platform-dependent order:** `SELECT array_distinct(['A', 'A', 'B', NULL, NULL]) AS arr;` may return `[A, B]` or `[B, A]`.
- **Floating-point aggregates with multiple threads:** `stddev` and `corr` over a constant column can return tiny values (`0 <= z < 10e-16`) instead of exactly 0:

```sql
CREATE TABLE tbl AS
    SELECT 'ABCDEFG'[floor(random() * 7 + 1)::INT] AS s, 3.7 AS x, i AS y
    FROM range(1, 1_000_000) r(i);
SELECT s, stddev(x) AS standard_deviation, corr(x, y) AS correlation
FROM tbl GROUP BY s ORDER BY s;
```

- Order-dependent functions such as `first()` without `ORDER BY`, and scans of Arrow tables or Polars DataFrames on many threads, can also vary (see [Python Data Ingestion](../clients/python/dataframes-and-arrow.md)).

Workarounds:

```sql
SET threads = 1;                                                        -- remove multi-threading effects
SELECT * FROM (SELECT 'A' AS x UNION SELECT 'B' AS x) ORDER BY ALL;     -- enforce ordering
SELECT list_sort(array_distinct(['A', 'A', 'B', NULL, NULL])) AS i ORDER BY i;
```

See [Order preservation](../sql/dialect/introduction-and-compatibility.md) for which operations keep insertion order.
