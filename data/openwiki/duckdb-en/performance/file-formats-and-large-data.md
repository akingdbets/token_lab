---
type: guide
title: File Formats, Bulk Import, Huge Databases and Out-of-Memory
description: Performance guidance for data at scale — when to query Parquet directly vs. load it into DuckDB, Parquet row group and file sizes, Hive partitioning, compressed and many-small CSV files, DuckLake storage, recommended bulk import methods, configuration and schema tips against out-of-memory errors, and working with multi-terabyte database files.
tags: [performance, parquet, row-group, csv, bulk-import, out-of-memory, huge-databases, ducklake]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-67041ab417ab3407b36ed8a4
    resource: repo://docs/2.0/guides/performance/file_formats.md
  - id: openwiki-source-73e7596f851b0601a5e0f31f
    resource: repo://docs/2.0/guides/performance/import.md
  - id: openwiki-source-3a48b87cebfb8c70687bc851
    resource: repo://docs/2.0/guides/performance/oom.md
  - id: openwiki-source-9ffc80798439bd4a6633377e
    resource: repo://docs/2.0/guides/performance/working_with_huge_databases.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# File Formats, Bulk Import, Huge Databases and Out-of-Memory

This page covers performance decisions that depend on how data is stored and loaded. General tuning (threads, profiling, the slow-workload checklist) is on [Performance Tuning](tuning-workloads.md); schema, index and join tuning on [Schema Design, Indexes and Join Performance](schema-indexes-and-joins.md).

## Query Parquet directly or load it?

**Reasons to query Parquet directly**

- Parquet is columnar with basic statistics (zonemaps), so projection and filter pushdown work well; workloads mixing projection, filtering and aggregation perform well on raw files.
- **Storage:** loading needs roughly the same space again for the DuckDB file — with limited disk, query the files.

**Reasons to load into DuckDB**

- DuckDB's format has **HyperLogLog statistics** that Parquet lacks, improving cardinality estimates, especially for join-heavy queries. If DuckDB picks a bad join order on Parquet, try loading the data.
- **Repeated queries** are always somewhat faster on DuckDB tables, amortizing load time.
- **Heavy compression** (e.g. gzip) costs decompression on every access; Snappy, LZ4 and zstd are lighter. Check with `parquet_metadata`.

Microbenchmark: TPC-H SF30 ran **1.1–4.1× slower (2.8× median)** on default-settings Parquet than on a DuckDB database.

> **Best practice:** with storage available and a join-heavy or repeated-query workload, load Parquet into the database first. Study compression and row group sizes with `parquet_metadata`.

### Row group sizes

DuckDB parallelizes **over row groups**, so a file with one giant row group is processed by a single thread. DuckDB works best with **100K–1M rows per row group**. Aggregation microbenchmark:

| Row group size | Time |
| ---: | ---: |
| 2,048 | 10.35 s |
| 4,096 | 4.81 s |
| 8,192 | 3.38 s |
| 30,720 | 3.00 s |
| 122,880 | 2.81 s |
| 491,520 | 2.79 s |
| 1,966,080 | 2.81 s |

2,048-row groups are ~3.7× slower than ideal and 4,096 still 1.7×; above ~60,000 rows differences are about 5%. DuckDB's writer rounds `ROW_GROUP_SIZE` up to a multiple of 2,048 (the vector size); the default is 122,880.

### File sizes and partitioning

- Have **at least as many total row groups across all files as CPU threads** (10 threads: 10 files × 1 row group or 1 file × 10 row groups).
- > **Best practice:** keep individual Parquet files between **100 MB and 10 GB**.
- Use a **Hive-partitioned** folder layout on commonly filtered columns so only matching folders are read — especially helpful for remote files (see [Multiple Files and Hive Partitioning](../data/multiple-files-and-partitioning.md)).

More writing tips (sorting before writing, `PER_THREAD_OUTPUT`) are in [Parquet Files](../data/parquet.md).

## CSV files

**Compressed CSV:** decompressing on the fly is typically faster than decompressing first, thanks to reduced I/O. LDBC Comment SF100 (7.3 GiB `.csv.gz`, 24 GiB uncompressed): **13.5 s** loading `.csv.gz` directly vs **18.5 s** decompressing with parallel `gzip` then loading.

**Many small CSV files:** the sniffer runs on every file, which can dominate. If all files share a dialect and schema, sniff one and disable detection:

```sql
.mode line
SELECT Prompt FROM sniff_csv('part-0001.csv');
FROM read_csv('part-*.csv', auto_detect=false, delim=',', quote='"', escape='"', new_line='\n',
              skip=0, header=true, columns={'hello': 'BIGINT', 'world': 'VARCHAR'});
```

## Reducing storage with DuckLake

DuckLake stores data as Parquet files with configurable compression, which can be much smaller than CSV or even DuckDB's native format:

```sql
ATTACH 'ducklake:metadata.ducklake' AS d;
CALL d.set_option('parquet_compression', 'zstd');
CALL d.set_option('parquet_version', 2);
CALL d.set_option('parquet_compression_level', 22);
COPY FROM DATABASE services TO d;
```

High zstd levels trade slower writes for smaller files — best for write-once, read-many data.

## Bulk import

Recommended order when importing from other systems:

1. A **scanner extension** if available: MySQL, PostgreSQL, SQLite, or the generic ODBC scanner (see [ATTACH](../connect/attach-and-multiple-databases.md)).
2. The source system's **bulk export** to Parquet or CSV, then DuckDB's Parquet/CSV loaders.
3. The **Appender** (C, C++, Go, Java, Julia, Node.js, Python, Rust) — see [INSERT, UPDATE, DELETE, MERGE INTO and the Appender](../sql/statements/modifying-data.md).

Avoid row-by-row inserts in loops — even with prepared statements they are slow.

> **Best practice:** unless your data is small (**< 100k rows**), avoid inserts in loops.

## Out-of-memory issues

Configuration to try:

```sql
SET threads = ⟨lower_than_the_number_of_available_threads⟩;
SET memory_limit = ⟨lower_than_80%_of_system_memory⟩;
SET preserve_insertion_order = false;
```

- Fewer threads reduce concurrent memory use.
- Lowering `memory_limit` below the default 80% sounds counter-intuitive but helps, because some operations bypass the buffer manager. If the OS or OOM reaper kills DuckDB, set it to **50–60%** of system memory.
- `preserve_insertion_order = false` helps queries that read or write large amounts of data.
- **Schema:** use the most restrictive types (e.g. `TINYINT`). Bitpacking keeps small values small on disk, but larger types still use more memory during processing.
- **Indexes** significantly increase memory use and are not buffer-managed; avoid them where possible or lower the memory limit to accommodate them.
- `operator_memory_limit` (new in 2.0) caps per-connection sort/hash memory; `temp_directory` and `max_temp_directory_size` control spilling (see [Configuration Options](../configuration/settings-and-pragmas.md)).

Error symptoms and diagnosis (`OutOfMemoryException`, `Killed`, `dmesg`) are on [Troubleshooting](../operations/troubleshooting.md).

## Working with huge databases

DuckDB's format has no practical size limit (1% of 2024 survey respondents used files of 2 TB+, ≈10 TB of CSV). Keep in mind:

1. **Object storage limits** file sizes — e.g. AWS S3 allows at most **5 TB** per object.
2. **Checkpointing can be slow** — adding a few rows to TPC-H SF1000 and checkpointing takes about **5 seconds**.
3. On block storage the **file system matters**; on Linux DuckDB performs best with **XFS** for large files.

For large data consider **DuckLake**, which spreads data over many immutable Parquet files, sidestepping object-size limits and whole-database checkpoints while keeping transactional guarantees.
