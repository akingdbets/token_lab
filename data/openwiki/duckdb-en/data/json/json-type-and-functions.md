---
type: reference
title: The JSON Type and JSON Functions
description: DuckDB's JSON logical type and its casting rules, extraction with json_extract / -> and json_extract_string / ->> (JSONPath and JSON Pointer, 0-based), scalar, patching, mutation (new in 2.0), aggregate and table functions (json_each, json_tree), transforming JSON to STRUCT/LIST with json_transform, creating JSON with to_json/json_object, SQL-to-JSON serialization, and equality caveats.
tags: [json, json-type, json-extract, json-functions, json-transform, json-each, to-json]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-252cf2b5256477885a86a8e8
    resource: repo://docs/2.0/data/json/caveats.md
  - id: openwiki-source-a2b3e167bfc4f99708de1e7c
    resource: repo://docs/2.0/data/json/creating_json.md
  - id: openwiki-source-6e2b33d0d652ad8808acc153
    resource: repo://docs/2.0/data/json/json_functions.md
  - id: openwiki-source-4fb441f795abb7e5206ecde0
    resource: repo://docs/2.0/data/json/json_type.md
  - id: openwiki-source-9a78d0479a54da7fa9d9beff
    resource: repo://docs/2.0/data/json/sql_to_and_from_json.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# The JSON Type and JSON Functions

The `json` extension (shipped with DuckDB and autoloaded) provides the `JSON` type and functions. Reading and writing JSON files is covered in [Loading and Writing JSON Files](loading-and-writing-json.md); the semi-structured `VARIANT` type is an alternative described in [VARIANT and GEOMETRY Types](../../sql/data-types/variant-and-geometry.md).

## The `JSON` type

`JSON` is logically a `VARCHAR` restricted to valid JSON, and is physically stored as `VARCHAR`.

```sql
SELECT '[1, null, {"key": "value"}]'::JSON;
SELECT 'unquoted'::JSON;      -- Conversion Error: Malformed JSON at byte 0 of input ...
SELECT '"quoted"'::JSON;      -- what you probably wanted
```

Because it is stored as text:

- **Whitespace is significant** and kept in round trips: `'{ "a": 5 }'::JSON = '{"a":5}'::JSON` is `false`.
- **Key order is significant**: `'{"a":1,"b":2}'::JSON = '{"b":2,"a":1}'::JSON` is `false`.
- Duplicate keys are allowed: `'{"a":1,"a":2}'::JSON`.

Any DuckDB type casts to `JSON` and back:

```sql
SELECT '{"duck": 42}'::JSON::STRUCT(duck INTEGER);   -- {'duck': 42}
SELECT {duck: 42}::JSON;                             -- {"duck":42}
SELECT '2023-05-12'::DATE::JSON;                     -- "2023-05-12"
```

The exception is `VARCHAR` → `JSON`, which does not convert but parses and validates the string.

**Equality caveat:** comparison is sometimes textual and sometimes logical. In `SELECT '[]'::JSON AS a, '[ ]'::JSON AS b, '[[]]'::JSON AS c, '[[ ]]'::JSON AS d`, all of `a != b`, `c != d`, `c[0] = d[0]`, `a = c[0]` and `b != c[0]` are true (extracting a field removes its whitespace). Use `json_normalize` before comparing documents that differ only in key order.

## Extraction: `->` and `->>`

| Function | Alias | Operator | Returns |
| --- | --- | --- | --- |
| `json_exists(json, path)` | | | `true` if the path exists |
| `json_extract(json, path)` | `json_extract_path` | `->` | `JSON` (a `LIST` of `JSON` if `path` is a list) |
| `json_extract_string(json, path)` | `json_extract_path_text` | `->>` | `VARCHAR` (list for list paths) |
| `json_value(json, path)` | | | `JSON`, or `NULL` if not a scalar |

Operators only work on values of the `JSON` type. Paths use **JSONPath** (`$.field`, `$.arr[0]`, `$.arr[*]`) or **JSON Pointer** (`/field/0`); bare keys and integer indexes also work. JSON indexing is **0-based**.

```sql
CREATE TABLE example (j JSON);
INSERT INTO example VALUES
    ('{ "family": "anatidae", "species": [ "duck", "goose", "swan", null ] }');

SELECT j->'$.family' FROM example;            -- "anatidae"
SELECT j->>'$.family' FROM example;           -- anatidae
SELECT j->'$.species[0]' FROM example;        -- "duck"
SELECT j->>'$.species[*]' FROM example;       -- [duck, goose, swan, NULL]
SELECT j->'species'->>0 FROM example;         -- duck
SELECT j->'species'->>['/0', '/1'] FROM example;   -- [duck, goose]
```

`->` has low precedence because it is also used by lambdas, so wrap it in arithmetic/comparisons: `SELECT ((JSON '{"field": 42}')->'field') = 42;`. **Unlike DuckDB 1.x**, arrow operators bind more tightly than `AND`/`OR`, so `WHERE 1 = 1 AND j->>'field' IS NOT NULL` works without parentheses.

Extract several paths at once to parse the JSON only once:

```sql
WITH extracted AS (
    SELECT json_extract(j, ['family', 'species']) AS extracted_list
    FROM example
)
SELECT extracted_list[1] AS family, extracted_list[2] AS species
FROM extracted;
```

Wildcard results are lists, so [lambda functions](../../sql/functions/list-array-and-lambda.md) apply:

```sql
SELECT list_transform(j->>'$.species[*]', lambda s: upper(s)) AS names FROM example;
```

## Scalar functions

All except `json_valid` error on invalid JSON.

| Function | Description |
| --- | --- |
| `json_array_length(json[, path])` | Array length, `0` if not an array |
| `json_contains(json_haystack, json_needle)` | Whether needle is contained (strings must be double-quoted) |
| `json_keys(json[, path])` | Object keys as `VARCHAR[]` |
| `json_pretty(json)` | Indented output |
| `json_structure(json)` | Structure (`JSON` where inconsistent); dates, times, timestamps and UUIDs appear as `VARCHAR` |
| `json_type(json[, path])` | `ARRAY`, `BIGINT`, `BOOLEAN`, `DOUBLE`, `OBJECT`, `UBIGINT`, `VARCHAR` or `NULL` |
| `json_valid(json)` | Whether the input is valid JSON |
| `json(json)` | Parse and minify |

### Patching and normalization

| Function | Description |
| --- | --- |
| `json_merge_patch(json, json)` | RFC 7396 merge patch (`null` deletes a key) |
| `json_deep_merge(json, patch[, ...])` | Recursive merge where a JSON `null` keeps the original value |
| `json_merge_patch_diff(json_orig, json_modified)` | Minimal merge patch from one document to the other |
| `json_normalize(json)` | Sort object keys recursively (array order kept) |
| `json_strip_nulls(json)` | Remove `null`-valued keys recursively |

### Mutation (new in DuckDB 2.0)

`value` is JSON text, e.g. `'2'` or `'"duck"'`.

```sql
SELECT json_set('{"a": 1}', '$.b', '2');            -- {"a":1,"b":2}  (insert or overwrite)
SELECT json_insert('{"a": 1}', '$.a', '9');         -- {"a":1}        (only if missing)
SELECT json_replace('{"a": 1}', '$.b', '2');        -- {"a":1}        (only if present)
SELECT json_remove('{"a": 1, "b": 2}', '$.b');
```

## Creating JSON

| Function | Description |
| --- | --- |
| `to_json(any)` (alias `json_quote`) | Any value; `LIST` → array, `STRUCT`/`MAP` → object |
| `array_to_json(list)` / `row_to_json(struct)` | Restricted aliases of `to_json` |
| `json_array(any, ...)` | Array from arguments |
| `json_object(key, value, ...)` | Object from an even number of arguments |

```sql
SELECT to_json([1, 2, 3]);                          -- [1,2,3]
SELECT to_json(MAP(['duck'], [42]));                -- {"duck":42}
SELECT json_object('duck', 42, 'goose', 123);       -- {"duck":42,"goose":123}
SELECT json_merge_patch('{"duck": 42}', '{"goose": 123}');
```

### Aggregates

`json_group_array(any)`, `json_group_object(key, value)` and `json_group_structure(json)`:

```sql
SELECT json_group_array(v) FROM example1;           -- [42, 7]
```

## Transforming JSON to nested types

Extracting values one by one is inefficient; `json_transform(json, structure)` (alias `from_json`) converts the whole document to `STRUCT`/`LIST` using a structure in the form returned by `json_structure`. Missing keys become `NULL`; failed casts give `NULL`, while `json_transform_strict` (alias `from_json_strict`) raises an error.

```sql
SELECT json_transform(j, '{"family": "VARCHAR", "coolness": "DOUBLE"}') FROM example;
-- {'family': anatidae, 'coolness': 42.420000}
SELECT json_transform_strict(j, '{"family": "TINYINT", "coolness": "DOUBLE"}') FROM example;
-- Invalid Input Error: Failed to cast value: "anatidae"
```

## Table functions: `json_each` and `json_tree`

`json_each(json[, path])` returns one row per top-level element; `json_tree(json[, path])` traverses depth-first. Columns: `key`, `value`, `type`, `atom`, `id`, `parent`, `fullkey`, `path`, plus virtual `json`, `root`, `rowid`. They behave like SQLite's functions and act as lateral joins:

```sql
SELECT je.*, je.rowid
FROM example AS e, json_each(e.j) AS je;
```

## SQL to and from JSON

| Function | Description |
| --- | --- |
| `json_serialize_sql(varchar, skip_default, skip_empty, skip_null, format)` | Serialize `;`-separated `SELECT` statements to JSON |
| `json_deserialize_sql(json)` | Back to SQL text |
| `json_execute_serialized_sql(varchar)` | Table function executing one serialized statement (cannot see transaction-local changes; use the `PRAGMA` form for that) |
| `json_serialize_plan(varchar, skip_default, format, optimize)` | Serialize the bound (optionally optimized) logical plan |

```sql
SELECT json_deserialize_sql(json_serialize_sql('FROM x SELECT 1 + 2'));   -- SELECT (1 + 2) FROM x
SELECT * FROM json_execute_serialized_sql(json_serialize_sql('SELECT 1 + 2'));
```

Round trips are semantically equivalent but drop syntactic sugar. Invalid SQL yields `{"error":true,"error_type":"parser",...}`.
