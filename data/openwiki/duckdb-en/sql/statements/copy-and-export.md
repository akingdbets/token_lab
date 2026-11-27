---
type: reference
title: COPY and EXPORT/IMPORT DATABASE
description: The DuckDB COPY statement — COPY ... FROM to append file data into a table, COPY ... TO to write tables or query results to CSV, Parquet, JSON or BLOB files, general and format-specific options with defaults (ORDER_BY, PARTITION_PATH, RETURN_COLUMN_TYPES and Parquet timestamp options new in 2.0), COPY in CTEs (new in 2.0), COPY FROM DATABASE, and EXPORT/IMPORT DATABASE.
tags: [sql, copy, export, import, csv, parquet, json, blob, statements]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-ea1b8a7c9ee80096fe0e7092
    resource: repo://docs/2.0/sql/statements/copy.md
  - id: openwiki-source-f65322c002dc4cdf8386d0cc
    resource: repo://docs/2.0/sql/statements/export.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# COPY and EXPORT/IMPORT DATABASE

`COPY` moves data between DuckDB and external files: `COPY ... FROM` imports, `COPY ... TO` exports. Built in are CSV, Parquet, JSON (and BLOB for writing); extensions can add formats. Reader-side details are on [Reading and Writing CSV](../../data/csv/reading-and-writing-csv.md), [Parquet](../../data/parquet.md) and [Multiple Files and Partitioning](../../data/multiple-files-and-partitioning.md).

```sql
COPY lineitem FROM 'lineitem.csv';                                   -- auto-detected CSV options
COPY lineitem FROM 'lineitem.csv' (DELIMITER '|');
COPY lineitem FROM 'lineitem.pq' (FORMAT parquet);
COPY lineitem FROM 'lineitem.json' (FORMAT json, AUTO_DETECT true);
COPY lineitem TO 'lineitem.csv' (FORMAT csv, DELIMITER '|', HEADER);
COPY (SELECT l_orderkey, l_partkey FROM lineitem) TO 'lineitem.parquet' (COMPRESSION zstd);
COPY FROM DATABASE db1 TO db2;
COPY FROM DATABASE db1 TO db2 (SCHEMA);                              -- schema only
```

File names may be single-quoted, double-quoted (`"lineitem.csv"`) or unquoted (`lineitem.csv`).

## `COPY ... FROM`

Imports a file into an **existing** table, **appending** to its data. The file's column count must match the table's and values must be convertible to the column types, otherwise an error is raised. With a column list, only those columns are read; other columns get their default values.

```sql
COPY test FROM 'test.csv';
COPY category FROM 'categories.csv' (HEADER);
COPY lineitem FROM 'lineitem.tbl' (AUTO_DETECT true);    -- detect delimiter, quote, header
COPY category(name) FROM 'names.csv';                    -- other columns get defaults
COPY lineitem FROM 'lineitem.parquet' (FORMAT parquet);
COPY lineitem FROM 'lineitem.ndjson' (FORMAT json);      -- newline-delimited JSON
COPY lineitem FROM 'lineitem.json' (FORMAT json, ARRAY true);
```

The source can be an expression in parentheses, e.g. a variable or a prepared-statement parameter:

```sql
SET VARIABLE source_file = 'lineitem.json';
COPY lineitem FROM (getvariable('source_file'));

PREPARE v1 AS COPY lineitem FROM ($1);
EXECUTE v1('lineitem.json');
```

For PostgreSQL compatibility, legacy forms such as `COPY tbl FROM 'tbl.csv' WITH DELIMITER '|' CSV HEADER;` are accepted. `COPY` cannot copy between tables — use `INSERT INTO tbl2 FROM tbl1;` (see [Modifying Data](modifying-data.md)).

## `COPY ... TO`

Writes a whole table (optionally a column list) or a query result to a file. Files written this way can be read back with `COPY ... FROM`.

```sql
COPY lineitem TO 'lineitem.csv';                                         -- CSV with header
COPY lineitem TO 'lineitem.tsv' (DELIMITER '\t', HEADER false);
COPY lineitem(l_orderkey) TO 'orderkey.tbl' (DELIMITER '|');
COPY (SELECT 42 AS a, 'hello' AS b) TO 'query.parquet' (FORMAT parquet);
COPY (SELECT 42 AS a, 'hello' AS b) TO 'query.ndjson' (FORMAT json);
COPY (SELECT 42 AS a, 'hello' AS b) TO 'query.json' (FORMAT json, ARRAY true);
COPY (SELECT l_orderkey, l_comment FROM lineitem) TO 'lineitem_part.parquet' (RETURN_STATS);
```

- `COPY ... TO` **overwrites** an existing destination file without an error. By default (`USE_TMP_FILE`) it writes to a temporary file first and replaces the destination only on success, so an interrupted write does not corrupt the previous file. Reading from and writing to the same file in one statement is not guaranteed to be safe.
- Targets and option values may be expressions: `COPY (SELECT 'hello world') TO (getvariable('target_file'));`, `PREPARE v1 AS COPY (SELECT 42 AS i) TO $1;`, `(FORMAT getvariable('my_format'))`.

**`COPY` in CTEs (new in DuckDB 2.0):** `COPY ... TO` can be a CTE body, returning the number of rows written (`COPY ... FROM` cannot):

```sql
WITH copied(rows_written) AS (
    COPY lineitem TO 'lineitem.csv' (FORMAT CSV, HEADER)
)
SELECT rows_written FROM copied;
```

### Options

Options go in parentheses (`WITH` is optional); values may be quoted or not. Booleans accept `true`/`ON`/`1` and `false`/`OFF`/`0`, and a bare option name (e.g. `(HEADER)`) means `true`.

| Option | Description | Default |
| --- | --- | --- |
| `FORMAT` | Copy function; chosen from the file extension, `CSV` if unknown | `auto` |
| `USE_TMP_FILE` | Write to `target.tmp` first if the target exists | `auto` |
| `OVERWRITE_OR_IGNORE` | Allow overwriting existing files (multi-file writes only) | `false` |
| `OVERWRITE` | Remove all existing files in the target directories (multi-file writes; not on remote file systems) | `false` |
| `APPEND` | Regenerate file names that already exist instead of overwriting (multi-file writes) | `false` |
| `FILENAME_PATTERN` | Pattern with `{uuid}`/`{uuidv4}`, `{uuidv7}` or `{i}` (multi-file writes) | `auto` |
| `FILE_EXTENSION` | Extension for generated files | `auto` |
| `PER_THREAD_OUTPUT` | One file per thread for faster parallel writes | `false` |
| `FILE_SIZE_BYTES` | Write into a directory, starting a new file past this approximate size (`1000`, `1k`, …) | (empty) |
| `PARTITION_BY` | Hive-partitioning columns | (empty) |
| `PARTITION_PATH` | Expression over the `PARTITION_BY` columns computing a relative subdirectory instead of `col=value` (new in 2.0) | (empty) |
| `ORDER_BY` | Sort rows before writing (within each partition with `PARTITION_BY`) (new in 2.0) | (empty) |
| `PRESERVE_ORDER` | Preserve order while copying | `preserve_insertion_order` |
| `RETURN_FILES` | Add a `files VARCHAR[]` result column | `false` |
| `RETURN_STATS` | Return written files with column statistics | `false` |
| `RETURN_COLUMN_TYPES` | Add a `columns` result column with each written column's name and DuckDB type (new in 2.0) | `false` |
| `WRITE_PARTITION_COLUMNS` | Also write partition columns into the files | `false` |

```sql
COPY (
    SELECT 1.23::DECIMAL(10, 2) AS amount,
           '00000000-0000-0000-0000-000000000001'::UUID AS id
) TO 'out.csv' (RETURN_COLUMN_TYPES);
-- Count = 1, columns = [{'name': amount, 'type': 'DECIMAL(10,2)'}, {'name': id, 'type': UUID}]
```

### CSV write options

| Option | Default |
| --- | --- |
| `COMPRESSION` (`none`, `gzip`, `zstd`; from extension, e.g. `.csv.gz`) | `auto` |
| `DELIM` / `SEP` | `,` |
| `HEADER` | `true` |
| `QUOTE` / `ESCAPE` | `"` / `"` |
| `NEW_LINE` (escaped strings, e.g. `E'\x1e'`) | `\n` |
| `NULLSTR` | (empty) |
| `FORCE_QUOTE` (columns always quoted) | `[]` |
| `DATEFORMAT`, `TIMESTAMPFORMAT` | (empty) |
| `PREFIX` + `SUFFIX` (both required, need `HEADER false`) | (empty) |

### Parquet write options

| Option | Default |
| --- | --- |
| `COMPRESSION` (`uncompressed`, `snappy`, `gzip`, `zstd`, `brotli`, `lz4`, `lz4_raw`) | `snappy` |
| `COMPRESSION_LEVEL` (zstd only, 1–22) | `3` |
| `ROW_GROUP_SIZE` (alias `CHUNK_SIZE`) | `122880` |
| `ROW_GROUP_SIZE_BYTES` (only with `SET preserve_insertion_order = false`) | |
| `ROW_GROUPS_PER_FILE` | |
| `PARQUET_VERSION` (`V1`, `V2`) | `V1` |
| `FIELD_IDS` (`'auto'` or a struct such as `{i: 42}`) | (empty) |
| `KV_METADATA` (footer key-value metadata) | (empty) |
| `SHREDDING` (shred `VARIANT` columns into a type) | (empty) |
| `DATA_PAGE_SIZE_LIMIT` | `104857600` (100 MiB) |
| `DICTIONARY_SIZE_LIMIT` (`0` disables dictionary encoding) | `ROW_GROUP_SIZE / 5` |
| `WRITE_BLOOM_FILTER` / `BLOOM_FILTER_FALSE_POSITIVE_RATIO` | `true` / `0.01` |
| `GEOPARQUET_VERSION` (`NONE`, `V1`, `V2`, `BOTH`) | `V1` |
| `TIMESTAMP_IS_ADJUSTED_TO_UTC` (`AUTO`, `TRUE`, `FALSE`; new in 2.0) | `AUTO` |
| `WRITE_TIMESTAMP_AS_INT96` (legacy readers; new in 2.0) | `false` |

```sql
COPY (SELECT {i: 128} AS my_struct) TO 'my.parquet'
    (FIELD_IDS {my_struct: {__duckdb_field_id: 42, i: 43}});
```

### JSON and BLOB write options

JSON: `ARRAY` (default `false` = newline-delimited; `true` = one JSON array of records), `COMPRESSION` (`auto`), `DATEFORMAT`, `TIMESTAMPFORMAT`.

```sql
COPY (SELECT 'QUACK!' AS hello) TO 'quack.json';        -- {"hello":"QUACK!"}
```

`FORMAT BLOB` writes a single `BLOB` column to a file (`COMPRESSION` defaults to `auto`):

```sql
COPY (SELECT 'foo'::BLOB) TO 'blob_output.blob' (FORMAT BLOB);
```

## `COPY FROM DATABASE ... TO`

Copies everything from one [attached database](../../connect/attach-and-multiple-databases.md) to another — schema (constraints, indexes, sequences, macros) and data:

```sql
ATTACH 'db1.db' AS db1;
CREATE TABLE db1.tbl AS SELECT 42 AS x, 3 AS y;
CREATE MACRO db1.two_x_plus_y(x, y) AS 2 * x + y;

ATTACH 'db2.db' AS db2;
COPY FROM DATABASE db1 TO db2;
SELECT db2.two_x_plus_y(x, y) AS z FROM db2.tbl;     -- 87
```

## `EXPORT DATABASE` and `IMPORT DATABASE`

`EXPORT DATABASE` writes the full database — schema, tables, views, sequences — to a directory; `IMPORT DATABASE` reads it back. Options are the `COPY ... TO` options.

```sql
EXPORT DATABASE 'target_directory';                                    -- CSV
EXPORT DATABASE 'target_directory' (FORMAT csv, DELIMITER '|');
EXPORT DATABASE 'target_directory' (FORMAT parquet);
EXPORT DATABASE 'target_directory' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 100_000);

IMPORT DATABASE 'source_directory';
PRAGMA import_database('source_directory');
```

The directory contains `schema.sql` (the `CREATE SCHEMA/TABLE/VIEW/SEQUENCE` statements), `load.sql` (one `COPY` per table) and one data file per table; running `schema.sql` then `load.sql` manually is equivalent to `IMPORT DATABASE`.

- **Import into an empty database:** `schema.sql` uses plain `CREATE` (no `OR REPLACE` / `IF NOT EXISTS`), so any existing object (e.g., a user-defined type) causes an "already exists" error.
- **Triggers** are not exported in DuckDB 2.0.0, and `COPY FROM DATABASE` does not copy them either — recreate them manually.
