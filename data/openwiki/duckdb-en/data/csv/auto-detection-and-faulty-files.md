---
type: reference
title: CSV Auto-Detection and Reading Faulty CSV Files
description: How DuckDB's CSV sniffer detects dialect, column types, header and date formats (sample_size default 20,480 rows), how to inspect it with sniff_csv and override it (types, auto_type_candidates, all_varchar, dateformat), and how to handle broken files with detailed errors, ignore_errors and the store_rejects reject_scans / reject_errors tables.
tags: [csv, sniffer, auto-detection, sniff-csv, ignore-errors, store-rejects, data-cleaning]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-7e0dbc7f4005aa4f5ff41c02
    resource: repo://docs/2.0/data/csv/auto_detection.md
  - id: openwiki-source-cca095e3985f0fb81b26a307
    resource: repo://docs/2.0/data/csv/reading_faulty_csv_files.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# CSV Auto-Detection and Reading Faulty CSV Files

CSV files are not self-describing, so `read_csv` runs a **CSV sniffer** that detects (1) the dialect (delimiter, quote, escape), (2) the column types, and (3) whether there is a header row. Every option can be overridden individually, for example `read_csv('file.csv', delim = '|')`. The full parameter list of `read_csv` is in [Reading and Writing CSV Files](reading-and-writing-csv.md).

## Sample size

Detection runs on a sample. `sample_size` defaults to **20,480 rows**; `-1` reads the whole file:

```sql
SELECT * FROM read_csv('my_csv_file.csv', sample_size = -1);
```

On regular files DuckDB samples from different locations; on files it cannot seek in (e.g. `.gz` compressed files or `stdin`) it samples only from the beginning.

## `sniff_csv`

`sniff_csv(filename)` runs only the sniffer and returns one row of detected properties. It accepts the same named parameters as `read_csv`; any parameter you pass is treated as fixed and only the rest is detected.

```sql
FROM sniff_csv('my_file.csv');
FROM sniff_csv('my_file.csv', sample_size = 1000);
```

| Column | Description | `read_csv` parameter | Example |
| --- | --- | --- | --- |
| `Delimiter` | Delimiter | `delim` | `,` |
| `Quote` | Quote character | `quote` | `"` |
| `Escape` | Escape | `escape` | `\` |
| `NewLineDelimiter` | New-line delimiter | `new_line` | `\r\n` |
| `Comment` | Comment character | `comment` | `#` |
| `SkipRows` | Rows skipped | `skip` | `1` |
| `HasHeader` | Header present | `header` | `true` |
| `Columns` | Types as a `LIST` of `STRUCT`s | `columns` | `({'name': 'VARCHAR', 'age': 'BIGINT'})` |
| `DateFormat` | Date format | `dateformat` | `%d/%m/%Y` |
| `TimestampFormat` | Timestamp format | `timestampformat` | `%Y-%m-%dT%H:%M:%S.%f` |
| `UserArguments` | Arguments passed to `sniff_csv` | – | `sample_size = 1000` |
| `Prompt` | Ready-to-run `read_csv` call | – | `FROM read_csv('my_file.csv', auto_detect=false, delim=',', ...)` |

```sql
.mode line
SELECT Prompt FROM sniff_csv('my_file.csv');
```

## Detection steps

### Dialect

Each candidate dialect parses the sample; the winner has (1) a consistent number of columns per row and (2) the highest number of columns.

| Parameter | Considered values |
| --- | --- |
| `delim` | `,` `\|` `;` `\t` |
| `quote` | `"` `'` (empty) |
| `escape` | `"` `'` `\` (empty) |

For a file like `FlightDate|UniqueCarrier|OriginCityName|DestCityName` with values such as `New York, NY`, splitting on `|` yields 4 consistent columns while `,` gives inconsistent counts, so `|` is chosen.

### Types

Type detection runs only for `read_csv`; with `COPY` the target table's types are used. Each value is tried against candidate types; failing candidates are removed and the highest-priority survivor wins. Default candidates, in priority order:

`NULL`, `BOOLEAN`, `TIME`, `DATE`, `TIMESTAMP`, `TIMESTAMPTZ`, `BIGINT`, `HUGEINT`, `BIGNUM`, `DOUBLE`, `VARCHAR`

`VARCHAR` is the fallback with the lowest priority and is always a candidate. `auto_type_candidates` can add `TINYINT`, `SMALLINT`, `INTEGER`, `DECIMAL`, `FLOAT`. Quoted and unquoted values (`"42"` vs `42`) are treated the same.

Overrides:

- `types = ['INTEGER', 'VARCHAR', 'DATE']` — by position, or `types = {'quarter': 'INTEGER'}` — by name; any valid type is accepted (use `typeof()` or `sniff_csv`'s `Columns` to get definitions).
- `all_varchar = true` disables type detection.

### Header

The first row is a header if its types deviate from the other rows (e.g. all `VARCHAR` while a column contains `DATE`s). Without a header, columns are named `column0`, `column1`, …. If **all** columns are `VARCHAR`, the header cannot be detected and DuckDB **assumes a header**; set `header = false` to override.

### Dates and timestamps

ISO 8601 is supported by default; otherwise the sniffer tries other formats and resolves ambiguities (e.g. `01-02-2000`) from the data where possible. Otherwise preferences apply (higher wins), and you can set `dateformat` / `timestampformat` with [format specifiers](../../sql/functions/date-and-time.md).

| `dateformat` candidates | `timestampformat` candidates |
| --- | --- |
| ISO 8601 | ISO 8601 |
| `%y-%m-%d` | `%y-%m-%d %H:%M:%S` |
| `%Y-%m-%d` | `%Y-%m-%d %H:%M:%S` |
| `%d-%m-%y` | `%d-%m-%y %H:%M:%S` |
| `%d-%m-%Y` | `%d-%m-%Y %H:%M:%S` |
| `%m-%d-%y` | `%m-%d-%y %I:%M:%S %p` |
| `%m-%d-%Y` | `%m-%d-%Y %I:%M:%S %p` |
| | `%Y-%m-%d %H:%M:%S.%f` |

## Reading faulty CSV files

### Structural error types

Using `CREATE TABLE people (name VARCHAR, birth_date DATE);` as the target:

| Error | Example |
| --- | --- |
| `CAST` | `Pedro,The 90s` (not a date) |
| `MISSING COLUMNS` | `Pedro` (one value, two expected) |
| `TOO MANY COLUMNS` | `Pedro,01-01-1992,pdet` |
| `UNQUOTED VALUE` | `"pedro"holanda, 01-01-1992` with `quote='"'` |
| `LINE SIZE OVER MAXIMUM` | line longer than `max_line_size` (default **2,000,000 bytes**) |
| `INVALID ENCODING` | characters outside UTF-8, UTF-16, Latin-1, e.g. `pedro\xff\xff` |

By default the scanner **stops at the first error**. Error messages show the line number, the original line, the failing column, suggested fixes (e.g. `types={'birth_date': 'VARCHAR'}`, `sample_size=-1`, or using `COPY` with an existing table) and the sniffed options:

```console
Conversion Error:
CSV Error on Line: 5648
Original Line: Pedro,The 90s
Error when converting column "birth_date". date field value out of range: "The 90s", expected format is (DD-MM-YYYY)
```

### `ignore_errors`

```sql
FROM read_csv('faulty.csv', columns = {'name': 'VARCHAR', 'age': 'INTEGER'});                       -- cast error
FROM read_csv('faulty.csv', columns = {'name': 'VARCHAR', 'age': 'INTEGER'}, ignore_errors = true); -- skips bad row
```

With `faulty.csv` containing `Pedro,31` and `Oogie Boogie, three`, the second query returns only `Pedro | 31`. Because of projection pushdown, `SELECT name FROM read_csv(...)` returns **both** rows — the cast error on `age` never happens.

### Rejects tables: `store_rejects`

`store_rejects = true` skips faulty lines and records them in two temporary tables (one entry per error; a line with several errors appears several times):

```sql
FROM read_csv(
    'faulty.csv',
    columns = {'name': 'VARCHAR', 'age': 'INTEGER'},
    store_rejects = true
);
FROM reject_scans;
FROM reject_errors;
```

| Parameter | Description | Default |
| --- | --- | --- |
| `store_rejects` | Skip errors and store them in rejects tables | `false` |
| `rejects_scan` | Name of the scan-info temp table | `reject_scans` |
| `rejects_table` | Name of the faulty-lines temp table | `reject_errors` |
| `rejects_limit` | Max faulty records stored (`0` = no limit) | `0` |
| `rejects_line_size_limit` | Max characters of `csv_line` stored (`0` = no truncation); **new in 2.0** | `10000` |

`reject_scans` columns: `scan_id`, `file_id`, `file_path`, `delimiter`, `quote`, `escape`, `newline_delimiter`, `skip_rows`, `has_header`, `columns`, `date_format`, `timestamp_format`, `user_arguments`.

`reject_errors` columns: `scan_id`, `file_id` (join keys), `line`, `line_byte_position`, `byte_position`, `column_idx`, `column_name`, `error_type` (`ENUM`), `csv_line`, `error_message`. Example row: line `2`, column `age`, `CAST`, `Oogie Boogie, three`, `Could not convert string " three" to 'INTEGER'`.
