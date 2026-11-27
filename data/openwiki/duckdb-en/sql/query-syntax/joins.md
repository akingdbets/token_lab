---
type: "Reference"
title: "FROM Clause and Joins (including ASOF and LATERAL)"
openwiki_generated: true
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-0d309995187ea09571947156
    resource: repo://docs/2.0/guides/sql_features/asof_join.md
  - id: openwiki-source-6fd29452c3332e8a59b27f33
    resource: repo://docs/2.0/sql/query_syntax/from.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---


# FROM Clause and Joins (including ASOF and LATERAL)

The `FROM` clause specifies the data source; logically, query execution starts here. Join performance tips are on [Schema Design, Indexes and Join Performance](../../performance/schema-indexes-and-joins.md); other clauses on [SELECT, FROM, WHERE …](select-from-where.md).

## Data sources

```sql
SELECT * FROM tbl;
FROM tbl SELECT *;                                  -- FROM-first
FROM tbl;                                           -- SELECT * implied
SELECT tn.* FROM tbl tn;
SELECT tn.* FROM tn: tbl;                           -- prefix alias
SELECT * FROM schema_name.tbl;
SELECT t.i FROM range(100) AS t(i);                 -- table function with column alias
SELECT * FROM 'test.csv';                           -- = read_csv('test.csv')
SELECT * FROM (SELECT * FROM tbl);                  -- subquery
SELECT t FROM t;                                    -- whole row as a STRUCT
SELECT * FROM tbl TABLESAMPLE 10%;                  -- sampling (see SELECT page)
FROM range(100) AS t(i) SELECT sum(t.i) WHERE i % 2 = 0;
```

**Table functions** (`read_csv`, `read_parquet`, `range`, `generate_series`, `repeat`, `unnest`, `glob`, …) are used like tables. Any table function accepts `WITH ORDINALITY`, adding an `ordinality` column numbered from 1 — useful to enumerate one side of a join without a subquery:

```sql
SELECT * FROM read_csv('test.csv') WITH ORDINALITY;
```

## Join types

A join combines left and right relations; each result row has columns from both.

| Join | Meaning |
| --- | --- |
| `[INNER] JOIN ... ON / USING` | Only matched pairs |
| `LEFT` / `RIGHT` / `FULL [OUTER] JOIN` | Unmatched left / right / both rows kept with `NULL`s |
| `CROSS JOIN` (or `FROM a, b`) | All pairs |
| `NATURAL JOIN` | Join on all same-named columns |
| `SEMI JOIN` | Left rows with ≥ 1 match (like `IN`) |
| `ANTI JOIN` | Left rows with no match (like `NOT IN`, but ignores right-side `NULL`s) |
| `LATERAL` | Subquery referencing earlier `FROM` items |
| `POSITIONAL JOIN` | Pair rows by position |
| `ASOF [LEFT] JOIN` | Nearest preceding/following match on an ordering column |
| `... [APPROX] NEAREST k BY SIMILARITY/DISTANCE expr` | Top-k similarity join (new in 2.0) |

```sql
SELECT n.*, r.* FROM l_nations n JOIN l_regions r ON (n_regionkey = r_regionkey);
SELECT n.*, r.* FROM l_nations n JOIN l_regions r USING (regionkey);
SELECT s1.t_id, s2.t_id FROM west s1, west s2 WHERE s1.time > s2.time AND s1.cost < s2.cost;   -- any predicate
SELECT * FROM city_airport NATURAL JOIN airport_names;      -- = JOIN airport_names USING (iata)
```

Semi and anti joins never return more rows than the left side:

```sql
SELECT * FROM city_airport SEMI JOIN airport_names USING (iata);
-- = WHERE iata IN (SELECT iata FROM airport_names)
SELECT * FROM city_airport ANTI JOIN airport_names USING (iata);
-- = WHERE iata NOT IN (SELECT iata FROM airport_names WHERE iata IS NOT NULL)
```

## `LATERAL` joins

Subqueries in `FROM` may refer to earlier items — a generalization of correlated subqueries that can return several rows per input row (think "for each row of `t`, run the subquery"). DuckDB detects lateral references automatically, so the keyword is optional.

```sql
SELECT * FROM range(3) t(i), LATERAL (SELECT i + 1) t2(j);
SELECT * FROM generate_series(0, 1) t(i), LATERAL (SELECT i + 10 UNION ALL SELECT i + 100) t2(j);
```

Table functions such as `json_each` act as lateral joins.

## `POSITIONAL JOIN`

Pairs rows by physical position — useful for data frames and files with a natural order. It is always a **full outer** join: the result has the length of the longer input, padded with `NULL`s.

```sql
CREATE TABLE t1 (x INTEGER);
CREATE TABLE t2 (s VARCHAR);
INSERT INTO t1 VALUES (1), (2), (3);
INSERT INTO t2 VALUES ('a'), ('b');
SELECT * FROM t1 POSITIONAL JOIN t2;   -- (1, a), (2, b), (3, NULL)
```

## `ASOF` joins

An as-of join finds, for each left row, the nearest matching right row on an ordered column — "the value of the property **as of** this time". It needs **at least one inequality** (`>=`, `>`, `<=`, `<`, on any type; usually `>=` on time); other conditions must be equalities (or `NOT DISTINCT`), so table order matters. Each left row matches **at most one** right row.

```sql
CREATE TABLE prices AS FROM 'https://duckdb.org/data/prices.csv';
CREATE TABLE holdings AS FROM 'https://duckdb.org/data/holdings.csv';

SELECT h.ticker, h.when, price * shares AS value
FROM holdings h
ASOF JOIN prices p
    ON h.ticker = p.ticker
    AND h.when >= p.when;
```

- The inner form drops left rows without a match (missing ticker or time before the first price); `ASOF LEFT JOIN` keeps them with `NULL`s — the left side never grows.
- With `USING`, the **last** column is the inequality and it is always `>=`: `ASOF JOIN prices p USING (ticker, "when")`. `SELECT *` then returns the merged `ticker` and `when` from the **left** table; list columns explicitly to see the matched price time:

```sql
SELECT h.ticker, h.when AS holdings_when, p.when AS prices_when, h.shares, p.price
FROM holdings h
ASOF JOIN prices p USING (ticker, "when");
```

## `NEAREST` joins (new in DuckDB 2.0)

Match each left row with the top-k right rows by a measure: `NEAREST k BY SIMILARITY expr` (higher is closer) or `NEAREST k BY DISTANCE expr` (lower is closer); `APPROX` uses an approximate search that can be faster on large inputs. Combinable with regular join types:

```sql
SELECT q.user_id, t.product_id
FROM users q
    INNER JOIN products t APPROX NEAREST 2
    BY SIMILARITY array_cosine_similarity(q.embedding, t.embedding);

SELECT q.user_id, t.product_id
FROM users q
    LEFT JOIN products t NEAREST 1
    BY DISTANCE array_distance(q.embedding, t.embedding);
```

## Self-joins and shorthands

Self-joins need aliases; otherwise: `Binder Error: Ambiguous reference to table "memory.main.t" (duplicate alias ...)`.

```sql
SELECT * FROM t AS t1 JOIN t AS t2 USING(x);
SELECT * FROM t1 NATURAL JOIN t2 t2(x);                  -- rename columns in the JOIN clause
SELECT * FROM t1 NATURAL JOIN (VALUES (2), (4)) _(x);    -- VALUES as a join input
```

## Explicit join types: `JOIN BY (TYPE ...)` (new in DuckDB 2.0)

Selects a join type directly, including internal ones without standard syntax (case-insensitive, optional `_join` suffix):

```sql
SELECT ... FROM ⟨left_table⟩ JOIN BY (TYPE ⟨join_type⟩) ⟨right_table⟩ ON ⟨condition⟩;
```

| Type | Meaning |
| --- | --- |
| `inner`, `left`, `right`, `full` | Standard joins |
| `semi`, `anti` | Left rows with / without a match |
| `right_semi`, `right_anti` | Right rows with / without a match |
| `mark` | All left rows plus `BOOLEAN` `__mark_join_marker` with `IN`-style three-valued logic |
| `single` | Left rows with their single match or `NULL`; errors on multiple matches (like a scalar subquery) |

```sql
SELECT a, __mark_join_marker
FROM t1
JOIN BY (TYPE mark) t2 ON (a = b)
ORDER BY a NULLS LAST;
```

Joins do not preserve row order (see [order preservation](../dialect/introduction-and-compatibility.md)). In Python, `rel.join(other, condition, how=...)` exposes the same join types (see [Python Relational API](../../clients/python/relational-api.md)).
