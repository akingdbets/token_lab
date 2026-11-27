---
type: reference
title: SELECT, FROM, WHERE, ORDER BY, LIMIT, VALUES, Sampling and Prepared Statements
description: The core DuckDB query clauses — canonical SELECT clause order, column indexes and prefix aliases, the rowid pseudocolumn, DISTINCT and DISTINCT ON, WHERE, ORDER BY with NULL ordering defaults and ORDER BY ALL, LIMIT/OFFSET and FETCH FIRST (new in 2.0), VALUES lists, USING SAMPLE / TABLESAMPLE with reservoir, bernoulli and system methods, and prepared statements with ?, $1 and $name parameters plus session-variable defaults (new in 2.0).
tags: [sql, select, where, order-by, limit, fetch, values, sampling, prepared-statements]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-a07a29e37cff72d1caadf638
    resource: repo://docs/2.0/sql/query_syntax/limit.md
  - id: openwiki-source-bc0ff6f3559d9b68113d9850
    resource: repo://docs/2.0/sql/query_syntax/orderby.md
  - id: openwiki-source-2cf99f7d5b7f7f1d5a498a9d
    resource: repo://docs/2.0/sql/query_syntax/prepared_statements.md
  - id: openwiki-source-7212d629ead37272e00dfac4
    resource: repo://docs/2.0/sql/query_syntax/samples.md
  - id: openwiki-source-835ad97702892b3d580416d8
    resource: repo://docs/2.0/sql/statements/select.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# SELECT, FROM, WHERE, ORDER BY, LIMIT, VALUES, Sampling and Prepared Statements

Joins and the `FROM` clause are covered on [FROM Clause and Joins](joins.md); aggregation and post-filters on [GROUP BY, GROUPING SETS, HAVING, FILTER and QUALIFY](grouping-and-filtering.md); CTEs and set operations on [CTEs, Recursive Queries, Set Operations, UNNEST and query()](ctes-set-operations-unnest.md).

## The `SELECT` statement

A `SELECT` returns rows. Its clauses appear in this canonical order:

```sql
SELECT ⟨select_list⟩
FROM ⟨tables⟩
    USING SAMPLE ⟨sample_expression⟩
WHERE ⟨condition⟩
GROUP BY ⟨groups⟩
HAVING ⟨group_filter⟩
    WINDOW ⟨window_expression⟩
    QUALIFY ⟨qualify_filter⟩
ORDER BY ⟨order_expression⟩
LIMIT ⟨n⟩;
```

DuckDB also accepts `FROM`-first syntax (`FROM tbl SELECT ...`, or `FROM tbl` alone for `SELECT *`); see [Friendly SQL](../dialect/friendly-sql.md).

```sql
SELECT * FROM tbl;
SELECT j FROM tbl WHERE i = 3;
SELECT i, sum(j) FROM tbl GROUP BY i;
SELECT * FROM tbl ORDER BY i DESC LIMIT 3;
SELECT #1, #3 FROM tbl;               -- columns by 1-based index
SELECT DISTINCT city FROM addresses;
```

### The `rowid` pseudocolumn

Every table has a `rowid` pseudocolumn holding the row identifier of its physical storage location:

```sql
CREATE TABLE t (id INTEGER, content VARCHAR);
INSERT INTO t VALUES (42, 'hello'), (43, 'world');
SELECT rowid, id, content FROM t;     -- rowid 0, 1
```

- Row ids are contiguous (0, 1, …) if no rows were deleted.
- They are stable within a transaction but **should not be used as identifiers** across transactions — use a primary key or sequence instead.
- A user column named `rowid` shadows the pseudocolumn.

## The `SELECT` clause

```sql
SELECT col1 + col2 AS res, sqrt(col1) AS root FROM tbl;
SELECT res: col1 + col2, root: sqrt(col1) FROM tbl;    -- prefix aliases
SELECT * FROM tbl;
SELECT DISTINCT city FROM addresses;
SELECT count(*) FROM addresses;
SELECT * EXCLUDE (city) FROM addresses;
SELECT * REPLACE (lower(city) AS city) FROM addresses;
SELECT COLUMNS('number\d+') FROM addresses;
```

Star expressions and `COLUMNS(...)` are described on [Expressions](../expressions.md).

**`DISTINCT`** removes duplicate rows; it requires a hash over the whole result and is relatively expensive. **`DISTINCT ON (...)`** keeps one row per distinct value of the given expressions — combine it with `ORDER BY` to pick *which* row:

```sql
-- the largest city per country
SELECT DISTINCT ON(country) city, population
FROM cities
ORDER BY population DESC;
```

Without `ORDER BY`, the row chosen per group is arbitrary.

## `WHERE`

`WHERE` filters rows before grouping; any boolean expression is allowed:

```sql
SELECT * FROM tbl WHERE id = 3;
SELECT * FROM tbl WHERE name ILIKE '%mark%';         -- case-insensitive
SELECT * FROM tbl WHERE id = 3 OR id = 7;
```

## `ORDER BY`

```sql
SELECT * FROM addresses ORDER BY city;
SELECT * FROM addresses ORDER BY city DESC NULLS LAST;
SELECT * FROM addresses ORDER BY city, zip;
SELECT * FROM addresses ORDER BY city COLLATE DE;     -- collation
SELECT * FROM addresses ORDER BY 1, 2;                -- column positions, from 1
SELECT * FROM addresses ORDER BY ALL;                 -- all columns, left to right
SELECT * FROM addresses ORDER BY ALL DESC;
```

- **Default:** `ASC NULLS LAST`. DuckDB keeps `NULLS LAST` even for `DESC` — unlike PostgreSQL, which puts `NULL`s first on descending sorts.
- Change defaults with settings: `default_order` (`ASC` / `DESC`) and `default_null_order`, which accepts `NULLS_FIRST`, `NULLS_LAST`, `NULLS_FIRST_ON_ASC_LAST_ON_DESC` and `NULLS_LAST_ON_ASC_FIRST_ON_DESC`. For PostgreSQL behavior in both directions use:

```sql
SET default_null_order = 'NULLS_LAST_ON_ASC_FIRST_ON_DESC';
```

- `ORDER BY ALL` (optionally with `ASC`/`DESC` and `NULLS FIRST`/`LAST`) must be the only `ORDER BY` item.
- Without `ORDER BY`, result order is not guaranteed (see [order preservation](../dialect/introduction-and-compatibility.md)).

## `LIMIT`, `OFFSET` and `FETCH`

```sql
SELECT * FROM addresses LIMIT 5;
SELECT * FROM addresses LIMIT 5 OFFSET 5;             -- skip the first five
SELECT * FROM addresses LIMIT 10%;                    -- percentage of rows
SELECT city, count(*) AS population
FROM addresses
GROUP BY city
ORDER BY population DESC
LIMIT 5;
```

`LIMIT` without `ORDER BY` returns a nondeterministic subset.

**New in DuckDB 2.0:** the SQL-standard `FETCH` form. `FIRST`/`NEXT` and `ROW`/`ROWS` are interchangeable; omitting the count fetches one row:

```sql
SELECT * FROM addresses ORDER BY city FETCH FIRST 5 ROWS ONLY;
SELECT * FROM addresses ORDER BY city OFFSET 5 ROWS FETCH NEXT 5 ROWS ONLY;
SELECT * FROM addresses ORDER BY city FETCH FIRST ROW ONLY;
```

## `VALUES` lists

`VALUES` builds an inline relation; it can stand alone, appear in `FROM` (with column aliases), feed `INSERT`, or create a table:

```sql
VALUES ('Amsterdam', 1), ('London', 2);
SELECT * FROM (VALUES ('Amsterdam', 1), ('London', 2)) cities(name, id);
INSERT INTO cities VALUES ('Amsterdam', 1), ('London', 2);
CREATE TABLE cities AS SELECT * FROM (VALUES ('Amsterdam', 1), ('London', 2)) cities(name, id);
```

## Sampling

Samples return a random subset — handy for exploring large datasets.

```sql
SELECT * FROM addresses USING SAMPLE 1%;                     -- system sampling
SELECT * FROM addresses USING SAMPLE 1% (bernoulli);
SELECT * FROM (SELECT * FROM addresses) USING SAMPLE 10 ROWS; -- reservoir
SELECT * FROM tbl USING SAMPLE 5;                             -- 5 rows
SELECT * FROM tbl USING SAMPLE 10 PERCENT (bernoulli);
SELECT * FROM tbl USING SAMPLE reservoir(50 ROWS) REPEATABLE (100);
SELECT * FROM tbl USING SAMPLE 20% (system, 377);             -- method and seed
```

Size is a percentage (`10%`, `10 PERCENT`) or a row count (`10`, `10 ROWS`). The **default method** is `reservoir` for row counts and `system` for percentages. All methods support percentages; **only reservoir** supports a fixed row count.

| Method | How it works | Notes |
| --- | --- | --- |
| `reservoir` | Draws exactly the requested rows | Materializes the sample (and with percentages, the whole input) — avoid for large samples |
| `bernoulli` | Includes each row independently with the given probability | Percentages only; no multithreading penalty |
| `system` | Includes whole vectors (≈ 2048 rows) with the given probability | Fastest, but higher variance; for tables under ~10k rows prefer `bernoulli` (system may return no rows at all) |

A seed (`REPEATABLE (n)` or `(method, seed)`) makes the sample reproducible **only when running single-threaded** (`SET threads = 1`).

**Placement:** `USING SAMPLE` is written after `WHERE`/`GROUP BY` but is applied right after the `FROM` clause, i.e., before `WHERE` and aggregates. To sample one table **before** a join, use `TABLESAMPLE` on that table; `USING SAMPLE` on a join samples the join result:

```sql
SELECT * FROM tbl TABLESAMPLE reservoir(20%), tbl2
WHERE tbl.i = tbl2.i;                   -- sample tbl, then join

SELECT * FROM tbl, tbl2
WHERE tbl.i = tbl2.i
USING SAMPLE reservoir(20%);                 -- join, then sample
```

## Prepared statements

Prepared statements parse and plan a query once, then run it with different parameters — avoiding SQL injection from string concatenation and repeated planning. DuckDB supports three parameter styles:

| Style | Example | Notes |
| --- | --- | --- |
| Auto-incremented `?` | `WHERE starts_with(name, ?) AND age > ?` | Values bound by position; the only style JDBC supports |
| Positional `$1`, `$2`, … | `WHERE starts_with(name, $2) AND age > $1` | A parameter may be reused |
| Named `$name` | `WHERE starts_with(name, $name_start)` | Bound by name |

```sql
PREPARE query_person AS
    SELECT * FROM person WHERE starts_with(name, ?) AND age >= ?;
EXECUTE query_person('B', 40);

PREPARE query_person AS
    SELECT * FROM person WHERE starts_with(name, $name_start) AND age >= $minimum_age;
EXECUTE query_person(name_start := 'B', minimum_age := 40);

PREPARE add_values AS SELECT $1 + $2;
EXECUTE add_values(20, 22);
```

### Session variables as parameter defaults (new in DuckDB 2.0)

A named parameter that is not bound in `EXECUTE` takes the value of the session variable of the same name (set with `SET VARIABLE`). This applies to **named parameters only**; an explicit argument overrides the variable:

```sql
SET VARIABLE multiplier = 10;
SET VARIABLE x = 42;
PREPARE compute AS SELECT $multiplier * $x AS result;
EXECUTE compute;                      -- 420
EXECUTE compute(multiplier := 3);     -- 126
```

### Deallocating

```sql
DEALLOCATE query_person;
DEALLOCATE PREPARE add_values;        -- PREPARE keyword optional
```

Client APIs expose prepared statements natively (e.g., `con.execute(query, [params])` in Python — see [Python Getting Started](../../clients/python/getting-started.md)).
