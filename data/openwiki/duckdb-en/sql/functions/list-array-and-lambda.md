---
type: reference
title: List, Array and Lambda Functions
description: Functions for DuckDB LIST and ARRAY values — indexing and slicing rules, list operators (&&, @>, <@, ||, <=>, <->), common list_* functions and their array_* aliases, list comprehensions, range and generate_series, list_aggregate and list_* rewrites, list_sort ordering, flatten, ARRAY distance/similarity functions, and lambda functions (list_transform, list_filter, list_reduce, index parameters, scoping, the deprecated -> syntax).
tags: [sql, functions, list, array, lambda, list-transform, list-comprehension, slicing]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-82a30ad665b9c31f85ca6c82
    resource: repo://docs/2.0/sql/functions/lambda.md
  - id: openwiki-source-e8b37b05346b394771e9effe
    resource: repo://docs/2.0/sql/functions/list.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# List, Array and Lambda Functions

All list functions also work on fixed-size `ARRAY`s; most have `array_*` aliases for PostgreSQL compatibility. Type details are on [Nested Types](../data-types/nested-types.md).

## Indexing and slicing

`list[index]` is **1-based** (negative indexes count from the end). Slices: `list_slice(list, begin, end[, step])`, `array_slice(...)`, `list[begin:end]`, `list[begin:end:step]`.

- `begin`/`end` are inclusive; negatives count from the end; `begin > length` gives `[]`; `end > length` is clamped; `end < begin` gives `[]`; a too-negative `begin` is clamped to the start.
- Omitted bounds in bracket notation default to the start/end; with a `step` and no `end`, write `-` (`[:-:2]`).
- `step` must be non-zero; a negative step reverses and swaps `begin`/`end` before applying the rules.

```sql
SELECT list_slice([1, 2, 3, 4, 5], 2, 4);   -- [2, 3, 4]
SELECT ([1, 2, 3, 4, 5])[2:4:2];            -- [2, 4]
SELECT ([1, 2, 3, 4, 5])[4:2:-2];           -- [4, 2]
SELECT ([1, 2, 3, 4, 5])[1:99:-1];          -- [] (bounds swapped → begin 99)
SELECT ([1, 2, 3, 4, 5])[:-:-2];            -- [5, 3, 1]
```

## List operators

| Operator | Meaning | Example | Result |
| --- | --- | --- | --- |
| `&&` | `list_has_any` | `[1, 2, 3, 4, 5] && [2, 5, 5, 6]` | `true` |
| `@>` | `list_has_all` (right is the sublist) | `[1, 2, 3, 4] @> [3, 4, 3]` | `true` |
| `<@` | `list_has_all` (left is the sublist) | `[1, 4] <@ [1, 2, 3, 4]` | `true` |
| `\|\|` | Concatenation; any `NULL` → `NULL` | `[1, 2, 3] \|\| [4, 5, 6]` | `[1, 2, 3, 4, 5, 6]` |
| `<=>` | `list_cosine_distance` | `[1, 2, 3] <=> [1, 2, 5]` | `0.024099927051466796` |
| `<->` | `list_distance` (Euclidean) | `[1, 2, 3] <-> [1, 2, 5]` | `2.0` |

## Common list functions

| Function (aliases) | Description |
| --- | --- |
| `list_value(arg, ...)` (`list_pack`) | Create a list |
| `list_extract(list, index)` (`list_element`, `array_extract`) | 1-based element |
| `length(list)` (`len`, `array_length`) | Length |
| `list_append(list, el)` (`array_append`, `array_push_back`), `list_prepend(el, list)` | Add elements |
| `array_pop_back(list)`, `array_pop_front(list)` | Drop last / first |
| `list_concat(l1, ..., ln)` (`list_cat`, `array_concat`, `array_cat`), `concat(...)` | Concatenate; `NULL` inputs skipped (unlike `\|\|`) |
| `list_contains(list, el)` (`list_has`, `array_contains`, `array_has`, `contains`) | Membership |
| `list_has_all(l1, l2)`, `list_has_any(l1, l2)` | Set tests; `NULL`s ignored |
| `list_position(list, el)` (`list_indexof`, `array_position`) | 1-based index or `NULL` |
| `list_distinct(list)` | Remove duplicates **and `NULL`s**; order not preserved |
| `list_unique(list)` | Count unique elements |
| `list_intersect(l1, l2)` | Common elements, no duplicates |
| `list_reverse(list)` | Reverse |
| `list_sort(list[, order][, nulls])`, `list_reverse_sort(list[, nulls])`, `list_grade_up(list, ...)` | Sorting / sort indexes |
| `list_select(values, indexes)`, `list_where(values, mask)` | Select by index list / boolean mask |
| `list_resize(list, size[, value])` | Resize, padding with `value` or `NULL` |
| `list_zip(l1, ..., ln[, truncate])` | List of structs; length of the longest list unless truncating |
| `flatten(nested_list)` | Concatenate one nesting level |
| `list_cosine_similarity`, `list_cosine_distance`, `list_distance`, `list_inner_product` (`list_dot_product`), `list_negative_inner_product` | Vector math on same-size lists |
| `array_to_string(list, delimiter)` | Join elements into a string |
| `repeat(list, count)` | Repeat |
| `unnest(list)` | Expand to rows (changes cardinality) |

## List comprehensions

```sql
SELECT [lower(x) FOR x IN strings] AS strings FROM (VALUES (['Hello', '', 'World'])) t(strings);
SELECT [upper(x) FOR x IN strings IF len(x) > 0] AS strings FROM (VALUES (['Hello', '', 'World'])) t(strings);
SELECT [4, 5, 6] AS l, [x FOR x, i IN l IF i != 2] AS filtered;   -- [4, 6]; i is the 1-based position
```

`[f(x) FOR x IN l IF g(x)]` is rewritten to `list_apply` + `list_filter` + `list_apply`.

## Range functions

| Function | Stop | Example | Result |
| --- | --- | --- | --- |
| `range(start[, stop][, step])` | exclusive | `range(2, 5)` | `[2, 3, 4]` |
| `generate_series(start[, stop][, step])` | inclusive | `generate_series(2, 5, 3)` | `[2, 5]` |

`start` defaults to 0 and `step` to 1 (`range(5)` = `[0, 1, 2, 3, 4]`). Both also work as table functions, including for timestamps, where `stop` and `step` are required:

```sql
SELECT * FROM generate_series(DATE '1992-01-01', DATE '1992-03-01', INTERVAL '1' MONTH);
SELECT generate_subscripts([4, 5, 6], 1) AS i;   -- 1, 2, 3
```

## List aggregates

`list_aggregate(list, 'function_name', ...)` (aliases `list_aggr`, `aggregate`, `array_aggregate`, `array_aggr`) runs any aggregate over a list's elements; extra arguments are passed to the aggregate. Order-sensitive aggregates use list order; `ORDER BY`, `DISTINCT` and `FILTER` are not supported (emulate with `list_sort`, `list_distinct`, `list_filter`).

```sql
SELECT list_aggregate([1, 2, -4, NULL], 'min');                 -- -4
SELECT list_aggregate([2, 4, 8, 42], 'string_agg', '|');       -- 2|4|8|42
SELECT list_sum([2, 4, 8, 42]);                                 -- 56 (rewrite)
SELECT array_to_string([1, 2, 3], '-') AS str;                  -- 1-2-3
```

Rewrites exist for many aggregates: `list_min`, `list_max`, `list_sum`, `list_avg`, `list_count`, `list_first`, `list_last`, `list_median`, `list_mode`, `list_product`, `list_string_agg`, `list_stddev_samp`, `list_var_pop`, `list_histogram`, `list_bool_and`, `list_any_value`, etc.

## Sorting lists

`list_sort` behaves like `ORDER BY`; default **`ASC NULLS LAST`** (changeable via the default-order settings). Optional second argument `'ASC'`/`'DESC'`, third `'NULLS FIRST'`/`'NULLS LAST'`; `list_reverse_sort` takes only the `NULL` order.

```sql
SELECT list_sort([1, 3, NULL, 5, NULL, -5]);               -- [-5, 1, 3, 5, NULL, NULL]
SELECT list_sort([1, 3, NULL, 2], 'DESC', 'NULLS FIRST');  -- [NULL, 3, 2, 1]
SELECT list_reverse_sort([1, 3, NULL, 2], 'NULLS LAST');   -- [3, 2, 1, NULL]
```

## `flatten`

Concatenates sub-lists **one level** only: `flatten([[1, 2], [3, 4]])` → `[1, 2, 3, 4]`; deeper lists keep inner nesting. Edge cases: `flatten([])` → `[]`, `flatten(NULL)` → `NULL`, `flatten([NULL])` → `[]`, `flatten([[NULL]])` → `[NULL]`, `flatten([[NULL], [NULL]])` → `[NULL, NULL]` (no de-duplication).

## Array-native functions

For same-size `ARRAY`s without `NULL` elements: `array_value(arg, ...)`, `array_cosine_similarity`, `array_cosine_distance`, `array_distance`, `array_inner_product` (`array_dot_product`), `array_negative_inner_product` (`array_negative_dot_product`), and `array_cross_product` (size-3 arrays).

```sql
SELECT array_cosine_similarity(x.v, y.v) FROM x, y WHERE x.i = y.i;
```

## Lambda functions

Syntax: `lambda ⟨parameters⟩ : ⟨expression⟩`, e.g. `lambda param : param > 1`, `lambda acc, x : acc + x`. The first parameter receives the element; an optional **last** parameter receives the 1-based index. The body must be scalar: no subqueries (`Binder Error: subqueries in lambda expressions are not supported`), no table functions; scalar macros without subqueries are allowed. Lambdas must be defined inline (a macro cannot return one). Lambdas also work in `COLUMNS(lambda c: ...)`.

| Function (aliases) | Description |
| --- | --- |
| `list_transform(list, lambda)` (`list_apply`, `array_transform`, `array_apply`, `apply`) | Map each element |
| `list_filter(list, lambda)` (`array_filter`, `filter`) | Keep elements where the lambda is true |
| `list_reduce(list, lambda(acc, x)[, initial_value])` (`array_reduce`, `reduce`) | Fold into one value |

```sql
SELECT list_transform([1, 2, NULL, 3], lambda x: x + 1);                     -- [2, 3, NULL, 4]
SELECT list_filter([5, -6, NULL, 7], lambda x: x > 0);                       -- [5, 7]
SELECT list_filter([1, 3, 1, 5], lambda x, i: x > i);                        -- [3, 5]
SELECT list_reduce([1, 2, 3, 4], lambda acc, x: acc + x);                    -- 10
SELECT list_reduce(['a', 'b', 'c', 'd'], lambda x, y, i: x || ' - ' || CAST(i AS VARCHAR) || ' - ' || y, 'INITIAL');
SELECT list_transform(list_filter([0, 1, 2, 3, 4, 5], lambda x: x % 2 = 0), lambda y: y * y);   -- [0, 4, 16]
```

**Scoping order:** inner lambda parameters, outer lambda parameters, column names, macro parameters.

**Deprecated syntax:** the single-arrow form `x -> x + 1` was deprecated in 1.3; **DuckDB 2.0 disables it by default** (`lambda_syntax = 'default'` allows only `lambda x : ...`). `SET lambda_syntax = 'enable_single_arrow';` restores it temporarily; DuckDB 2.1 will remove the setting and the arrow syntax.
