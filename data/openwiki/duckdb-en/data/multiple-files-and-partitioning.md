---
type: guide
title: Multiple Files, Globbing, Schema Combination and Hive Partitioning
description: Read many CSV, Parquet or JSON files at once with lists, glob patterns and directory paths, handle empty matches (allow_empty, glob()), add a filename column, combine differing schemas by position or with union_by_name, read Hive-partitioned datasets with filter pushdown and hive_types, and write partitioned datasets with COPY ... PARTITION_BY, FILENAME_PATTERN, PARTITION_PATH and ORDER_BY.
tags: [multiple-files, glob, union-by-name, hive-partitioning, partition-by, partitioned-writes, filename]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-e6b34ae06010354a97267e00
    resource: repo://docs/2.0/data/multiple_files/combining_schemas.md
  - id: openwiki-source-ad4045b42d6623baf54ef199
    resource: repo://docs/2.0/data/multiple_files/overview.md
  - id: openwiki-source-4597d4a12b78b6cfa462613c
    resource: repo://docs/2.0/data/partitioning/hive_partitioning.md
  - id: openwiki-source-f7af88537b36c2f0b623ea07
    resource: repo://docs/2.0/data/partitioning/partitioned_writes.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Multiple Files, Globbing, Schema Combination and Hive Partitioning

All of DuckDB's file readers (`read_csv`, `read_parquet`, `read_json`) can treat many files as one table. Format-specific options are on [Reading and Writing CSV Files](csv/reading-and-writing-csv.md), [Parquet Files](parquet.md) and [Loading and Writing JSON Files](json/loading-and-writing-json.md).

## Reading multiple files

```sql
SELECT * FROM 'dir/*.csv';                                     -- files in dir
SELECT * FROM '*/*/*.csv';                                     -- two directories deep
SELECT * FROM 'dir/**/*.csv';                                  -- any depth
SELECT * FROM read_csv(['flights1.csv', 'flights2.csv']);      -- explicit list
SELECT * FROM read_parquet(['folder1/*.parquet', 'folder2/*.parquet']);   -- list of globs
SELECT * FROM read_parquet('dir');                             -- directory path
```

### Glob syntax

| Wildcard | Matches |
| --- | --- |
| `*` | Any number of any characters (including none) |
| `**` | Any number of subdirectories (including none) |
| `?` | Any single character (not supported over S3 due to HTTP encoding) |
| `[abc]` | One character from the set |
| `[a-z]` | One character from the range |

### Directory paths

`read_parquet('dir')` recursively reads files with the `.parquet` extension, equivalent to `read_parquet('dir/**/*.parquet')` (trailing slash optional); `read_parquet('dir/*.parquet')` reads only the top level. Other extensions are ignored even if they contain Parquet data — list them explicitly. An empty directory raises an error.

### No matching files

A glob that matches nothing raises `IO Error: No files found that match the pattern "test/*.parquet"`. **Since DuckDB 2.0**, CSV, JSON and Parquet readers accept `allow_empty = true`, returning an empty result with a single `BOOLEAN` column named `empty`. Alternatively check first with the `glob` table function, which returns an empty result instead of erroring:

```sql
SELECT * FROM read_parquet('test/*.parquet', allow_empty = true);
SELECT count(*) AS matches FROM glob('test/*.parquet');
SELECT * FROM glob('*');                                       -- column: file
```

### The `filename` column

```sql
SELECT * FROM read_csv(['flights3.csv', 'flights4.csv'], union_by_name = true, filename = true);
```

The `filename` option adds a column showing each row's source file; pass a string (e.g. `filename = 'input_file'`) to choose the column name and avoid collisions with an existing `filename` column. Since DuckDB 1.3.0, readers also expose `filename` as a virtual column (`SELECT filename, * FROM 'todos-*.json'`).

## Combining schemas

Files can have different schemas. DuckDB offers two ways to unify them.

**By position (default).** DuckDB reads the schema of the **first file** and matches subsequent files to it by column name: columns missing from the first file are **silently dropped**, and columns of the first file missing in a later file cause an error. This equals `UNION ALL` and works when all files share a schema.

**By name.** `union_by_name = true` unifies columns by name and fills missing values with `NULL`, equivalent to `UNION ALL BY NAME`. It **increases memory consumption**.

```sql
SELECT * FROM read_csv('flights*.csv');                        -- by position
SELECT * FROM read_csv(['flights3.csv', 'flights4.csv'], union_by_name = true);
```

| FlightDate | OriginCityName | DestCityName | UniqueCarrier |
| --- | --- | --- | --- |
| 1988-01-01 | New York, NY | Los Angeles, CA | NULL |
| 1988-01-03 | New York, NY | Los Angeles, CA | AA |

Without `union_by_name`, `UniqueCarrier` from `flights4.csv` would be dropped (or the reversed order would error). Directory paths do not change schema combination.

## Reading Hive-partitioned data

Hive partitioning stores files in folders named `key=value`, e.g. `orders/year=2022/month=11/file.parquet`. The partition values become columns:

```sql
SELECT * FROM read_parquet('orders/*/*/*.parquet', hive_partitioning = true);
```

- **Filter pushdown:** filters on partition keys skip unneeded files, so `WHERE year = 2022 AND month = 11` reads only that folder.
- **Auto-detection:** by default DuckDB detects the `key=value` pattern and enables `hive_partitioning` automatically; set `hive_partitioning = false` to exclude the partition columns.
- **Types:** `DATE`, `TIMESTAMP` and `BIGINT` are auto-detected; specify others with `hive_types`, or disable autocasting with `hive_types_autocast = 0`.

```sql
SELECT *
FROM read_parquet('dir/**/*.parquet', hive_partitioning = true,
                  hive_types = {'release': 'DATE', 'orders': 'BIGINT'});
```

- **NULL values:** a SQL `NULL` partition value is written as `__HIVE_DEFAULT_PARTITION__` and read back as `NULL`; the text `'NULL'` is a different value (`bucket=NULL`).

## Writing partitioned data: `COPY ... PARTITION_BY`

```sql
COPY orders TO 'orders' (FORMAT parquet, PARTITION_BY (year, month));
COPY orders TO 'orders' (FORMAT csv, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE);
COPY orders TO 'orders' (FORMAT csv, PARTITION_BY (year, month), COMPRESSION gzip, FILE_EXTENSION 'csv.gz');
```

`PARTITION_BY` cannot take expressions; compute columns in a subquery:

```sql
COPY (SELECT *, year(timestamp) AS year, month(timestamp) AS month FROM services)
TO 'test' (PARTITION_BY (year, month));
```

- The target is the root directory; partition values come from the data. Many partitions create many files and are expensive — aim for **at least 100 MB per partition**.
- `SET partitioned_write_max_open_files = 10;` limits files kept open before flushing (default **100**).
- **File names** default to `data_0.parquet` / `data_0.csv`; `FILENAME_PATTERN` accepts `{i}` (index) and `{uuid}` (128-bit UUID): `FILENAME_PATTERN 'orders_{i}'`, `FILENAME_PATTERN 'file_{uuid}'`.
- **Overwriting:** not allowed by default. On local file systems `OVERWRITE` and `OVERWRITE_OR_IGNORE` remove existing directories; remote file systems do not support overwriting.
- **Appending:** `APPEND` behaves like `OVERWRITE_OR_IGNORE, FILENAME_PATTERN '{uuid}'` but also regenerates the UUID if a file already exists.
- Slashes in column names: use percent-encoding via `url_encode`.

### Custom partition paths (new in DuckDB 2.0)

`PARTITION_PATH` replaces the default `col=value` layout with an expression over the `PARTITION_BY` columns, evaluated once per partition and cast to `VARCHAR`. The path must be relative, non-empty and free of `..`; it requires `PARTITION_BY` and cannot be combined with `HIVE_FILE_PATTERN`.

```sql
COPY sales TO 'sales'
(FORMAT parquet, PARTITION_BY (region),
 PARTITION_PATH CASE
     WHEN region = 'eu' THEN 'europe'
     ELSE 'region=' || coalesce(region, 'unknown')
 END);

SELECT hive_partition_component('year', 2024);        -- year=2024 (NULL → __HIVE_DEFAULT_PARTITION__)
SELECT path_join('dir', 'subdir', 'file.txt');        -- dir/subdir/file.txt
```

### Sorting within partitions (new in DuckDB 2.0)

`ORDER_BY` sorts rows before writing; with `PARTITION_BY` it sorts within each partition. Each expression may have `ASC`/`DESC` and `NULLS FIRST`/`NULLS LAST`:

```sql
COPY orders TO 'orders'
(FORMAT parquet, PARTITION_BY (year, month), ORDER_BY (amount DESC NULLS LAST));
```

All `COPY` options are listed in [COPY and EXPORT/IMPORT DATABASE](../sql/statements/copy-and-export.md); the Python `write_parquet(partition_by=...)` maps to the same mechanism.
