---
type: reference
title: Window Functions and the WINDOW Clause
description: DuckDB window functions — OVER with PARTITION BY and ORDER BY, general-purpose window functions (row_number, rank, dense_rank, lag, lead, first_value, nth_value, ntile, fill), aggregates as window functions with DISTINCT and ORDER BY arguments, IGNORE/RESPECT NULLS, frames (ROWS, RANGE, GROUPS) and their defaults, EXCLUDE, named windows with the WINDOW clause, and filtering with QUALIFY.
tags: [sql, functions, window-functions, over, partition-by, frames, window-clause, qualify]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-6809f713b09d8280b7e69870
    resource: repo://docs/2.0/sql/functions/window_functions.md
  - id: openwiki-source-446ef7afed4f2fad633b58b7
    resource: repo://docs/2.0/sql/query_syntax/qualify.md
  - id: openwiki-source-42f5680fd9ba344fb3ac5e55
    resource: repo://docs/2.0/sql/query_syntax/window.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Window Functions and the WINDOW Clause

Window functions compute a value for each row from multiple related rows. They are **blocking operators** that buffer their whole input, making them among the most memory-intensive operators (they can spill to disk; see [Performance Tuning](../../performance/tuning-workloads.md)). They may appear in `SELECT`, `ORDER BY` and `QUALIFY`.

```sql
SELECT row_number() OVER () FROM sales;                                  -- tip: rowid also numbers table rows
SELECT row_number() OVER (ORDER BY time) FROM sales;
SELECT row_number() OVER (PARTITION BY region ORDER BY time) FROM sales;
SELECT amount - lag(amount) OVER (ORDER BY time) FROM sales;
SELECT amount / sum(amount) OVER (PARTITION BY region) FROM sales;
```

## General-purpose window functions

| Function | Description | Returns |
| --- | --- | --- |
| `row_number([ORDER BY ...])` | Row number within the partition, from 1 | `BIGINT` |
| `rank([ORDER BY ...])` | Rank **with gaps** (row number of the first peer) | `BIGINT` |
| `dense_rank()` | Rank **without gaps** (counts peer groups) | `BIGINT` |
| `percent_rank([ORDER BY ...])` | `(rank() - 1) / (total partition rows - 1)` | `DOUBLE` |
| `cume_dist([ORDER BY ...])` | (rows preceding or peer with current) / partition rows | `DOUBLE` |
| `ntile(num_buckets[ ORDER BY ...])` | Bucket 1…`num_buckets`, as equal as possible | `BIGINT` |
| `lag(expr[, offset[, default]][ ORDER BY ...][ IGNORE NULLS])` | Value `offset` rows before (else `default`) | type of `expr` |
| `lead(expr[, offset[, default]][ ORDER BY ...][ IGNORE NULLS])` | Value `offset` rows after | type of `expr` |
| `first_value(expr[ ORDER BY ...][ IGNORE NULLS])`, `last_value(...)` | First / last row of the frame | type of `expr` |
| `nth_value(expr, nth[ ORDER BY ...][ IGNORE NULLS])` | nth row of the frame (1-based), `NULL` if none | type of `expr` |
| `fill(expr[ ORDER BY ...])` | Replace `NULL`s by linear interpolation along a single ordering key | type of `expr` |

```sql
SELECT percent_rank() OVER (ORDER BY x) AS percent_rank FROM (VALUES (42)) AS t(x);   -- 0.0
```

**`NULL` handling:** functions accepting `IGNORE NULLS` respect nulls by default (`RESPECT NULLS` makes it explicit). Aggregate window functions ignore nulls and do not accept `RESPECT NULLS` — except `list` (and aliases), which keeps `NULL`s unless filtered. E.g. a cumulative `sum(column) OVER (ORDER BY time)` repeats the previous value on `NULL` rows.

## Aggregates as window functions

Every [aggregate function](aggregate.md) works in a window, including `FILTER`. `first` and `last` are shadowed by the general-purpose versions (so no `FILTER`, but `IGNORE NULLS` works).

- **`DISTINCT` arguments:** `SELECT count(DISTINCT name) OVER (ORDER BY time) FROM sales;`, `list(DISTINCT name) OVER (...)`.
- **`ORDER BY` arguments** (different from the window ordering, no comma before it) make order-sensitive aggregates (`mode`, `list`, `string_agg`) deterministic:

```sql
SELECT mode(value ORDER BY time DESC) OVER (ORDER BY time) FROM sales;
```

DuckDB extends this argument ordering to all general-purpose window functions except `dense_rank`, applying it within the frame:

```sql
SELECT event, date, athlete, time,
    first_value(time ORDER BY time ASC) OVER w AS record_time,
    first_value(athlete ORDER BY time ASC) OVER w AS record_athlete,
FROM meet_results
WINDOW w AS (PARTITION BY event ORDER BY datetime)
ORDER BY ALL;
```

## Evaluation: partitions, ordering, frames

- **Partitioning** (optional) splits rows into independent groups; functions cannot see other partitions. Without it the whole relation is one partition.
- **Ordering** (optional) sorts each partition; without it, general-purpose functions, order-sensitive aggregates and framing are not well-defined. Window ordering does **not** sort the output — add an outer `ORDER BY`.
- **Frames** select rows around the current row, as `ROWS` (row counts), `RANGE` (a value delta on the single ordering expression, which must support subtraction unless only `UNBOUNDED PRECEDING` / `UNBOUNDED FOLLOWING` / `CURRENT ROW` are used), or `GROUPS` (peer groups). A frame may not start after it ends; frames are cropped at partition edges.

**Default frame:** the whole partition without `ORDER BY`; `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` with `ORDER BY`. The `CURRENT ROW` boundary includes all **peers** for `RANGE`/`GROUPS` but only the row itself for `ROWS`.

```sql
SELECT points, sum(points) OVER (ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) AS we FROM results;

SELECT "Plant", "Date",
    avg("MWh") OVER (
        PARTITION BY "Plant"
        ORDER BY "Date" ASC
        RANGE BETWEEN INTERVAL 3 DAYS PRECEDING AND INTERVAL 3 DAYS FOLLOWING)
        AS "MWh 7-day Moving Average"
FROM "Generation History"
ORDER BY 1, 2;

SELECT "Date", "Plant",
    avg("MWh") OVER (ORDER BY "Date" ASC GROUPS BETWEEN 3 PRECEDING AND 3 FOLLOWING) AS "MWh 7-day Moving Average"
FROM "Generation History"
ORDER BY 1, 2;
```

A `RANGE` frame handles missing days naturally; `GROUPS` counts distinct order values without date arithmetic.

### `EXCLUDE`

Excludes rows around the current row from the frame (for windowed aggregates and `first`, `last`, `nth_value`):

| Option | Effect |
| --- | --- |
| `EXCLUDE CURRENT ROW` | Only the current row |
| `EXCLUDE GROUP` | Current row and its peers |
| `EXCLUDE TIES` | Peers but not the current row |
| `EXCLUDE NO OTHERS` | Nothing (**default**) |

```sql
SELECT event, date, athlete, avg(time) OVER w AS recent,
FROM results
WINDOW w AS (
    PARTITION BY event
    ORDER BY date
    RANGE BETWEEN INTERVAL 10 DAYS PRECEDING AND INTERVAL 10 DAYS FOLLOWING
    EXCLUDE CURRENT ROW
)
ORDER BY event, date, athlete;
```

## Named windows: the `WINDOW` clause

The `WINDOW` clause defines named windows shared by several functions via `OVER ⟨name⟩`, avoiding repetition and letting functions share the data layout (faster). Multiple windows are comma-separated:

```sql
SELECT "Plant", "Date",
    min("MWh") OVER seven AS "MWh 7-day Moving Minimum",
    avg("MWh") OVER seven AS "MWh 7-day Moving Average",
    max("MWh") OVER three AS "MWh 3-day Moving Maximum"
FROM "Generation History"
WINDOW
    seven AS (PARTITION BY "Plant" ORDER BY "Date" ASC
              RANGE BETWEEN INTERVAL 3 DAYS PRECEDING AND INTERVAL 3 DAYS FOLLOWING),
    three AS (PARTITION BY "Plant" ORDER BY "Date" ASC
              RANGE BETWEEN INTERVAL 1 DAYS PRECEDING AND INTERVAL 1 DAYS FOLLOWING)
ORDER BY 1, 2;
```

Statistical aggregates are optimized for windows, e.g. moving box-and-whisker data with `quantile_cont("MWh", [0.25, 0.5, 0.75]) OVER seven`.

## Filtering window results: `QUALIFY`

Window functions run after `WHERE` and `HAVING`, so those clauses cannot filter on them. `QUALIFY` does, without a subquery or CTE:

```sql
SELECT schema_name, function_name,
    row_number() OVER (PARTITION BY schema_name ORDER BY function_name) AS function_rank
FROM duckdb_functions()
QUALIFY function_rank < 3;
```

See [GROUP BY, GROUPING SETS, HAVING, FILTER and QUALIFY](../query-syntax/grouping-and-filtering.md). In Python, windows are available via `.over(...)` on expressions (see [Python Expression API](../../clients/python/expressions-udfs-and-types.md)).
