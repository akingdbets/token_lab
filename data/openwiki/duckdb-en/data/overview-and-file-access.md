---
type: "Reference"
title: "Importing Data Overview, File Access, read_text/read_blob and Excel"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-6e48ca94e41639f0bb00c0df
    resource: repo://docs/2.0/data/io.md
  - id: openwiki-source-9264389003a6626e1e41bd56
    resource: repo://docs/2.0/data/overview.md
  - id: openwiki-source-487996b270a2700748e9b39f
    resource: repo://docs/2.0/guides/file_formats/excel_export.md
  - id: openwiki-source-4903b3ca839fb0593ccaf178
    resource: repo://docs/2.0/guides/file_formats/excel_import.md
  - id: openwiki-source-3db4fc6effe21c0e9e31e26b
    resource: repo://docs/2.0/guides/file_formats/file_access.md
  - id: openwiki-source-4b0bb9709d0daeee6a181114
    resource: repo://docs/2.0/guides/file_formats/read_file.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---


# Importing Data Overview, File Access, read_text/read_blob and Excel

DuckDB reads data directly from files, object storage and other databases. This page is the map; format details live on [CSV](csv/reading-and-writing-csv.md), [JSON](json/loading-and-writing-json.md), [Parquet](parquet.md) and [Multiple Files and Partitioning](multiple-files-and-partitioning.md).

## Ways to load data

| Method | Use |
| --- | --- |
| `INSERT INTO people VALUES (1, 'Mark');` | Prototyping; significant per-row overhead, avoid for bulk loading (see [INSERT, UPDATE, DELETE, MERGE](../sql/statements/modifying-data.md)) |
| `SELECT * FROM 'test.csv'` / `read_csv(...)` | Query files directly; the reader is inferred from the extension |
| `CREATE TABLE test AS SELECT * FROM 'test.csv';` | Materialize a file into a table |
| `COPY tbl FROM 'test.csv' (HEADER false);` | Load into an existing table using its schema |
| Appender (C, C++, Go, Java, Julia, Node.js, Python, Rust) | Efficient row-by-row bulk loading without SQL |

```sql
SELECT * FROM 'test.csv.gz';                     -- compressed CSV read directly
SELECT * FROM read_parquet('test.parquet');
COPY tbl FROM 'test.json';
```

**Relative paths** are resolved against the working directory, or against the "root directories" listed in the `file_search_path` setting when it is set.

### Virtual columns: `filename` and `file_index`

Since DuckDB 1.3.0, CSV, JSON and Parquet readers expose a `filename` virtual column; they also expose `file_index`, the zero-based index of the source file in read order:

```sql
COPY (FROM (VALUES (42)) t(x)) TO 'a.parquet';
COPY (FROM (VALUES (43)) t(x)) TO 'b.parquet';
SELECT x, file_index FROM read_parquet(['a.parquet', 'b.parquet']);   -- 42 | 0, 43 | 1
SELECT *, filename FROM 'a.parquet';
```

## Supported data sources

File formats and protocols include CSV, JSON, Parquet, text and blob files (built-in), plus via extensions: AWS S3 and S3-compatible storage, AWS authentication, Azure Blob Storage, Cloudflare R2, HTTP(S) (`httpfs`), Avro, Delta Lake, DuckLake, Excel, Iceberg, Lance tables, Unity Catalog, Vortex files, and databases MySQL, PostgreSQL and SQLite (attach them with [ATTACH](../connect/attach-and-multiple-databases.md)). Credentials for remote sources are managed with the [Secrets Manager](../configuration/secrets-manager.md).

## The `file:` protocol

Supported forms: `file:/some/path` (no host), `file:///some/path` (empty host), `file://localhost/some/path`. Not supported: `file:some/relative/path` and `file://some/path` (non-standard), and remote (non-localhost) hosts.

## `read_text` and `read_blob`

These table functions read whole files (a name, list or glob) into one row per file: `read_text` as `VARCHAR`, `read_blob` as `BLOB`. Both return `filename` (`VARCHAR`), `content`, `size` (`BIGINT`) and `last_modified` (`TIMESTAMP WITH TIME ZONE`).

```sql
SELECT size, parse_path(filename), content
FROM read_text('test/sql/table_function/files/*.txt');

SELECT size, content, filename
FROM read_blob('test/sql/table_function/files/*');
```

- `read_text` validates UTF-8 and suggests `read_blob` on invalid input; it also reads pipes such as `/dev/stdin`.
- Maximum file size: **3.9 GiB** for both.
- Hive-partitioned paths add partition columns (`WHERE part IN ('a', 'b') AND date >= '2012-01-01'`).
- Missing metadata (e.g. no timestamp over HTTP) becomes `NULL`.
- Projection pushdown: omit `content` to list sizes without reading file data.

## Excel (`.xlsx`)

The `excel` extension reads and writes `.xlsx` (not `.xls`).

```sql
SELECT * FROM read_xlsx('test_excel.xlsx');
SELECT * FROM 'test_excel.xlsx';
SELECT * FROM read_xlsx('test_excel.xlsx', sheet = 'Sheet1');        -- default: first sheet
SELECT * FROM read_xlsx('test_excel.xlsx', range = 'A5:Z');          -- skip first 4 rows
SELECT * FROM read_xlsx('test_excel.xlsx', range = '1:100', stop_at_empty = true);
SELECT * FROM read_xlsx('test_excel.xlsx', header = true);
COPY tbl FROM 'test_excel.xlsx' (FORMAT xlsx, SHEET 'Sheet1');       -- coerce to table types
```

| `read_xlsx` behavior | Default / option |
| --- | --- |
| Range | Inferred: from the first row of consecutive non-empty cells to the first empty row; or `range = 'A1:B2'` |
| `stop_at_empty` | `true` without a range, `false` (read to end of range) with a range |
| `header` | First row is a header if all its cells are non-empty strings |
| Types | `TIMESTAMP`, `TIME`, `DATE`, `BOOLEAN` from number formats; text `TRUE`/`FALSE` → `BOOLEAN`; empty cells → `DOUBLE`; otherwise `VARCHAR` or `DOUBLE` |
| `empty_as_varchar` | Treat empty cells as `VARCHAR` |
| `all_varchar` | Disable inference |
| `ignore_errors` | Replace uncastable cells with `NULL` |

Export:

```sql
INSTALL excel;
LOAD excel;
COPY tbl TO 'output.xlsx' WITH (FORMAT xlsx, HEADER true, SHEET 'Sheet1');
COPY (SELECT CAST(a AS VARCHAR), b FROM tbl) TO 'output.xlsx' WITH (FORMAT xlsx);
```

Write conversions: numerics → `DOUBLE`; temporal types → Excel serial numbers with a date/time number format; `TIMESTAMP_TZ`/`TIME_TZ` → UTC `TIMESTAMP`/`TIME` (time zone lost); `BOOLEAN` → `1`/`0` formatted as `TRUE`/`FALSE`; everything else → text.

## I/O settings

> DuckDB ships with safe defaults; these are advanced options.

### Asynchronous I/O (new in DuckDB 2.0)

DuckDB issues reads in the background and keeps several requests in flight while worker threads process arrived data. It is used automatically for Parquet, uncompressed seekable UTF-8 CSV, and DuckDB's native storage (also through DuckLake); other formats such as JSON use synchronous I/O.

- **Thread pools:** worker threads (`threads`, default = CPU cores) and asynchronous I/O threads (`async_threads`, default **four times the system threads, capped at 256**). Many DuckDB instances in one process multiply threads — set both explicitly.
- **`read_ahead_depth`:** `-1` (default, unlimited, bounded by memory and shrinking under pressure), `N > 0` (at most N jobs ahead, no memory budget), `0` (off).
- **`http_client_pool_capacity`** (new in 2.0): derived from CPU and async threads, bounded by the file-descriptor limit, capped at 256.
- Parquet files should have at least as many row groups as threads to keep the network busy.

```sql
SET read_ahead_depth = 64;
SET async_threads = 48;
SET http_retries = 8;
SET http_retry_wait_ms = 50;
SET http_retry_backoff = 2;      -- saturated a 25 Gbit/s link on a 64-core EC2 instance
```

### `fsync_mode`

Controls flushing to stable storage (global): `STANDARD` (default; `fdatasync`/`fsync`, `FlushFileBuffers` on Windows), `FULL` (macOS `F_FULLFSYNC`, otherwise like `STANDARD`), `NONE` (skip sync). `SET fsync_mode = 'NONE';` risks data loss or corruption on OS crash or power loss — only use it for re-creatable databases.
