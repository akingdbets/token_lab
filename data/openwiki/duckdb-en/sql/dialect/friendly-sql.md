---
type: reference
title: Friendly SQL
description: DuckDB's "friendly SQL" conveniences — FROM-first queries, GROUP BY ALL / ORDER BY ALL, star expressions with EXCLUDE (and EXCEPT, new in 2.0), REPLACE, RENAME and pattern filters, the COLUMNS() expression with regexes, lambdas, lists and UNPACK, prefix and reusable aliases, trailing commas, top-N aggregates, 1-based indexing, and a map of other friendly features.
tags: [sql, friendly-sql, columns, star-expression, exclude, group-by-all, from-first, indexing]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-392c46f068eb35a2c984ffdc
    resource: repo://docs/2.0/sql/dialect/friendly_sql.md
  - id: openwiki-source-16ed68e059a276931df24353
    resource: repo://docs/2.0/sql/dialect/indexing.md
  - id: openwiki-source-9de2487450d9ae29c79ed700
    resource: repo://docs/2.0/sql/expressions/star.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Friendly SQL

DuckDB adds syntactic sugar that makes SQL more concise; several features originated in DuckDB (e.g. `GROUP BY ALL`) and were later adopted elsewhere. Standard dialect behavior is described in [SQL Introduction, Dialect and PostgreSQL Compatibility](introduction-and-compatibility.md).

## Feature map

| Area | Features (where to read more) |
| --- | --- |
| Tables & inserts | `CREATE OR REPLACE TABLE`, `CREATE TABLE ... AS SELECT`, `INSERT INTO ... BY NAME`, `INSERT OR IGNORE`, `INSERT OR REPLACE` ([CREATE TABLE](../statements/create-and-alter-tables.md), [INSERT](../statements/modifying-data.md)) |
| Inspection | `DESCRIBE`, `SUMMARIZE`, `SHOW ⟨setting⟩` (e.g. `SHOW threads`) ([DESCRIBE, SHOW, SUMMARIZE](../statements/inspection-and-metadata.md)) |
| Compact clauses | `FROM`-first with optional `SELECT`, `GROUP BY ALL`, `ORDER BY ALL`, `SELECT * EXCLUDE/REPLACE`, `UNION BY NAME`, prefix aliases `x: 42`, `LIMIT 10%`, `FETCH FIRST 5 ROWS ONLY`, `GROUP BY unnest(...)` ([SELECT](../query-syntax/select-from-where.md), [GROUP BY](../query-syntax/grouping-and-filtering.md)) |
| Transformations | `PIVOT`, `UNPIVOT` ([PIVOT and UNPIVOT](../statements/pivot-and-unpivot.md)) |
| Variables | `SET VARIABLE`, `RESET VARIABLE`, `$name` shorthand ([Configuration](../../configuration/settings-and-pragmas.md)) |
| Catalog & extensions | Nested schemas (`CREATE SCHEMA finance.reports`), `INSTALL AND LOAD` |
| Query features | Column aliases in `WHERE`/`GROUP BY`/`HAVING` (not in `JOIN ... ON`), reusable (lateral) aliases, `FILTER`, `GROUPING SETS`/`CUBE`/`ROLLUP`, `count()` for `count(*)`, `IN` on lists and maps, CTE column names, data-modifying CTEs, `VALUES` in joins and CTE anchors, `SWITCH` as `CASE` sugar |
| Literals & identifiers | Case-insensitive identifiers that preserve catalog case, deduplicated identifiers, `_` digit separators |
| Data import | CSV auto-detection, `FROM 'my.csv'` / `'my.parquet'` replacement scans, `FROM df` in Python, globbing `FROM 'my-data/part-*.parquet'` |
| Functions | Dot chaining `('hello').upper()`, `format()` / `printf()`, list comprehensions, list/string slicing and `[-1]`, `STRUCT.*`, `[...]` lists, simple struct creation, struct schema updates |
| Joins | `ASOF`, `LATERAL`, `POSITIONAL`, `NEAREST` (top-k similarity, e.g. embeddings) ([Joins](../query-syntax/joins.md)) |
| Types | `MAP`, `UNION` |

Lateral column alias example: `SELECT i + 1 AS j, j + 2 AS k FROM range(0, 3) t(i)`.

## Trailing commas

Allowed in lists of entities (columns, tables) and in `LIST` literals:

```sql
SELECT
    42 AS x,
    ['a', 'b', 'c',] AS y,
    'hello world' AS z,
;
```

## Top-N in group

Instead of window functions in a subquery, use `max(arg, n)`, `min(arg, n)`, `arg_max(arg, val, n)`, `arg_min(arg, val, n)`, `max_by(arg, val, n)`, `min_by(arg, val, n)`:

```sql
-- conventional
SELECT array_agg(rs.val), rs.grp
FROM (SELECT val, grp, row_number() OVER (PARTITION BY grp ORDER BY val DESC) AS rid
      FROM t1 ORDER BY val DESC) AS rs
WHERE rid < 4
GROUP BY rs.grp;
-- DuckDB: more concise and more efficient
SELECT max(val, 3) FROM t1 GROUP BY grp;
```

## Star expressions

```sql
SELECT * FROM tbl;
SELECT tbl.* FROM tbl JOIN other_tbl USING (id);              -- one table's columns
SELECT st.* FROM (SELECT {'x': 1, 'y': 2, 'z': 3} AS st);     -- struct keys as columns
SELECT * EXCLUDE (col) FROM tbl;
SELECT * EXCEPT (col) FROM tbl;                                -- synonym, new in 2.0
SELECT * REPLACE (col1 / 1_000 AS col1, col2 / 1_000 AS col2) FROM tbl;
SELECT * RENAME (col1 AS height, col2 AS width) FROM tbl;
SELECT * LIKE 'col%' FROM tbl;
SELECT * GLOB 'col*' FROM tbl;
SELECT * SIMILAR TO 'col.' FROM tbl;
SELECT * NOT SIMILAR TO 'col.' FROM tbl;
```

**New in DuckDB 2.0:** `EXCEPT` is accepted as a synonym of `EXCLUDE` (SQL-standard/BigQuery spelling); both may be mixed.

## The `COLUMNS` expression

`COLUMNS(...)` selects columns like `*` but lets you apply an expression to each:

```sql
CREATE TABLE numbers (id INTEGER, number INTEGER);
INSERT INTO numbers VALUES (1, 10), (2, 20), (3, NULL);

SELECT min(COLUMNS(*)), count(COLUMNS(*)) FROM numbers;
SELECT min(COLUMNS(* REPLACE (number + id AS number))), count(COLUMNS(* EXCLUDE (number))) FROM numbers;
SELECT COLUMNS(*) + COLUMNS(*) FROM numbers;                  -- combinable if same star expression
SELECT COLUMNS('(id|numbers?)') FROM numbers;                -- regular expression
SELECT COLUMNS('(\w{3}).*') AS '\1' FROM numbers;             -- rename via capture groups (\0 = original)
SELECT min(COLUMNS(*)) AS "min_\0" FROM numbers;              -- min_id, min_number
SELECT COLUMNS(lambda c: c LIKE '%num%') FROM numbers;        -- lambda over names (optional 2nd arg: 1-based index)
SELECT COLUMNS(['id', 'number']) FROM numbers;                -- explicit list
SELECT COLUMNS(lambda c: c != getvariable('column_to_exclude')) FROM tbl;
```

- In `WHERE`, conditions apply to all matched columns combined with `AND`: `WHERE COLUMNS(*) = 'a'` ≡ `x = 'a' AND y = 'a'`. For `OR`, unpack into `greatest`: `WHERE greatest(UNPACK(COLUMNS(*) = 'a'))`.
- In `DISTINCT ON`: `SELECT DISTINCT ON (COLUMNS('x|y')) * FROM ...`.
- `COLUMNS` does not support pattern-matching operators — use a regex string instead.

### `UNPACK`

Without `UNPACK`, operations apply per column; with it, the columns expand into the parent call (like Python's `*`):

```sql
SELECT coalesce(COLUMNS(['a', 'b', 'c'])) AS result FROM (SELECT NULL a, 42 b, true c);          -- 3 columns
SELECT coalesce(UNPACK(COLUMNS(['a', 'b', 'c']))) AS result FROM (SELECT NULL AS a, 42 AS b, true AS c);   -- 42
SELECT coalesce(*COLUMNS(*)) AS result FROM (SELECT NULL a, 42 AS b, true AS c);                 -- * shorthand
SELECT greatest(UNPACK(COLUMNS(*) + 1)) AS result FROM (SELECT 1 AS a, 2 AS b, 3 AS c);          -- 4
```

`*` can replace `UNPACK` only when applied directly to `COLUMNS` with no intermediate operation (`greatest(*COLUMNS(*) + 1)` is a syntax error).

## Indexing

DuckDB uses **1-based indexing** for strings, lists and arrays, but **0-based** for JSON:

```sql
SELECT list[1] AS element FROM (SELECT ['first', 'second', 'third'] AS list);            -- first
SELECT json[1] AS element FROM (SELECT '["first", "second", "third"]'::JSON AS json);    -- "second"
```

See [List, Array and Lambda Functions](../functions/list-array-and-lambda.md) for slicing and list comprehensions, and [The JSON Type and JSON Functions](../../data/json/json-type-and-functions.md) for JSON paths.
