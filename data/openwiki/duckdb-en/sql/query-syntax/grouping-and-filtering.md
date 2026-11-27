---
type: reference
title: GROUP BY, GROUPING SETS, HAVING, FILTER and QUALIFY
description: DuckDB's aggregation and post-filtering clauses — GROUP BY and GROUP BY ALL, grouping by unnest (new in 2.0), GROUPING SETS / ROLLUP / CUBE and GROUPING_ID (no-argument form new in 2.0), HAVING, the FILTER clause for per-aggregate conditions and static pivots, and QUALIFY for filtering window function results.
tags: [sql, group-by, group-by-all, grouping-sets, rollup, cube, having, filter, qualify]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-95ef60cab62b58e6e6aaae91
    resource: repo://docs/2.0/sql/query_syntax/filter.md
  - id: openwiki-source-15c1b99d6ce6d3d69ab0493d
    resource: repo://docs/2.0/sql/query_syntax/groupby.md
  - id: openwiki-source-2f3e8e879e578fc81b7ebdf0
    resource: repo://docs/2.0/sql/query_syntax/grouping_sets.md
  - id: openwiki-source-02df71b2129a0aab425f370d
    resource: repo://docs/2.0/sql/query_syntax/having.md
  - id: openwiki-source-446ef7afed4f2fad633b58b7
    resource: repo://docs/2.0/sql/query_syntax/qualify.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# GROUP BY, GROUPING SETS, HAVING, FILTER and QUALIFY

Aggregate functions are listed on [Aggregate Functions](../functions/aggregate.md); window functions on [Window Functions](../functions/window.md).

## `GROUP BY`

A `GROUP BY` makes the query an aggregate query (even without aggregates in `SELECT`). Rows with equal grouping values are combined; non-grouped columns must be aggregated.

```sql
SELECT city, count(*) FROM addresses GROUP BY city;
SELECT city, street_name, avg(income) FROM addresses GROUP BY city, street_name;
```

### `GROUP BY ALL`

Groups by every `SELECT` column that is not inside an aggregate — the column list lives in one place and the grouping granularity stays aligned with `SELECT`:

```sql
SELECT city, street_name FROM addresses GROUP BY ALL;                 -- deduplicate
SELECT city, street_name, avg(income) FROM addresses GROUP BY ALL;    -- = GROUP BY city, street_name
```

`GROUP BY ALL` also solves DuckDB's lack of functional-dependency inference (`SELECT j FROM tbl GROUP BY i` errors even if `i` is the primary key; alternatively use `any_value(j)`).

### Grouping by `unnest` (new in DuckDB 2.0)

```sql
SELECT unnest(tags) AS tag, count(*) AS n
FROM (VALUES (['a', 'b']), (['b', 'c']), (['b'])) t(tags)
GROUP BY unnest(tags)
ORDER BY tag;
```

## `GROUPING SETS`, `ROLLUP` and `CUBE`

Aggregate over several groupings in one query (not combinable with `GROUP BY ALL`). Columns not in a row's grouping set are `NULL`.

```sql
-- () is the empty set (ungrouped aggregate)
SELECT city, street_name, avg(income)
FROM addresses
GROUP BY GROUPING SETS ((city, street_name), (city), (street_name), ());

SELECT city, street_name, avg(income) FROM addresses GROUP BY CUBE (city, street_name);    -- same four sets
SELECT city, street_name, avg(income) FROM addresses GROUP BY ROLLUP (city, street_name);  -- (city, street_name), (city), ()
```

- `ROLLUP (country, city, zip)` → `(country, city, zip), (country, city), (country), ()` — hierarchical subtotals.
- `CUBE (country, city, zip)` → all `2^n` combinations.
- `GROUPING SETS ((course, type), course, type, ())` is equivalent to a `UNION ALL` of the four individual `GROUP BY`s with `NULL` placeholders.

### Identifying super-aggregate rows: `GROUPING_ID()`

Since grouped columns can contain real `NULL`s, use `GROUPING_ID(...)` (alias `grouping`), which returns a `BIGINT` bitfield: `0` for regular aggregate rows; for super-aggregate rows, a bit is set for each argument **not** in the grouping (the first bit corresponds to the **last** argument).

```sql
WITH days AS (
    SELECT year("generate_series") AS y, quarter("generate_series") AS q, month("generate_series") AS m
    FROM generate_series(DATE '2023-01-01', DATE '2023-12-31', INTERVAL 1 DAY)
)
SELECT y, q, m,
    GROUPING_ID(y, q, m) AS "grouping_id(y, q, m)",
    right(GROUPING_ID(y, q, m)::BIT::VARCHAR, 3) AS "y_q_m_bits"
FROM days
GROUP BY GROUPING SETS ((y, q, m), (y, q), (y), ())
ORDER BY y, q, m;
```

The arguments of `GROUPING_ID()` are independent of the grouping set definitions. **New in 2.0:** `GROUPING_ID()` / `GROUPING()` without arguments use all `GROUP BY` columns in `GROUP BY` order.

## `HAVING`

Filters **groups after** aggregation; it must directly follow `GROUP BY` and may use aggregates (unlike `WHERE`):

```sql
SELECT city, count(*) FROM addresses GROUP BY city HAVING count(*) >= 50;
SELECT city, street_name, avg(income)
FROM addresses
GROUP BY city, street_name
HAVING median(income) > 50000;
```

## `FILTER`

`FILTER (WHERE ...)` after an aggregate restricts the rows fed to that aggregate only (the `WHERE` keyword is optional):

```sql
SELECT
    count() AS total_rows,
    count() FILTER (i <= 5) AS lte_five,
    count() FILTER (i % 2 = 1) AS odds
FROM generate_series(1, 10) tbl(i);

SELECT
    sum(i) FILTER (i <= 5) AS lte_five_sum,
    median(i) FILTER (i % 2 = 1 AND i <= 5) AS odds_lte_five_median
FROM generate_series(1, 10) tbl(i);
```

- The condition acts on **rows**, not list values: `list(x) FILTER (WHERE y)` can still contain `NULL`; use `list(x) FILTER (WHERE x IS NOT NULL)` to drop them.
- Simple conditional counts can also use boolean `sum`, e.g. `sum(i <= 5)`.
- **Static pivots:** `count(i) FILTER (year = 2022) AS "2022", ...` produces one column per value. It is equivalent to `count(CASE WHEN year = 2022 THEN i END)` for `NULL`-ignoring aggregates, but **only `FILTER` works correctly** with aggregates that do not ignore `NULL`s, such as `first` — `first(CASE WHEN ...)` returns `NULL` whenever the first evaluated row does not match. For dynamic pivots see [PIVOT and UNPIVOT](../statements/pivot-and-unpivot.md).

## `QUALIFY`

`QUALIFY` filters the results of **window functions**, as `HAVING` does for aggregates, avoiding a subquery or CTE. It comes after the `WINDOW` clause and before `ORDER BY`; the window function may be in `QUALIFY` itself or referenced by its `SELECT` alias.

```sql
SELECT schema_name, function_name,
    row_number() OVER (PARTITION BY schema_name ORDER BY function_name) AS function_rank
FROM duckdb_functions()
QUALIFY function_rank < 3;

SELECT schema_name, function_name, row_number() OVER my_window AS function_rank
FROM duckdb_functions()
WINDOW my_window AS (PARTITION BY schema_name ORDER BY function_name)
QUALIFY row_number() OVER my_window < 3;
```

Equivalent without `QUALIFY`:

```sql
WITH ranked_functions AS (
    SELECT schema_name, function_name,
        row_number() OVER (PARTITION BY schema_name ORDER BY function_name) AS function_rank
    FROM duckdb_functions()
)
SELECT * FROM ranked_functions WHERE function_rank < 3;
```

Clause order within a full `SELECT` is described on [SELECT, FROM, WHERE …](select-from-where.md).
