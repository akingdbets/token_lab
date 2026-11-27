---
type: reference
title: Struct, Map, Union, Enum and Nested Functions
description: Functions for DuckDB STRUCT and TUPLE values (struct_pack, row, struct_extract, struct_extract_at, struct_insert, struct_update, struct_concat, struct_keys/values, remap_struct), MAP values (map_extract vs map_extract_value, map_entries, map_from_entries, map_concat, switch), UNION values (union_value, union_extract, union_tag) and ENUM types (enum_range, enum_code), plus a map of nested-type function pages.
tags: [sql, functions, struct, tuple, map, union, enum, nested]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-41697d3b4e7690435bac8f5c
    resource: repo://docs/2.0/sql/functions/enum.md
  - id: openwiki-source-2f6492c4510c64ea336ed644
    resource: repo://docs/2.0/sql/functions/map.md
  - id: openwiki-source-43697ac89e2bc3edfc61f238
    resource: repo://docs/2.0/sql/functions/struct.md
  - id: openwiki-source-b5cff355c84ef199313f5868
    resource: repo://docs/2.0/sql/functions/union.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Struct, Map, Union, Enum and Nested Functions

Nested types have dedicated function sets: `ARRAY` and `LIST` → [List, Array and Lambda Functions](list-array-and-lambda.md); `STRUCT` (also `TUPLE`), `MAP`, `UNION` and `ENUM` → this page; `VARIANT` → [VARIANT and GEOMETRY Types](../data-types/variant-and-geometry.md). Type semantics are on [Nested Types](../data-types/nested-types.md).

## Struct and tuple functions

Position-based functions (`struct[idx]`, `struct_extract_at`, `struct_contains`, `struct_position`, `struct_values`) also work on `TUPLE`s.

| Function | Example | Result |
| --- | --- | --- |
| `struct.entry` (dot notation) | `({'i': 3, 's': 'string'}).i` | `3` |
| `struct['entry']` | `({'i': 3, 's': 'string'})['i']` | `3` |
| `struct[idx]` (tuples, 1-based) | `(row(42, 84))[1]` | `42` |
| `struct_pack(name := any, ...)` | `struct_pack(i := 4, s := 'string')` | `{'i': 4, 's': string}` |
| `row(any, ...)` | `row(i, i % 4, i / 4)` | `(10, 2, 2.5)` (a `TUPLE`) |
| `struct_extract(struct, 'entry')` | `struct_extract({'i': 3, 'v2': 3, 'v3': 0}, 'i')` | `3` |
| `struct_extract(tuple, idx)` | `struct_extract(row(42, 84), 1)` | `42` |
| `struct_extract_at(struct, idx)` | `struct_extract_at({'v1': 10, 'v2': 20, 'v3': 3}, 2)` | `20` |
| `struct_insert(struct, name := any, ...)` | `struct_insert({'a': 1}, b := 2)` | `{'a': 1, 'b': 2}` (add only) |
| `struct_update(struct, name := any, ...)` | `struct_update({'a': 1, 'b': 2}, b := 3, c := 4)` | `{'a': 1, 'b': 3, 'c': 4}` (add or update) |
| `struct_concat(structs...)` | `struct_concat(struct_pack(i := 4), struct_pack(s := 'string'))` | `{'i': 4, 's': string}` |
| `struct_contains(struct, entry)` | `struct_contains(row(1, 2, 3), 2)` | `true` |
| `struct_position(struct, entry)` | `struct_position(row(1, 2, 3), 2)` | `2` (1-based; `NULL` if absent) |
| `struct_keys(struct)` | `struct_keys({'a': 1, 'b': 2})` | `[a, b]` |
| `struct_values(struct)` | `struct_values({'a': 1, 'b': 2, 'c': 3})` | `(1, 2, 3)` |

`struct_extract` on a missing key raises an error (struct keys behave like columns), whereas list and map lookups return `NULL`.

### `remap_struct`

`remap_struct(input, target_type, mapping, defaults)` reshapes a `STRUCT`, `LIST` or `MAP` into the type of `target_type`, renaming/reordering fields and filling missing ones from `defaults`:

```sql
SELECT remap_struct(
    {'i': 1, 'j': 2},
    NULL::STRUCT(v1 INT, v2 INT, v3 INT),
    {'v1': 'j', 'v3': 'i'},
    {'v2': NULL::INTEGER}
);   -- {'v1': 2, 'v2': NULL, 'v3': 1}
```

For a nested target `STRUCT`, give the mapping value as `ROW(source_field, {inner_mapping})` and nest the defaults the same way.

Other struct operations: `unnest(struct)` and `struct.*` expand entries into columns; `ALTER TABLE ... ADD/DROP/RENAME` changes struct sub-fields (see [Nested Types](../data-types/nested-types.md)).

## Map functions

| Function | Example | Result |
| --- | --- | --- |
| `map()` | `map()` | `{}` |
| `map[key]` / `map_extract_value(map, key)` | `map([100, 5], ['a', 'b'])[100]` | `a` (`NULL` if missing) |
| `map_extract(map, key)` (`element_at`) | `map_extract(map([100, 5], [42, 43]), 100)` | `[42]` (`[]` if missing) |
| `map_keys(map)` / `map_values(map)` | `map_keys(map([100, 5], [42,43]))` | `[100, 5]` |
| `map_entries(map)` | `map_entries(map([100, 5], [42, 43]))` | `[{'key': 100, 'value': 42}, {'key': 5, 'value': 43}]` |
| `map_from_entries(STRUCT(k, v)[])` | `map_from_entries([{k: 5, v: 'val1'}, {k: 3, v: 'val2'}])` | `{5=val1, 3=val2}` |
| `map_concat(maps...)` | `map_concat(MAP {'key1': 10, 'key2': 20}, MAP {'key3': 30}, MAP {'key2': 5})` | `{key1=10, key2=5, key3=30}` (last map wins) |
| `map_contains(map, key)` | `map_contains(MAP {'key1': 10, 'key2': 20, 'key3': 30}, 'key2')` | `true` |
| `map_contains_value(map, value)` | `map_contains_value(MAP {'key1': 10, ...}, 20)` | `true` |
| `map_contains_entry(map, key, value)` | `map_contains_entry(MAP {'key1': 10, 'key2': 20, 'key3': 30}, 'key2', 20)` | `true` |
| `cardinality(map)` | `cardinality(map([4, 2], ['a', 'b']))` | `2` |
| `switch(key, map[, default])` | `switch('key1', MAP {'key1': 10, 'key2': 20})` | `10` (`NULL` or `default` if missing) |

The key argument's type must match the map's key type, or an error is raised. `'key1' IN MAP {...}` checks keys too (see [Expressions](../expressions.md)), and `SWITCH(expr, MAP {...}, default)` is also usable as `CASE` sugar.

## Union functions

| Function | Example | Result |
| --- | --- | --- |
| `union_value(tag := any)` | `union_value(k := 'hello')` | `hello` of type `UNION(k VARCHAR)` |
| `union.tag` / `union_extract(union, 'tag')` | `(union_value(k := 'hello')).k` | `hello` (`NULL` if another tag is active) |
| `union_tag(union)` | `union_tag(union_value(k := 'foo'))` | `'k'` (as an `ENUM`) |

```sql
CREATE TABLE tbl1 (u UNION(num INTEGER, str VARCHAR));
INSERT INTO tbl1 VALUES (1), ('two'), (union_value(str := 'three'));
SELECT union_extract(u, 'str') AS str, union_tag(u) AS t FROM tbl1;
```

## Enum functions

With `CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy', 'anxious');`. Arguments can be `NULL` of the type or any value; most results depend only on the type, except `enum_code` and `enum_range_boundary`.

| Function | Example | Result |
| --- | --- | --- |
| `enum_code(enum_value)` | `enum_code('happy'::mood)` | `2` (0-based backing value) |
| `enum_first(enum)` | `enum_first(NULL::mood)` | `sad` |
| `enum_last(enum)` | `enum_last(NULL::mood)` | `anxious` |
| `enum_range(enum)` | `enum_range(NULL::mood)` | `[sad, ok, happy, anxious]` |
| `enum_range_boundary(enum, enum)` | `enum_range_boundary(NULL, 'happy'::mood)` | `[sad, ok, happy]` |

Enums also cast to `VARCHAR` automatically, so all [text functions](text-and-pattern-matching.md) apply to them.
