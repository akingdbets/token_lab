---
type: reference
title: Aggregate Functions
description: DuckDB aggregate functions and their modifiers — DISTINCT, ORDER BY inside aggregates, FILTER, NULL handling and empty groups; general aggregates (arg_max/arg_min, count, list, string_agg, histogram, lttb new in 2.0, decimal_average new in 2.0, top-N min/max), approximate aggregates, statistical aggregates (quantiles, regression), ordered-set WITHIN GROUP aggregates, and grouping().
tags: [sql, functions, aggregates, group-by, quantile, statistics, approximate, string-agg]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-a1b702e095cf546cdc20031d
    resource: repo://docs/2.0/sql/functions/aggregates.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Aggregate Functions

Aggregates combine many rows into one value, changing the result's cardinality (unlike scalar and window functions). They may appear in `SELECT`, `HAVING` and `ORDER BY`. Grouping clauses are on [GROUP BY, GROUPING SETS, HAVING, FILTER and QUALIFY](../query-syntax/grouping-and-filtering.md); most aggregates can also be used as [window functions](window.md).

```sql
SELECT sum(amount) FROM sales;
SELECT region, sum(amount) FROM sales GROUP BY region;
SELECT region FROM sales GROUP BY region HAVING sum(amount) > 100;
SELECT count(DISTINCT region) FROM sales;
SELECT sum(amount), sum(amount) FILTER (region != 'north') FROM sales;
SELECT list(region ORDER BY amount DESC) FROM sales;
SELECT first(amount ORDER BY date ASC) FROM sales;
SELECT unnest(lttb(x, sin(x), 5 ORDER BY x)) AS point FROM range(0, 100) t(x);
```

## Modifiers

**`DISTINCT`** — only distinct values are aggregated (usually with `count`); ignored for duplicate-insensitive aggregates like `min`/`max`.

**`ORDER BY` inside the call** — written after the last argument **without a comma**:

```sql
SELECT ⟨aggregate_function⟩(⟨arg⟩, ⟨sep⟩ ORDER BY ⟨ordering_criteria⟩);
SELECT string_agg(s, ', ' ORDER BY s DESC) AS countdown FROM tbl;   -- 3, 2, 1
```

Most aggregates ignore ordering, but order-sensitive ones — `first`, `last`, `list`, `string_agg` (`group_concat`, `listagg`) and others marked "affected by ordering" — are **non-deterministic without it**. With `DISTINCT`, all `ORDER BY` expressions must be aggregate arguments:

```sql
SELECT list(DISTINCT x ORDER BY x DESC) FROM (VALUES (1), (2), (2), (3)) t(x);              -- [3, 2, 1]
SELECT list(DISTINCT x ORDER BY y DESC) FROM (VALUES (1, 10), (1, 20), (2, 5)) t(x, y);
-- Binder Error: In a DISTINCT aggregate, ORDER BY expressions must appear in the argument list
```

**`FILTER (WHERE ...)`** — aggregates only matching rows (see [FILTER](../query-syntax/grouping-and-filtering.md)).

### `NULL`s and empty groups

- All general aggregates ignore `NULL`s **except** `list` (`array_agg`), `first` (`arbitrary`) and `last`. Use `list(x) FILTER (WHERE x IS NOT NULL)`, or `any_value` instead of `first`.
- All general aggregates **except `count` return `NULL` on empty groups** — `list` does not return `[]`, `sum` not `0`, `string_agg` not `''`.

## General aggregates

| Function | Description |
| --- | --- |
| `any_value(arg)` | First non-`NULL` value |
| `arg_max(arg, val)` / `arg_min(arg, val)` | `arg` at the row with max/min `val` (rows with `NULL` `arg` or `val` ignored); aliases `argmax`, `max_by` / `argmin`, `min_by` |
| `arg_max(arg, val, n)` / `arg_min(arg, val, n)` | `LIST` of `arg` for top/bottom `n` rows by `val` |
| `arg_max_null` / `arg_min_null` | Only rows with `NULL` `val` are ignored |
| `arg_max_nulls_last(arg, val[, n])` / `arg_min_nulls_last` | `NULL` `arg` kept; `NULL` `val` sorted last |
| `avg(arg)` (`mean`) | Average of non-`NULL` values |
| `bit_and`, `bit_or`, `bit_xor`, `bitstring_agg` | Bitwise aggregates |
| `bool_and(arg)`, `bool_or(arg)` | All / any true |
| `count()` / `count(*)` | Number of rows |
| `count(arg)` | Rows where `arg` is not `NULL` |
| `countif(arg)` | Rows where `arg` is true |
| `decimal_average(arg)` | Exact `DECIMAL` average with banker's rounding, same width/scale — **new in 2.0** |
| `favg(arg)`, `fsum(arg)` | Kahan-summation average / sum (more accurate floats) |
| `first(arg)` / `last(arg)` | First / last value (incl. `NULL`) |
| `geometric_mean(arg)` | Geometric mean |
| `histogram(arg[, boundaries])` | `MAP` of buckets to counts (boundaries: left-open, right-closed bins) |
| `histogram_exact(arg, elements)` | Counts for given elements plus a catch-all |
| `histogram_values(source, col_name[, bin_count[, technique]])` | Table macro returning bin upper bounds and counts |
| `list(arg)` (`array_agg`) | `LIST` of all values |
| `lttb(x, y, n)` | Largest-Triangle-Three-Buckets downsampling to ≤ `n` points (`n >= 2`, constant); returns `LIST` of `STRUCT(x, y)` incl. first and last point; needs `ORDER BY x` — **new in 2.0** |
| `max(arg)` / `min(arg)` | Max / min |
| `max(arg, n)` / `min(arg, n)` | `LIST` of top / bottom `n` values |
| `product(arg)` | Product |
| `string_agg(arg[, sep])` | Concatenation, default separator `,` |
| `sum(arg)` | Sum; counts `true` values for booleans |
| `weighted_avg(arg, weight)` | Weighted average (rows with `NULL` weight skipped) |

Top-N per group in one aggregate: `SELECT max(val, 3) FROM t1 GROUP BY grp;` (see [Friendly SQL](../dialect/friendly-sql.md)).

## Approximate aggregates

| Function | Description | Example |
| --- | --- | --- |
| `approx_count_distinct(x)` | HyperLogLog distinct count | `approx_count_distinct(A)` |
| `approx_quantile(x, pos)` | T-Digest quantile | `approx_quantile(A, 0.5)` |
| `approx_top_k(arg, k)` | `LIST` of the `k` most frequent values (Filtered Space-Saving) | |
| `reservoir_quantile(x, quantile, sample_size = 8192)` | Reservoir-sampling quantile; default sample **8192** | `reservoir_quantile(A, 0.5, 1024)` |

## Statistical aggregates

These ignore `NULL` inputs (single column) or pairs with a `NULL` (two columns).

| Function | Description |
| --- | --- |
| `corr(y, x)` | Correlation coefficient: `covar_pop(y, x) / (stddev_pop(x) * stddev_pop(y))` |
| `covar_pop(y, x)` / `covar_samp(y, x)` | Population / sample (Bessel-corrected) covariance |
| `entropy(x)` | Log-2 entropy |
| `kurtosis(x)` / `kurtosis_pop(x)` | Excess kurtosis with / without bias correction |
| `skewness(x)` | Skewness |
| `mad(x)` | Median absolute deviation `median(abs(x - median(x)))` (temporal → positive `INTERVAL`) |
| `median(x)` | Middle value; even counts average quantitative values, ordinal values take the lower one; = `quantile_cont(x, 0.5)` |
| `mode(x)` | Most frequent value |
| `quantile_cont(x, pos)` | Interpolated quantile for `-1 <= pos <= 1` (`pos` may be a list) |
| `quantile_disc(x, pos)` (`quantile`) | Discrete quantile; negative positions select in descending order |
| `regr_avgx`, `regr_avgy`, `regr_count`, `regr_intercept`, `regr_r2`, `regr_slope`, `regr_sxx`, `regr_sxy`, `regr_syy` | Linear regression helpers (`y` dependent, `x` independent); `regr_slope = regr_sxy / regr_sxx` |
| `sem(x)` | Standard error of the mean |
| `stddev_pop(x)` / `stddev_samp(x)` (`stddev`) | Population / sample standard deviation |
| `var_pop(x)` / `var_samp(x)` (`variance`) | Population / sample variance |

## Ordered-set aggregates

`WITHIN GROUP (ORDER BY ...)` forms are rewritten to equivalent aggregates:

| Function | Equivalent |
| --- | --- |
| `mode() WITHIN GROUP (ORDER BY column [ASC\|DESC])` | `mode(column ORDER BY column [ASC\|DESC])` |
| `percentile_cont(fraction[s]) WITHIN GROUP (ORDER BY column)` | `quantile_cont(column, fraction[s] ORDER BY column)` |
| `percentile_disc(fraction[s]) WITHIN GROUP (ORDER BY column)` | `quantile_disc(column, fraction[s] ORDER BY column)` |

## Miscellaneous

`grouping(...)` (alias `grouping_id`) returns an integer identifying which expressions were grouped on in queries with `ROLLUP`, `CUBE` or `GROUPING SETS` (see [GROUPING SETS](../query-syntax/grouping-and-filtering.md)).

Memory notes: aggregates with complex state (`list`, `mode`, `quantile`, `string_agg`, approximate functions) allocate outside the buffer manager, and ordered (holistic) aggregates and `string_agg` cannot spill to disk — see [Performance Tuning](../../performance/tuning-workloads.md).
