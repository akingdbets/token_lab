---
type: reference
title: Reading and Writing CSV Files
description: Import CSV files with read_csv (or a bare 'file.csv' path), COPY ... FROM and CREATE TABLE AS, the full read_csv parameter list with defaults (delim, header, columns, types, nullstr, sample_size, union_by_name, allow_empty, ...), practical import tips, and exporting CSV with COPY ... TO and its CSV write options.
tags: [csv, read-csv, copy, import, export, parameters, union-by-name]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-b18d25ee8de839828d63c128
    resource: repo://docs/2.0/data/csv/overview.md
  - id: openwiki-source-a5279b59bd0f810ef7df3744
    resource: repo://docs/2.0/data/csv/tips.md
  - id: openwiki-source-0b401df4c9d2411e3600a8f2
    resource: repo://docs/2.0/guides/file_formats/csv_export.md
  - id: openwiki-source-ea1b8a7c9ee80096fe0e7092
    resource: repo://docs/2.0/sql/statements/copy.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Reading and Writing CSV Files

DuckDB's CSV reader auto-detects dialect, types and header (see [CSV Auto-Detection and Reading Faulty CSV Files](auto-detection-and-faulty-files.md)), so most files load with no options at all. The examples use a file `flights.csv`:

```csv
FlightDate|UniqueCarrier|OriginCityName|DestCityName
1988-01-01|AA|New York, NY|Los Angeles, CA
```

## Reading CSV

```sql
SELECT * FROM 'flights.csv';                   -- infer read_csv from the extension
SELECT * FROM read_csv('flights.csv');

SELECT *
FROM read_csv('flights.csv',
    delim = '|',
    header = true,
    columns = {
        'FlightDate': 'DATE',
        'UniqueCarrier': 'VARCHAR',
        'OriginCityName': 'VARCHAR',
        'DestCityName': 'VARCHAR'
    });
```

```batch
cat flights.csv | duckdb -c "SELECT * FROM read_csv('/dev/stdin')"
```

Paths may be relative (to the working directory) or absolute; globs and lists read multiple files (see [Multiple Files, Globbing and Hive Partitioning](../multiple-files-and-partitioning.md)). Remote paths (HTTP, S3, …) work via `httpfs` (see [Importing Data Overview](../overview-and-file-access.md)).

**Auto-detection** (`auto_detect`) is on by default. Setting an option explicitly does **not** disable it: the sniffer still detects every other option and your value overrides only that one. Use `auto_detect = false` to disable it entirely.

### Loading into tables

```sql
CREATE TABLE ontime AS SELECT * FROM read_csv('flights.csv');
CREATE TABLE ontime AS FROM 'flights.csv';               -- FROM-first syntax
INSERT INTO tbl SELECT * FROM read_csv('input.csv');
INSERT INTO tbl BY NAME SELECT * FROM read_csv('input.csv');   -- table has more columns than the file

CREATE TABLE ontime (FlightDate DATE, UniqueCarrier VARCHAR, OriginCityName VARCHAR, DestCityName VARCHAR);
COPY ontime FROM 'flights.csv';
COPY ontime FROM 'flights.csv' (DELIMITER '|', HEADER);
```

`COPY ... FROM` uses the **table's schema** instead of detecting types, which is faster and avoids detection mistakes; column order must match the file.

## `read_csv` parameters

Where meaningful, these also work as `COPY` options.

| Name | Description | Default |
| --- | --- | --- |
| `all_varchar` | Skip type detection; all columns `VARCHAR` (`read_csv` only) | `false` |
| `allow_empty` | If no files match, return an empty result (single `empty` `BOOL` column) instead of erroring; not in `COPY`. **Added in 2.0** | `false` |
| `allow_quoted_nulls` | Allow quoted values to become `NULL` | `true` |
| `auto_detect` | Auto-detect parameters | `true` |
| `auto_type_candidates` | Types considered by the sniffer (`VARCHAR` always added) | `['NULL', 'BOOLEAN', 'BIGINT', 'HUGEINT', 'BIGNUM', 'DOUBLE', 'TIME', 'DATE', 'TIMESTAMP', 'TIMESTAMPTZ', 'VARCHAR']` |
| `buffer_size` | Read buffer in bytes (must hold four lines) | `16 * max_line_size` |
| `columns` | Names and types as a struct; disables schema detection | (empty) |
| `comment` | Comment character; lines starting with it are ignored, other lines parsed up to it | (empty) |
| `compression` | `none`, `gzip`, `zstd`; from the extension by default | `auto` |
| `dateformat` (`date_format` in `COPY`) | Date format for parsing/writing | (empty) |
| `decimal_separator` | Decimal separator | `.` |
| `delim` / `sep` (`delimiter` in `COPY`) | Column separator, up to 4 bytes (e.g. 🦆) | `,` |
| `encoding` | `utf-8`, `utf-16`, `latin-1` (`COPY` always uses `utf-8`) | `utf-8` |
| `escape` | Escapes the quote character in quoted values | `"` |
| `filename` | Add a `filename` column (since 1.3.0 a virtual column exists anyway; kept for compatibility) | `false` |
| `files_to_sniff` | Files sniffed when reading many (`-1` = all) | `10` |
| `force_not_null` | Columns not matched against the NULL string | `[]` |
| `header` | First line holds column names | `false` (auto-detected) |
| `hive_partitioning` | Interpret Hive-partitioned paths | auto-detected |
| `ignore_errors` | Skip lines with parsing errors | `false` |
| `max_line_size` (`maximum_line_size`) | Max line size in bytes; not in `COPY` | `2000000` |
| `names` (`column_names`) | Column names as a list | (empty) |
| `new_line` | `'\r'`, `'\n'` or `'\r\n'` (single vs double character only) | (empty) |
| `normalize_names` | Strip non-alphanumerics; prefix reserved words with `_` | `false` |
| `null_padding` | Pad missing trailing columns with `NULL` | `false` |
| `nullstr` (`null`) | String or list of strings meaning `NULL` | (empty) |
| `parallel` | Use the parallel CSV reader | `true` |
| `quote` | Quote string | `"` |
| `rejects_scan` / `rejects_table` / `rejects_limit` / `rejects_line_size_limit` | Rejects-table settings | `reject_scans` / `reject_errors` / `0` / `10000` |
| `sample_size` | Rows sampled for detection | `20480` |
| `skip` | Lines skipped at the start of each file | `0` |
| `store_rejects` | Skip and store faulty lines | `false` |
| `strict_mode` | Error on any structural issue; `false` tries to read incorrect files (use with caution) | `true` |
| `thousands` | Thousands separator (single char, ≠ `decimal_separator`) | (empty) |
| `timestampformat` (`timestamp_format` in `COPY`) | Timestamp format | (empty) |
| `types` (`dtypes`, `column_types`) | Types by position (list) or name (struct) | (empty) |
| `union_by_name` | Align columns across files by name (more memory) | `false` |

Encodings other than UTF-8, UTF-16 and Latin-1 need the `encodings` extension or conversion, e.g. `iconv -f ISO-8859-2 -t UTF-8 input.csv > input-utf-8.csv`.

**Order preservation:** with `preserve_insertion_order = true` (the default), rows come back in file order; with `false` there is no guarantee.

## Import tips

```sql
SELECT * FROM read_csv('flights.csv', header = true);                         -- header not detected (all strings)
SELECT * FROM read_csv('flights.csv', names = ['DateOfFlight', 'CarrierName']); -- file without header
SELECT * FROM read_csv('flights.csv', types = {'FlightDate': 'DATE'});         -- override one column
SELECT * FROM read_csv('csv_file.csv', auto_type_candidates = ['BIGINT', 'DATE']);
SELECT * FROM read_csv('flights*.csv', union_by_name = true);                  -- different/missing columns → NULL
SELECT * FROM read_csv('my_csv_file.csv', sample_size = -1);                   -- wrong type detected
COPY tbl FROM 'test.csv';                                                      -- use the table schema
```

In the CLI, `.import data.csv my_table` does the same with automatic table creation (see [CLI Dot Commands](../../clients/cli/dot-commands-and-output-formats.md)); in Python use `duckdb.read_csv(...)` (see [Python Data Ingestion](../../clients/python/dataframes-and-arrow.md)).

## Writing CSV

```sql
COPY tbl TO 'output.csv' (HEADER, DELIMITER ',');
COPY (SELECT * FROM tbl) TO 'output.csv' (HEADER, DELIMITER ',');
```

CSV write options of `COPY ... TO`:

| Option | Description | Default |
| --- | --- | --- |
| `COMPRESSION` | `none`, `gzip`, `zstd`; detected from extension (`.csv.gz`, `.csv.zst`) | auto |
| `DATEFORMAT` / `TIMESTAMPFORMAT` | Formats for writing dates/timestamps | (empty) |
| `DELIM` or `SEP` | Column separator | `,` |
| `NEW_LINE` | Row separator, e.g. `E'\x1e'` | `\n` |
| `ESCAPE` | Character before a quote character | `"` |
| `QUOTE` | Quote character | `"` |
| `FORCE_QUOTE` | Columns always quoted | `[]` |
| `HEADER` | Write a header line | `true` |
| `NULLSTR` | Text for `NULL` | (empty) |
| `PREFIX` / `SUFFIX` | Strings around the file; must be used together and require `HEADER false` | (empty) |

General `COPY` options (partitioning, `OVERWRITE`, `PER_THREAD_OUTPUT`, …) are described in [COPY and EXPORT/IMPORT DATABASE](../../sql/statements/copy-and-export.md). The Python equivalent is `rel.write_csv(...)` (see [Python Relational API](../../clients/python/relational-api.md)).
