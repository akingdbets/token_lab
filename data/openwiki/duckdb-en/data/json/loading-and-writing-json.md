---
type: reference
title: Loading and Writing JSON Files
description: Read JSON files with read_json / read_ndjson (auto-detected format and schema) or as raw objects with read_json_objects, the format (auto, newline_delimited, array, unstructured) and records settings, all reader parameters with defaults, COPY ... FROM/TO with FORMAT json and ARRAY, and GeoJSON reading/writing (new in 2.0).
tags: [json, read-json, ndjson, copy, json-export, geojson, format, records]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-93281abb5e0872114124c6ea
    resource: repo://docs/2.0/data/json/format_settings.md
  - id: openwiki-source-4756d35f2465778c435dcefe
    resource: repo://docs/2.0/data/json/installing_and_loading.md
  - id: openwiki-source-84a6bc8b16f3f989aa7a8ecb
    resource: repo://docs/2.0/data/json/loading_json.md
  - id: openwiki-source-3a88b4a2ba346f717d391822
    resource: repo://docs/2.0/data/json/overview.md
  - id: openwiki-source-8d32c245d7da1e6c4f49db1e
    resource: repo://docs/2.0/data/json/writing_json.md
  - id: openwiki-source-ddeae737ec0a10e86706b86e
    resource: repo://docs/2.0/guides/file_formats/json_export.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Loading and Writing JSON Files

JSON support comes from the `json` extension, which ships with most DuckDB builds and is **autoloaded** on first use. To install/load manually:

```sql
INSTALL json;
LOAD json;
```

The `JSON` type and the functions that operate on JSON values are covered in [The JSON Type and JSON Functions](json-type-and-functions.md).

## Quick examples

```sql
SELECT * FROM 'todos.json';                     -- auto-infer everything

SELECT *
FROM read_json('todos.json',
    format = 'array',
    columns = {userId: 'UBIGINT', id: 'UBIGINT', title: 'VARCHAR', completed: 'BOOLEAN'});

CREATE TABLE todos AS SELECT * FROM 'todos.json';
CREATE TABLE todos (userId UBIGINT, id UBIGINT, title VARCHAR, completed BOOLEAN);
COPY todos FROM 'todos.json' (AUTO_DETECT true);
INSERT INTO tbl SELECT * FROM read_json('input.json');

SELECT filename, * FROM 'todos-*.json';         -- filename virtual column (since 1.3.0)
```

```batch
cat data/json/todos.json | duckdb -c "SELECT * FROM read_json('/dev/stdin')"
```

## Reading JSON as a table: `read_json`

`read_json` auto-detects the format, key names and types. Aliases: `read_json_auto` (same), `read_ndjson` and `read_ndjson_auto` (with `format = 'newline_delimited'`). Globs and lists read multiple files (see [Multiple Files and Partitioning](../multiple-files-and-partitioning.md)).

```sql
SELECT * FROM read_json('todos.json') LIMIT 5;
-- columns: userId BIGINT, id BIGINT, title VARCHAR, completed BOOLEAN
```

If `columns` lists only some keys, the other keys are **excluded**:

```sql
SELECT * FROM read_json('todos.json', columns = {userId: 'UBIGINT', completed: 'BOOLEAN'});
```

JSON arrays map to `LIST`s and missing keys become `NULL`:

```sql
SELECT * FROM read_json('example.json', columns = {duck: 'INTEGER', goose: 'INTEGER[]', swan: 'DOUBLE'});
SELECT goose, duck FROM '*.json.gz';
```

### Parameters

| Name | Description | Default |
| --- | --- | --- |
| `allow_empty` | No matching files → empty result (single `empty` column). **Added in 2.0** | `false` |
| `array` | Shorthand: `true` = `format = 'array'`, `false` = `'newline_delimited'`; must be quoted (`"array" = true`). **Added in 2.0** | – |
| `auto_detect` | Detect key names and types | `true` |
| `columns` | Struct of key names → types | (empty) |
| `compression` | `none`, `gzip`, `zstd`, `auto_detect` (from extension, e.g. `t.json.gz`) | `auto_detect` |
| `dateformat` | Date parsing format | `iso` |
| `timestampformat` | Timestamp format; `iso` infers ISO 8601 with offsets and fractional seconds | `iso` |
| `format` | `auto`, `unstructured`, `newline_delimited`, `array` | `auto` |
| `records` | `auto`, `true`, `false` | `auto` |
| `ignore_errors` | Ignore parse errors (only with `newline_delimited`) | `false` |
| `maximum_object_size` | Max object size in bytes | `16777216` |
| `maximum_depth` | Nesting depth for type detection (`-1` = full) | `-1` |
| `sample_size` | Objects sampled for detection (`-1` = whole file) | `20480` |
| `maximum_sample_files` | Files sampled for detection | `32` |
| `map_inference_threshold` | Infer `MAP` instead of `STRUCT` above this many subfields (`-1` disables) | `200` |
| `field_appearance_threshold` | Use `MAP` if average field appearance ratio is below this | `0.1` |
| `union_by_name` | Unify schemas across files by name | `false` |
| `hive_partitioning` | Interpret Hive-partitioned paths | auto-detected |
| `filename` | Add `filename` column (kept for compatibility; virtual column exists since 1.3.0) | `false` |
| `geojson` | Parse GeoJSON geometries as `GEOMETRY` | `false` |

### `format`

The reader detects the format with `format = 'auto'`; all three of these files read as the same `key1 | key2` table:

| Format | File shape | Example |
| --- | --- | --- |
| `newline_delimited` | One JSON value per line (NDJSON) | `read_json('records.json', format = 'newline_delimited')` |
| `array` | A top-level array of objects (pretty-printed or not) | `read_json('records-in-array.json', format = 'array')` |
| `unstructured` | Concatenated JSON values, not newline-delimited | `read_json('unstructured.json', format = 'unstructured')` |

### `records`

`records = true` expects objects and unpacks their fields into columns. `records = false` keeps each top-level value as one column named `json` (a `STRUCT` for objects), which also lets you read non-object JSON such as `[1, 2, 3]` lines:

```sql
SELECT * FROM read_json('records.json', records = false);   -- json: {'key1': value1, 'key2': value1}
SELECT * FROM read_json('arrays.json', records = false);    -- json: [1, 2, 3]
```

## Reading raw JSON objects

`read_json_objects(filename)` returns each JSON value as a `JSON` column without schema detection; `read_ndjson_objects` (format `newline_delimited`) and `read_json_objects_auto` (format `auto`) are aliases. They take `allow_empty`, `compression`, `filename`, `format`, `hive_partitioning`, `ignore_errors`, `maximum_sample_files` and `maximum_object_size`.

```sql
FROM read_json_objects('birds.json', format = 'unstructured');
FROM read_json_objects('birds-array.json', format = 'array');
```

## JSONPath, JSON Pointer and indexing

Extraction supports JSONPath lookups (`.key`, `[index]`, indexing from the back, wildcard `*`) and JSON Pointer; full JSONPath is not supported since SQL handles further transformation. Pick one syntax per application. Keys with `[` or `.` need double quotes: `'$."d[u]._\"ck"'`. **JSON uses 0-based indexing**, unlike DuckDB `LIST`/`ARRAY` (1-based, following PostgreSQL).

## Writing JSON with `COPY`

`COPY ... TO` writes **newline-delimited JSON by default**; `ARRAY` (or `ARRAY true`) writes a single JSON array. With the `json` extension, `FORMAT json` also works for `COPY FROM`, `IMPORT DATABASE` and `EXPORT DATABASE`.

```sql
CREATE TABLE cities AS FROM (VALUES ('Amsterdam', 1), ('London', 2)) cities(name, id);
COPY cities TO 'cities.json';
COPY (SELECT * FROM range(3) tbl(n)) TO 'output.json' (ARRAY);
COPY (SELECT * FROM range(5) r(i)) TO 'numbers.json' (ARRAY true);

CREATE TABLE numbers (i BIGINT);
COPY numbers FROM 'numbers.json' (ARRAY true);
COPY numbers FROM 'numbers.json' (AUTO_DETECT true);
```

See [COPY and EXPORT/IMPORT DATABASE](../../sql/statements/copy-and-export.md) for general options.

## GeoJSON (new in DuckDB 2.0)

Reading: pass `geojson := true` so geometry objects become `GEOMETRY` (the spatial type) instead of JSON. `.geojson` / `.geojsonl` files are also recognized directly.

```sql
SELECT * FROM read_json('features.geojson', geojson := true);
```

Writing: `FORMAT GEOJSON` writes a `FeatureCollection`; `FORMAT GEOJSONL` (or `ARRAY true` with `GEOJSON`) writes newline-delimited `Feature` objects. Optional `ID_COLUMN` and `GEOMETRY_COLUMN` select the feature id and geometry columns.

```sql
COPY (SELECT 'POINT(0 1)'::GEOMETRY AS geom, 10 AS my_field)
    TO 'test.json' (FORMAT GEOJSON);
COPY (SELECT 'POINT(0 1)'::GEOMETRY AS geom, 10 AS my_field)
    TO 'test.jsonl' (FORMAT GEOJSONL);
```

`st_asgeojson` / `st_geomfromgeojson` convert single values (see [VARIANT and GEOMETRY Types](../../sql/data-types/variant-and-geometry.md)).
