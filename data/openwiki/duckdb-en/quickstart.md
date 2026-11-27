---
type: guide
title: DuckDB Wiki Quickstart
description: Entry point to the DuckDB 2.0.1 (Cyanoptera) wiki — install DuckDB, open a database file in the CLI, run a first query, query and load a CSV file, try the same from Python, see what is new in DuckDB 2.0, and find the right wiki page for each task.
tags: [quickstart, overview, duckdb-2.0, cli, python, navigation]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T16:06:49.309Z
sources:
  - id: openwiki-source-8534ce7da177cdae31b6f93f
    resource: repo://docs/2.0/quickstart.md
  - id: openwiki-source-f30e0b6664781115de425736
    resource: repo://docs/2.0/whats_new_in_the_docs.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# DuckDB Wiki Quickstart

This wiki covers **DuckDB 2.0.1** (codename *Cyanoptera*). It is a usage-focused digest of the DuckDB documentation: SQL dialect, data import/export, clients, configuration, performance and operations. To try SQL without installing anything, DuckDB also runs in the browser at `https://shell.duckdb.org`.

## First steps with the CLI

1. **Install** DuckDB for your platform (see [Installation, Migration and Footprint](operations/installation-migration-and-footprint.md)); to use it from a programming language, pick a client API instead.
2. **Open a database file** — it is created if missing, and tables you create are saved to it:

```bash
duckdb quickstart.duckdb
```

3. **Run a query:**

```sql
SELECT 6 * 7 AS answer;      -- 42
```

4. **Query a CSV file directly.** Save this as `sales.csv` in the directory where you started DuckDB:

```text
product,quantity,price
Notebook,2,5.00
Pencil,3,1.50
Notebook,1,5.00
```

```sql
SELECT product, sum(quantity * price) AS revenue
FROM read_csv('sales.csv')
GROUP BY product
ORDER BY revenue DESC;       -- Notebook 15.00, Pencil 4.50
```

DuckDB detects the header and column types automatically. Persist the data as a table:

```sql
CREATE TABLE sales AS SELECT * FROM read_csv('sales.csv');
```

5. Enter `.exit` to quit; run `duckdb quickstart.duckdb` again to reopen the database and query `sales`.

CLI options, dot commands and output modes are on [CLI Overview and Arguments](clients/cli/overview-and-arguments.md) and [Dot Commands and Output Formats](clients/cli/dot-commands-and-output-formats.md).

## The same from Python

```python
import duckdb

duckdb.sql("SELECT 6 * 7 AS answer").show()

con = duckdb.connect("quickstart.duckdb")
con.sql("CREATE TABLE sales AS SELECT * FROM read_csv('sales.csv')")
print(con.sql("SELECT product, sum(quantity * price) AS revenue FROM sales GROUP BY product").fetchall())
```

See [Python: Getting Started](clients/python/getting-started.md) for installation, connections and result conversion.

## What's new in DuckDB 2.0

Pages throughout the wiki mark 2.0 features as *new in 2.0*. Highlights:

| Area | Changes | Page |
| --- | --- | --- |
| Server mode | Quack remote protocol, `CONNECT`/`DISCONNECT`, CLI `-serve`/`-connect` | [Connecting and Concurrency](connect/connecting-and-concurrency.md) |
| Types | `VARIANT` as a first-class semi-structured type | [VARIANT and GEOMETRY](sql/data-types/variant-and-geometry.md) |
| Triggers | `CREATE TRIGGER` | [Views, Macros, Types, Triggers](sql/statements/views-macros-and-types.md) |
| SQL dialect | `NEAREST` and explicit-type joins, data-modifying CTEs and `COPY` in CTEs, nested schemas, `$variable` shorthand, grouping by `unnest`, `FETCH FIRST`, `SECURE VIEW`, `SHOW ⟨setting⟩`, `setval` | [Joins](sql/query-syntax/joins.md), [CTEs](sql/query-syntax/ctes-set-operations-unnest.md), [SELECT …](sql/query-syntax/select-from-where.md) |
| `MERGE` / `UPDATE ... FROM` | Defined semantics for multiple matching source rows | [Modifying Data](sql/statements/modifying-data.md) |
| I/O | Asynchronous I/O with background reads and read-ahead (faster object storage) | [File Formats and Large Data](performance/file-formats-and-large-data.md) |
| Storage | Storage format v2.0.0 by default (lazy metadata, better compression, corruption validation); not readable by DuckDB before 2.0 | [Installation, Migration and Footprint](operations/installation-migration-and-footprint.md) |
| Parser | New PEG-based parser; extensions can add grammar (legacy parser available as an extension) | [Introduction and Compatibility](sql/dialect/introduction-and-compatibility.md) |
| Time zones | Native time zone, calendar and collation support in `icu` (replacing the ICU library) | [TIMESTAMP Functions](sql/functions/timestamp.md) |
| Extensions | C API v2 (not yet stable), self-hosted extension repositories | [Extensions](configuration/extensions.md) |
| Export | `PARTITION_PATH` and `ORDER_BY` copy options, new Parquet writer options, GeoJSON | [COPY and EXPORT](sql/statements/copy-and-export.md) |
| CLI | Agent mode, `.history`, `.manual`, pretty-printed `.schema` | [CLI Interactive Features](clients/cli/interactive-features.md) |
| Deprecations | Single-arrow lambda syntax disabled by default; macOS x86_64 community extensions best-effort | [List, Array and Lambda Functions](sql/functions/list-array-and-lambda.md) |

## Where to go next

| Task | Page |
| --- | --- |
| Open persistent or in-memory databases, concurrency | [Connecting and Concurrency](connect/connecting-and-concurrency.md) |
| Attach several databases (DuckDB, SQLite, PostgreSQL, …) | [ATTACH and Multiple Databases](connect/attach-and-multiple-databases.md) |
| Read local or remote files | [Data Import Overview and File Access](data/overview-and-file-access.md) |
| CSV / JSON / Parquet | [Reading and Writing CSV](data/csv/reading-and-writing-csv.md), [Loading and Writing JSON](data/json/loading-and-writing-json.md), [Parquet](data/parquet.md) |
| Globs, Hive partitioning, partitioned writes | [Multiple Files and Partitioning](data/multiple-files-and-partitioning.md) |
| Write query results to files, export a database | [COPY and EXPORT/IMPORT DATABASE](sql/statements/copy-and-export.md) |
| Learn DuckDB's SQL dialect and shortcuts | [Introduction and Compatibility](sql/dialect/introduction-and-compatibility.md), [Friendly SQL](sql/dialect/friendly-sql.md) |
| Write queries | [SELECT, FROM, WHERE …](sql/query-syntax/select-from-where.md), [Joins](sql/query-syntax/joins.md), [GROUP BY …](sql/query-syntax/grouping-and-filtering.md), [Window Functions](sql/functions/window.md) |
| Create and change tables | [CREATE TABLE, Constraints, ALTER TABLE …](sql/statements/create-and-alter-tables.md) |
| Insert, upsert, merge, bulk-load | [INSERT, UPDATE, DELETE, MERGE INTO and the Appender](sql/statements/modifying-data.md) |
| Types and functions | [Data Types Overview and Casting](sql/data-types/overview-and-casting.md), [Functions Overview](sql/functions/overview-numeric-and-utility.md) |
| Inspect schemas and plans | [DESCRIBE, SHOW, SUMMARIZE, EXPLAIN …](sql/statements/inspection-and-metadata.md) |
| Python, pandas, Polars, Arrow | [Python: Getting Started](clients/python/getting-started.md), [DataFrames and Arrow](clients/python/dataframes-and-arrow.md) |
| Settings, extensions, credentials | [Settings and PRAGMAs](configuration/settings-and-pragmas.md), [Extensions](configuration/extensions.md), [Secrets Manager](configuration/secrets-manager.md) |
| Speed up queries, handle large data | [Performance Tuning](performance/tuning-workloads.md), [Schema, Indexes and Joins](performance/schema-indexes-and-joins.md) |
| Transactions and disk space | [Transactions, CHECKPOINT, VACUUM …](sql/statements/transactions-and-maintenance.md) |
| Security and troubleshooting | [Securing DuckDB](operations/security.md), [Troubleshooting](operations/troubleshooting.md) |
