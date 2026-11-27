---
type: guide
title: "Performance Tuning: Environment, Workload Tuning and Diagnosing Slow Queries"
description: How to get good performance from DuckDB — hardware and OS guidance (1-4 GB per thread, SSD/NVMe, XFS, glibc vs musl, no read-write on NAS), workload tuning by goal (preserve_insertion_order, row groups and threads, spilling, profiling with EXPLAIN ANALYZE, prepared statements, remote files and the external file cache, connection reuse, compression of in-memory tables), the "my workload is slow" checklist, and benchmark notes.
tags: [performance, tuning, threads, memory, profiling, explain-analyze, spilling, remote-files]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-c7771ca092ba293a1efb2626
    resource: repo://docs/2.0/guides/performance/benchmarks.md
  - id: openwiki-source-6d7a5089601963e3a9fb06ff
    resource: repo://docs/2.0/guides/performance/environment.md
  - id: openwiki-source-80da4c973608d617b1b6312c
    resource: repo://docs/2.0/guides/performance/how_to_tune_workloads.md
  - id: openwiki-source-e4df8d12f2cc0a3a99c41611
    resource: repo://docs/2.0/guides/performance/my_workload_is_slow.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Performance Tuning: Environment, Workload Tuning and Diagnosing Slow Queries

DuckDB aims to be fast out of the box with well-chosen defaults. When tuning is worthwhile, there is no single magic setting: identify what you optimize for, change one thing and measure. Related pages: [Schema Design, Indexes and Join Performance](schema-indexes-and-joins.md) and [File Formats, Bulk Import, Huge Databases and Out-of-Memory](file-formats-and-large-data.md).

## "My workload is slow" checklist

1. **Enough memory?** DuckDB works best with **1–4 GB per thread**.
2. **Overcommitting / swapping?** Try *lowering* `memory_limit` below the default 80% of RAM, especially when other processes use more than 20% of memory.
3. **Fast disk?** Network-attached disks slow write-heavy and larger-than-memory workloads; in the cloud prefer instance-attached NVMe SSDs.
4. **Indexes or constraints?** Disable them if possible to speed up loads and updates.
5. **Correct types?** E.g. `TIMESTAMP` for datetimes, not strings.
6. **Parquet layout?** Row groups of 100k–1M rows and files of 100 MB–10 GB.
7. **Query plan?** Study it with `EXPLAIN` / `EXPLAIN ANALYZE`.
8. **Running in parallel?** Watch CPU usage with `htop` or the task manager.
9. **Too many threads?** Limit them with `SET threads = X` (e.g. with HyperThreading).

## Environment

### CPU and memory

- Officially supported: x86_64 (AMD64) and ARM64 (AArch64); other architectures (LoongArch, RISC-V) work without performance guarantees.
- > **Best practice:** aim for **1–4 GB of memory per thread**.
- **Minimum:** about **125 MB per thread** (8 threads → at least 1 GB); otherwise reduce `SET threads = 4;`.
- **Ideal** memory depends more on the queries than on data size: aggregation-heavy workloads need ~1–2 GB/thread, join-heavy (many-to-many) workloads ~3–4 GB/thread.
- Larger-than-memory workloads spill to disk in both persistent and in-memory mode (out-of-core grouping, joining, sorting, windowing).
- On many-core systems with `jemalloc`, consider enabling its background threads.

### Disks and file systems

- Use **SSD or NVMe**; HDDs work but are slow, especially for writes.
- A disk-based database can be **faster** than in-memory because compression is applied on disk but not to in-memory tables by default.
- Linux: **XFS** performs best (ext4 is fine). Windows: NTFS, avoid FAT32. DuckDB has built-in checksums, so file-system integrity checks are not required.
- Cloud block storage (e.g. AWS EBS) works for read-only and read-write workloads.
- **Avoid read-write use of the native format on network-attached storage** (NFS, SMB, Samba): users report slow, unpredictable performance and spurious errors. Read-only is fine; for read-write consider DuckLake.

### Operating system

Use current macOS, Windows or Linux; any mainstream distribution from the last ~5 years works, with Ubuntu LTS recommended. Prefer **glibc** builds — **musl** builds can be **more than 5× slower** on compute-intensive workloads.

## Tuning by goal

| Priority | Consider |
| --- | --- |
| Loading/exporting data larger than memory | `SET preserve_insertion_order = false;` |
| Using all cores | Row group sizing and `threads` |
| Processing data larger than memory | `temp_directory` for spilling |
| Diagnosing a slow query | `EXPLAIN` / `EXPLAIN ANALYZE` |
| Same query with different parameters | Prepared statements |
| Slow or unreliable network | Async I/O settings, reading less data |
| Many small queries | Reuse one connection |

### `preserve_insertion_order`

Large imports/exports to Parquet or CSV can fail with `Out of Memory Error: failed to allocate data of size ...`. Setting `preserve_insertion_order = false` lets DuckDB reorder results without `ORDER BY`, reducing memory (see [order preservation](../sql/dialect/introduction-and-compatibility.md)).

### Parallelism

DuckDB parallelizes over **row groups** (default **122,880 rows** in the native format), so a query needs at least *k* × 122,880 rows to use *k* threads. Set a smaller size for new files with `ATTACH '/tmp/somefile.db' AS db (ROW_GROUP_SIZE 16384);`. Too many threads (e.g. HyperThreading) can slow things down — limit with `SET threads = X`.

### Larger-than-memory workloads

Spill files go to `⟨database_file_name⟩.tmp` (persistent) or `.tmp` (in-memory); change with `SET temp_directory = '/path/to/temp_dir.tmp/';`. The memory-heavy **blocking operators** — `GROUP BY`, `JOIN`, `ORDER BY` and window functions — all support spilling. Limitations: several blocking operators in one query may still run out of memory; some aggregates such as `string_agg()` cannot offload to disk; ordered (holistic) aggregates can OOM on large data.

### Profiling

- `EXPLAIN` prints the physical plan without running it; `EXPLAIN ANALYZE` runs and profiles it (per-operator CPU times sum to more than wall time because of multi-threading). See [DESCRIBE, SHOW, SUMMARIZE, EXPLAIN/Profiling](../sql/statements/inspection-and-metadata.md).
- Look for nested loop joins (prefer hash joins), scans missing a filter pushdown for a later filter, and join orders whose cardinality explodes to billions of tuples.

### Prepared statements

Preparing caches parsing and planning, helping repeated small queries with different parameters with less than ~100 ms runtime. DuckDB is optimized for larger, less frequent queries rather than many small concurrent ones. See [prepared statements](../sql/query-syntax/select-from-where.md).

### Querying remote files

- **Since 2.0**, asynchronous I/O is used for Parquet, uncompressed seekable UTF-8 CSV and DuckDB files (also via DuckLake), so there is no need to raise `threads`; tune `read_ahead_depth`/`async_threads` if needed (see [I/O settings](../data/overview-and-file-access.md)).
- JSON and compressed CSV still use synchronous I/O (one HTTP request per thread); for many small requests set `threads` to about **2–5× the CPU cores**.
- Read less: avoid `SELECT *`, filter remote Parquet, and sort or partition data by commonly filtered columns. `EXPLAIN ANALYZE` reports total requests and bytes transferred.
- **External file cache** (since 1.3.0): inspect with `FROM duckdb_external_file_cache();`. It honors `Cache-Control` (`no-store`, `no-cache`, `private`, stale responses are not reused — e.g. GCS sends `private, max-age=0` for non-public objects). `SET enable_external_file_cache = true;` forces reuse regardless (data is still validated per `validate_external_file_cache`); the cache is shared by all connections, so only do this if all connections may read the files.

### Connections

Reuse a connection: reconnecting per query adds overhead and drops in-memory caches when the last connection closes. A single connection usually works best; a pool is fine. Multiple connections help mainly when bottlenecked by something other than CPU (e.g. network).

### In-memory vs persistent tables

Compression applies to persistent databases, not in-memory tables by default, so on-disk can be faster. TPC-H SF30 Q1 (`CALL dbgen(sf = 30); .timer on; PRAGMA tpch(1);`):

| Setup | Prompt | Time |
| --- | --- | ---: |
| In-memory (uncompressed) | `duckdb` | 0.23 s |
| In-memory (compressed) | `duckdb -cmd "ATTACH ':memory:' AS db (COMPRESS); USE db;"` | 0.15 s |
| Persistent (compressed) | `duckdb tpch-sf30.db` | 0.15 s |

Compression happens at checkpoint, so run an explicit `CHECKPOINT` after loading into a compressed in-memory database.

## Benchmarks

The performance guide's microbenchmarks ran **DuckDB v2.0.0** on a MacBook Pro (18-core M5 Pro, 48 GiB RAM, 1 TB SSD) using TPC-H (generated with the `tpch` extension) and LDBC BI Comment tables (SF100/SF300); scripts are in the `microbenchmarks` directory of `duckdb-web`. Fair benchmarking is hard: use the latest (preferably preview) build. These are not official TPC or LDBC results.
