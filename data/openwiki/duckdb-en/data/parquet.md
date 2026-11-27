---
type: reference
title: "Parquet Files: Reading, Writing, Metadata and Encryption"
description: Read Parquet with read_parquet (parameters such as union_by_name, schema, bound_schema, utf8_validation, int96_as), projection/filter pushdown and the page index (new in 2.0), write Parquet with COPY (compression, ROW_GROUP_SIZE, KV_METADATA, PARQUET_VERSION, DATA_PAGE_SIZE_LIMIT), inspect metadata with parquet_metadata and friends, encrypt files, and tune row groups.
tags: [parquet, read-parquet, copy, compression, row-group, metadata, encryption, pushdown]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-40002b46f7fb0f7acc7d3992
    resource: repo://docs/2.0/data/parquet/encryption.md
  - id: openwiki-source-8802eb41ef105194ce86737c
    resource: repo://docs/2.0/data/parquet/metadata.md
  - id: openwiki-source-35b11b5b698742211dd010f3
    resource: repo://docs/2.0/data/parquet/overview.md
  - id: openwiki-source-753b88a3c28169243818c910
    resource: repo://docs/2.0/data/parquet/tips.md
  - id: openwiki-source-ea1b8a7c9ee80096fe0e7092
    resource: repo://docs/2.0/sql/statements/copy.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Parquet Files: Reading, Writing, Metadata and Encryption

Parquet files are compressed columnar files that DuckDB reads and writes efficiently, pushing filters and projections into the scan. Support comes from the `parquet` extension, bundled with almost all clients (otherwise `INSTALL parquet;`). Multi-file reads, globbing and Hive partitioning are covered in [Multiple Files, Globbing and Hive Partitioning](multiple-files-and-partitioning.md); performance considerations in [File Formats, Bulk Import, Huge Databases](../performance/file-formats-and-large-data.md).

## Reading

```sql
SELECT * FROM 'test.parquet';
DESCRIBE SELECT * FROM 'test.parquet';                 -- columns and types
CREATE TABLE test AS SELECT * FROM 'test.parquet';
SELECT * FROM read_parquet('test.parq');               -- needed if the extension is not .parquet
SELECT * FROM read_parquet(['file1.parquet', 'file2.parquet', 'file3.parquet']);
SELECT * FROM read_parquet('test');                    -- directory: recursive *.parquet
SELECT *, filename FROM read_parquet('test/*.parquet');
SELECT * FROM read_parquet('https://some.url/some_file.parquet');
CREATE VIEW people AS SELECT * FROM read_parquet('test.parquet');   -- keep data in the file
COPY tbl FROM 'input.parquet' (FORMAT parquet);
```

`parquet_scan` is an alias of `read_parquet`.

### `read_parquet` parameters

| Name | Description | Default |
| --- | --- | --- |
| `allow_empty` | No matching files → empty result (`empty` `BOOL` column). **Added in 2.0** | `false` |
| `binary_as_string` | Load binary columns as strings (legacy writers without the `UTF8` flag) | `false` |
| `bound_schema` | Complete ordered output schema as a struct; columns matched by name and cast; unlisted columns not returned | – |
| `can_have_nan` | Account for `NaN` in min/max statistics for float pushdown | `false` |
| `encryption_config` | Parquet encryption config | – |
| `filename` | Extra `filename` column (virtual column exists since 1.3.0) | `false` |
| `file_row_number` | Include `file_row_number` | `false` |
| `hive_partitioning` | Interpret Hive-partitioned paths | auto-detected |
| `int96_as` | Read legacy `INT96` timestamps (Impala/old Spark) as `timestamp` (µs), `timestamp_ns` or `struct`. **Added in 2.0** | `timestamp` |
| `prefetch_strategy` | `auto` (choose at runtime) or `whole_group`. **Added in 2.0** | `auto` |
| `union_by_name` | Unify schemas of multiple files by name | `false` |
| `schema` | `MAP` keyed by field-id or column name giving `name`, `type`, `default_value`; cannot combine with `union_by_name` | `NULL` |
| `utf8_validation` | Invalid UTF-8: `strict` (error), `replace` (`?`), `ignore` (remove). **Added in 2.0** | `strict` |

```sql
COPY (SELECT 42::INTEGER AS i) TO 'integers.parquet' (FIELD_IDS {i: 0});
SELECT *
FROM read_parquet('integers.parquet', schema = MAP {
    0: {name: 'renamed_i', type: 'BIGINT', default_value: NULL},
    1: {name: 'new_column', type: 'UTINYINT', default_value: 43}
});
```

To read into a wider schema without `schema`, union with an empty typed row: `FROM (VALUES (NULL::VARCHAR, NULL, NULL::INTEGER)) t(c1, c2, c3) WHERE false UNION ALL BY NAME FROM 'f.parquet';`.

### Virtual columns

`file_row_number` gives the file-relative row index. **New in 2.0:** `file_row_group_number` gives the file-relative row group (starting at 0 per file):

```sql
SELECT file_row_group_number, count(*)
FROM read_parquet('test.parquet')
GROUP BY file_row_group_number
ORDER BY file_row_group_number;
```

### Partial reading (pushdown)

- **Projection pushdown:** only columns needed by the query are read.
- **Filter pushdown:** filters go into the scan and can skip row groups using zonemaps (min/max statistics), if the file contains them.
- **Page index (new in 2.0):** DuckDB reads and writes the Parquet page index (`ColumnIndex`/`OffsetIndex`), so filters can skip data pages — important for Spark/parquet-mr files without page-header statistics; written files let other engines prune too.

## Writing

```sql
COPY (SELECT * FROM tbl) TO 'result-snappy.parquet' (FORMAT parquet);   -- default: Snappy
COPY tbl TO 'result-zstd.parquet' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 1);
COPY (FROM generate_series(100_000)) TO 'test.parquet' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 100_000);
COPY tbl TO 'result-v2.parquet' (FORMAT parquet, PARQUET_VERSION 'V2');
COPY 'test.csv' TO 'result-uncompressed.parquet' (FORMAT parquet, COMPRESSION uncompressed);
COPY (SELECT 42 AS number, true AS is_even) TO 'kv_metadata.parquet' (
    FORMAT parquet,
    KV_METADATA {number: 'Answer to life, universe, and everything', is_even: 'not ''odd'''}
);
EXPORT DATABASE 'target_directory' (FORMAT parquet);
```

| Option | Default / notes |
| --- | --- |
| `COMPRESSION` | `snappy`; also `uncompressed`, `gzip`, `zstd`, `brotli`, `lz4`, `lz4_raw` (`lz4` ≡ `lz4_raw`) |
| `COMPRESSION_LEVEL` | `3`; 1 (fastest) – 22 (smallest); zstd only |
| `ROW_GROUP_SIZE` | `122880` rows (minimum = vector size 2,048) |
| `ROW_GROUP_SIZE_BYTES` | e.g. `2MB`; only used with `SET preserve_insertion_order = false;` |
| `ROW_GROUPS_PER_FILE` | Start a new file after N row groups (may slightly exceed with multiple threads, exact with `PER_THREAD_OUTPUT`) |
| `FIELD_IDS` | Struct of field ids, or `auto` |
| `KV_METADATA` | Custom key-value metadata (escape single quotes) |
| `PARQUET_VERSION` | e.g. `'V2'` |
| `STRING_DICTIONARY_PAGE_SIZE_LIMIT` | Dictionary page size, default 1 GiB |
| `DATA_PAGE_SIZE_LIMIT` | **New in 2.0**: split data pages below the default 100 MiB cap (best effort) |
| `PER_THREAD_OUTPUT` | One file per thread — significantly faster when file count does not matter |

Other `COPY` options (partitioning, `FILE_SIZE_BYTES`, `OVERWRITE`) are on [COPY and EXPORT/IMPORT DATABASE](../sql/statements/copy-and-export.md). Python: `rel.write_parquet(...)`.

### Row group tips

- Compression applies per row group, so larger row groups compress better but hold more memory per thread when streaming.
- Row groups are read in parallel and pruned by statistics; aim for **at least as many row groups per file as CPU threads**. More helps selective queries but slows full scans.
- **Sort on frequently filtered columns** before writing so min/max ranges are tight and non-overlapping:

```sql
COPY (FROM 'events.parquet' ORDER BY event_time) TO 'events-sorted.parquet' (FORMAT parquet);
```

## Metadata functions

```sql
SELECT * FROM parquet_metadata('test.parquet');          -- per row group / column chunk: stats_min, stats_max, compression, ...
SELECT * FROM parquet_schema('test.parquet');            -- internal schema: name, type, repetition_type, field_id, logical_type, ...
SELECT * FROM parquet_file_metadata('test.parquet');     -- created_by, num_rows, num_row_groups, format_version, encryption_algorithm, ...
SELECT * FROM parquet_kv_metadata('test.parquet');       -- key/value as BLOBs (decode() them; GeoParquet uses key 'geo')
SELECT * FROM parquet_full_metadata('test.parquet');     -- all of the above in one row
FROM parquet_bloom_probe('my_file.parquet', 'my_col', 500);   -- row groups excludable via Bloom filters
```

`parquet_metadata` columns include `file_name`, `row_group_id`, `row_group_num_rows`, `column_id`, `path_in_schema`, `type`, `stats_min`, `stats_max`, `stats_null_count`, `stats_distinct_count`, `compression`, `encodings`, `total_compressed_size`, `total_uncompressed_size`, `bloom_filter_offset`, `min_is_exact`, `max_is_exact`. For names and types, `DESCRIBE` is simpler than `parquet_schema`.

## Encryption

Since 0.10.0 DuckDB reads and writes encrypted Parquet following the Parquet Modular Encryption spec. Add named 128/192/256-bit keys (held in memory) and reference them:

```sql
PRAGMA add_parquet_key('key256', '01234567891123450123456789112345');
PRAGMA add_parquet_key('key256base64', 'MDEyMzQ1Njc4OTExMjM0NTAxMjM0NTY3ODkxMTIzNDU=');
COPY tbl TO 'tbl.parquet' (ENCRYPTION_CONFIG {footer_key: 'key256'});
SELECT * FROM read_parquet('tbl.parquet', encryption_config = {footer_key: 'key256'});
```

- DuckDB encrypts the footer and all columns with `footer_key`; per-column `column_keys` raise `Not implemented Error: Parquet encryption_config column_keys not yet implemented`.
- It can read uniformly encrypted files written by Arrow C++ (e.g. PyArrow) when one key covers footer and columns.
- Cost: reading/writing TPC-H SF1 `lineitem` (6M rows, 15 columns) went from 0.26 s / 0.99 s to 0.64 s / 2.21 s — about **2.5× slower**.
