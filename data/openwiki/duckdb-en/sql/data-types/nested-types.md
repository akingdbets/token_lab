---
type: reference
title: "Nested Types: LIST, ARRAY, STRUCT, MAP, UNION and ENUM"
description: How to create, query, compare and cast DuckDB's composite types — variable-length LIST and fixed-length ARRAY (1-based indexing and slicing), STRUCT (dot/bracket access, unnest, empty structs and TUPLE new in 2.0, schema evolution), MAP, tagged UNION, and ENUM with its ordering and comparison pitfalls.
tags: [data-types, list, array, struct, map, union, enum, tuple, nested-types]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-4406a8b7c49200ddba4eeec5
    resource: repo://docs/2.0/sql/data_types/array.md
  - id: openwiki-source-ed473b897b3bf992d4ece91e
    resource: repo://docs/2.0/sql/data_types/enum.md
  - id: openwiki-source-a54d82270741a71a1ff74534
    resource: repo://docs/2.0/sql/data_types/list.md
  - id: openwiki-source-3f48f9e72751161c9daf3ee3
    resource: repo://docs/2.0/sql/data_types/map.md
  - id: openwiki-source-42614473de3667a6540c44e7
    resource: repo://docs/2.0/sql/data_types/struct.md
  - id: openwiki-source-ef2762614fd6c31a316127bb
    resource: repo://docs/2.0/sql/data_types/union.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Nested Types: LIST, ARRAY, STRUCT, MAP, UNION and ENUM

| Type | Shape | Keys / members |
| --- | --- | --- |
| `LIST` (`INTEGER[]`) | Variable-length, same element type | – |
| `ARRAY` (`INTEGER[3]`) | Fixed-length, same element type | – |
| `STRUCT` | Same named entries in every row; each entry its own type | String keys, fixed per column |
| `TUPLE` | Unnamed entries, accessed by position (new in 2.0) | – |
| `MAP` | Key/value pairs; keys may vary per row | One key type, one value type |
| `UNION` | One of several tagged alternatives | Up to 255 members |
| `ENUM` | Dictionary of allowed string values | – |

Functions for these types are on [List, Array and Lambda Functions](../functions/list-array-and-lambda.md) and [Struct, Map, Union, Enum and Nested Functions](../functions/struct-map-and-union.md).

## `LIST`

Similar to PostgreSQL's `ARRAY` (some `array_` aliases exist for compatibility); elements may be any uniform type, including lists and structs.

```sql
SELECT [1, 2, 3];
SELECT ['duck', 'goose', NULL, 'heron'];
SELECT [['duck', 'goose', 'heron'], NULL, ['frog', 'toad'], []];
SELECT list_value(1, 2, 3);
CREATE TABLE list_table (int_list INTEGER[], varchar_list VARCHAR[]);
```

Indexing is **1-based**; negative indexes count from the end; slices are inclusive:

| Example | Result |
| --- | --- |
| `['a', 'b', 'c'][3]` | `'c'` |
| `['a', 'b', 'c'][-1]` | `'c'` |
| `list_extract(['a', 'b', 'c'], 3)` | `'c'` |
| `['a', 'b', 'c'][1:2]` | `['a', 'b']` |
| `['a', 'b', 'c'][:2]` | `['a', 'b']` |
| `['a', 'b', 'c'][-2:]` | `['b', 'c']` |
| `list_slice(['a', 'b', 'c'], 2, 3)` | `['b', 'c']` |

Use the `list` aggregate to build lists from a column. **Ordering** is positional: lists are equal if same length and elements; otherwise the first differing element decides, and if all compared elements are equal the longer list sorts last. Top-level `NULL` comparisons yield `NULL`; nested `NULL`s are greater than other values. So `[1, 2] < [1, 3]`, `[] < [1]` and `[1, 2] < [1, NULL, 4]` are true; `[1, 2] < [1]` is false; `NULL = [1]` is `NULL`.

## `ARRAY` (fixed length)

DuckDB arrays are fixed-length (unlike PostgreSQL's), useful e.g. for embeddings.

```sql
SELECT array_value(1, 2, 3);
SELECT array_value(1, 2, 3)[2];                  -- arrays implicitly cast to lists
SELECT [3, 2, 1]::INTEGER[3];                    -- dimensions must match
CREATE TABLE array_table (id INTEGER, arr INTEGER[3]);
INSERT INTO array_table VALUES (10, [1, 2, 3]), (20, [4, 5, 6]);
SELECT id, arr[1], list_extract(arr, 1), array_extract(arr, 1) FROM array_table;
SELECT id, arr[1:2] AS elements FROM array_table;   -- slicing returns a LIST
SELECT array_cosine_similarity(x.v, y.v) FROM x, y WHERE x.i = y.i;   -- FLOAT[3] columns
```

All list functions work on arrays, plus array-native functions such as `array_cross_product`. Ordering is lexicographic; `NULL`s compare greater than all values and equal to each other.

## `STRUCT`

A struct column has the same named entries in every row (unlike PostgreSQL's `ROW`), which lets DuckDB vectorize fully.

```sql
SELECT struct_pack(key1 := 'value1', key2 := 42) AS s;     -- no quotes around keys, :=
SELECT {'key1': 'value1', 'key2': 42} AS s;
SELECT d AS s FROM (SELECT 'value1' AS key1, 42 AS key2) d; -- row variable
SELECT struct_update({'a': 1, 'b': 2}, b := 3, c := 4) AS s; -- add or update fields
SELECT struct_pack() AS s;                                  -- {} — empty structs new in 2.0
```

`struct_insert` adds fields but cannot update existing ones. **New in 2.0:** `STRUCT` may be empty (`NULL::STRUCT`, `CREATE TABLE t (s STRUCT)`).

**Access:**

```sql
SELECT a.x FROM (SELECT {'x': 1, 'y': 2, 'z': 3} AS a);
SELECT a."x space", a['x space'] FROM (SELECT {'x space': 1, 'y': 2} AS a);   -- brackets: constant only
SELECT struct_extract({'x space': 1, 'y': 2, 'z': 3}, 'x space');
SELECT unnest(a) FROM (SELECT {'x': 1, 'y': 2, 'z': 3} AS a);                -- one column per key
SELECT a.* EXCLUDE ('y') FROM (SELECT {'x': 1, 'y': 2, 'z': 3} AS a);        -- top-level, non-aggregate only
```

**Dot resolution** prefers columns: `part1.part2` is table.column, else column.field; `part1.part2.part3` tries schema.table.column, then table.column.field, then column.field.field; further parts are always fields.

**Casting** between structs requires at least one matching field name (`Binder Error: STRUCT to STRUCT cast must have at least one matching member`); use `struct_pack(y := a.x)` instead. **Comparison** is lexicographic over entries with `IS NOT DISTINCT FROM` semantics (two `NULL`s equal; a `NULL` entry sorts after values). Structs with different keys are cast to the union of keys first, e.g. `{'k1': 0} < {'k2': 0}` is true.

**Schema evolution (since 1.3.0):**

```sql
CREATE TABLE test (s STRUCT(i INTEGER, j INTEGER));
ALTER TABLE test ADD COLUMN s.k INTEGER;
ALTER TABLE test DROP COLUMN s.i;
ALTER TABLE test RENAME s.j TO v1;
```

### `TUPLE` (new in DuckDB 2.0)

A tuple is a struct without entry names (earlier versions used structs with empty keys). Create with `row(...)` or parentheses for two or more values; `row(x)` or `(x,)` for one. Access by 1-based position with `t[1]`, `struct_extract` or `struct_extract_at` (no dot notation).

```sql
SELECT (x, x + 1, y) AS t FROM (SELECT 1 AS x, 'a' AS y);
SELECT typeof((1, 'a')) AS type;                                      -- TUPLE(INTEGER, VARCHAR)
SELECT t[1] AS first, struct_extract_at(t, 2) AS second FROM (SELECT (42, 'duck') AS t);
SELECT (1, 'a')::STRUCT(id INTEGER, name VARCHAR), {'id': 1, 'name': 'a'}::TUPLE(INTEGER, VARCHAR);
INSERT INTO t1 VALUES (row('a', 42));                                 -- into STRUCT(v VARCHAR, i INTEGER)
```

Casts between tuples and structs match by position and need the same number of entries. In formats without tuples (e.g. Parquet) they are written as structs with keys `element1`, `element2`, ….

## `MAP`

Ordered key/value pairs where keys may differ per row. All keys share one type and all values share one type (they may differ from each other); no duplicate keys.

```sql
SELECT MAP {'key1': 10, 'key2': 20, 'key3': 30};
SELECT map_from_entries([('key1', 10), ('key2', 20), ('key3', 30)]);
SELECT MAP(['key1', 'key2', 'key3'], [10, 20, 30]);
SELECT MAP {1: 42.001, 5: -32.1};
SELECT MAP {['a', 'b']: [1.1, 2.2], ['c', 'd']: [3.3, 4.4]};
CREATE TABLE tbl (col MAP(INTEGER, DOUBLE));
SELECT MAP {'key1': 5, 'key2': 43}['key1'];          -- 5 (map_extract_value); missing key → NULL
SELECT map_extract(MAP {'key1': 5, 'key2': 43}, 'key3');   -- [] (also element_at)
```

A key of the wrong type raises an error. Comparison is dictionary-like; nested `NULL` members compare greater than non-`NULL`s.

## `UNION`

A tagged union (like C's `union`, but with a tag): at least one and at most **255** members, unique tag names, implemented as a `STRUCT` with the tag first.

```sql
CREATE TABLE tbl1 (u UNION(num INTEGER, str VARCHAR));
INSERT INTO tbl1 VALUES (1), ('two'), (union_value(str := 'three'));
SELECT u, union_extract(u, 'str') AS str, u.str, union_tag(u) AS t FROM tbl1;
```

- Any type implicitly casts to a `UNION` containing a compatible member, chosen by implicit-cast priority (a `FLOAT` → `UNION(i INTEGER, v VARCHAR)` picks `INTEGER`); equal-priority candidates are ambiguous — use `union_value(num := 2::INTEGER)`.
- A `UNION` does **not** implicitly cast to a member type (use `union_extract`), except to `VARCHAR`.
- `UNION` → `UNION` casts work if the source tags are a subset of the target's and the matching types are implicitly castable.

## `ENUM`

A dictionary of all allowed values, ideal for low-cardinality string columns.

```sql
CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy');          -- values must be unique and non-NULL
CREATE TYPE my_schema.mood AS ENUM ('sad', 'ok', 'happy');
SELECT 'clubs'::ENUM ('spades', 'hearts', 'diamonds', 'clubs');   -- anonymous enum
CREATE TYPE region AS ENUM (SELECT region FROM 'sales_data.csv');  -- deduplicated, NULLs ignored
CREATE TABLE person (name TEXT, current_mood mood);
SELECT enum_range(NULL::mood) AS my_enum_range;            -- [sad, ok, happy]
DROP TYPE mood;
```

- Values are **case-sensitive**; inserting an unknown value (`'quackity-quack'`) fails. Columns may still hold SQL `NULL`.
- Enums cast to `VARCHAR` automatically, so they work with string functions. Comparing two different enum types, or an enum with `VARCHAR`, compares **strings**. Against a constant string DuckDB uses `try_cast` internally, so a bogus constant silently matches nothing (`WHERE current_mood = 'bogus'` → no rows); cast explicitly (`'bogus'::mood`) for type safety.
- **Ordering** follows definition order: `'low'::priority < 'high'::priority` is true. But `WHERE priority_level >= 'medium'` compares strings and misses `'high'` — write `>= 'medium'::priority`.
- `DROP TYPE` currently works even when tables use the enum; this may change to require `CASCADE`.

Creating types with `CREATE TYPE` is also described in [Views, Macros, Custom Types, Triggers and Comments](../statements/views-macros-and-types.md).
