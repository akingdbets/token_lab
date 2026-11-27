---
type: reference
title: CTEs, Recursive Queries, Set Operations, UNNEST and query()
description: The WITH clause in DuckDB — CTE materialization hints, data-modifying CTEs (new in 2.0), WITH RECURSIVE for sequences, trees and graph paths, the recurring prefix, USING KEY with aggregate payloads and UNION vs UNION ALL semantics (changed in 2.0); set operations UNION/INTERSECT/EXCEPT with ALL and BY NAME; unnest with recursive, max_depth and keep_parent_names; query() and query_table() for dynamic SQL; and SQL/PGQ graph queries with DuckPGQ.
tags: [sql, cte, with, recursive, using-key, union, set-operations, unnest, query-table, graph]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-2dc85f43c9a2d5af6009d59a
    resource: repo://docs/2.0/guides/sql_features/graph_queries.md
  - id: openwiki-source-939c180919543d5d0b0e1ee1
    resource: repo://docs/2.0/guides/sql_features/query_and_query_table_functions.md
  - id: openwiki-source-0168fdb5a414e7ff30a2ed31
    resource: repo://docs/2.0/sql/query_syntax/setops.md
  - id: openwiki-source-cc82ed538879f6b344eb4a64
    resource: repo://docs/2.0/sql/query_syntax/unnest.md
  - id: openwiki-source-f5413eafe3fca9473d0b4c6f
    resource: repo://docs/2.0/sql/query_syntax/with.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# CTEs, Recursive Queries, Set Operations, UNNEST and query()

Basic query clauses are on [SELECT, FROM, WHERE …](select-from-where.md); joins on [FROM Clause and Joins](joins.md).

## The `WITH` clause

Common table expressions (CTEs) are query-scoped views; they can reference earlier CTEs and be nested.

```sql
WITH cte AS (SELECT 42 AS x)
SELECT * FROM cte;

WITH
    cte1 AS (SELECT 42 AS i),
    cte2 AS (SELECT i * 100 AS x FROM cte1)
SELECT * FROM cte2;                    -- 4200

WITH cte(j) AS (SELECT 42 AS i)       -- column names for the CTE
FROM cte;
```

### Materialization

CTEs are **materialized by default** (evaluated once into a temporary result). DuckDB may **inline** a CTE when it is referenced at most once, has no `VOLATILE` function, uses `AS NOT MATERIALIZED` (and not `AS MATERIALIZED`), and performs no grouped aggregation — inlining is not always possible even then. Hints:

```sql
WITH t(x) AS MATERIALIZED (⟨complex_query⟩)
SELECT * FROM t AS t1, t AS t2, t AS t3;      -- complex_query evaluated once
WITH t(x) AS NOT MATERIALIZED (⟨complex_query⟩)
SELECT * FROM t AS t1, t AS t2, t AS t3;
```

Explicit hints are generally not recommended — the optimizer usually decides well.

### Data-modifying CTEs (new in DuckDB 2.0)

A CTE body may be `INSERT`, `UPDATE`, `DELETE` or `COPY`; use `RETURNING` when later parts read its rows, and mark it `MATERIALIZED` so it runs exactly once before dependents:

```sql
WITH moved AS MATERIALIZED (
    DELETE FROM staging
    RETURNING *
)
INSERT INTO archive
SELECT * FROM moved;

WITH updated AS (
    UPDATE orders SET status = 'shipped' WHERE status = 'ready'
    RETURNING *
)
SELECT count(*) AS shipped FROM updated;
```

## Recursive CTEs

`WITH RECURSIVE` lets a CTE refer to itself; the query must guarantee termination.

```sql
WITH RECURSIVE FibonacciNumbers (RecursionDepth, FibonacciNumber, NextNumber) AS (
    SELECT 0 AS RecursionDepth, 0 AS FibonacciNumber, 1 AS NextNumber      -- base case
    UNION ALL
    SELECT fib.RecursionDepth + 1, fib.NextNumber, fib.FibonacciNumber + fib.NextNumber
    FROM FibonacciNumbers fib
    WHERE fib.RecursionDepth + 1 < 10                                       -- recursive step
)
SELECT fn.RecursionDepth AS FibonacciNumberIndex, fn.FibonacciNumber FROM FibonacciNumbers fn;

-- tree traversal: path from 'Oasis' to the root
WITH RECURSIVE tag_hierarchy(id, source, path) AS (
    SELECT id, name, [name] AS path FROM tag WHERE subclassof IS NULL
    UNION ALL
    SELECT tag.id, tag.name, list_prepend(tag.name, tag_hierarchy.path)
    FROM tag, tag_hierarchy
    WHERE tag.subclassof = tag_hierarchy.id
)
SELECT path FROM tag_hierarchy WHERE source = 'Oasis';    -- [Oasis, Rock, Music, Art]
```

**Graph traversal:** cyclic graphs need cycle detection, e.g. store the path in a list and skip visited nodes with `WHERE list_position(paths.path, node2id) IS NULL` (all paths) or `WHERE NOT EXISTS (FROM paths previous_paths WHERE list_contains(previous_paths.path, node2id))` (unweighted shortest paths). To stop as soon as an end node is reached, track it with a window function such as `max(CASE WHEN node2id = 8 THEN 1 ELSE 0 END) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)`.

**`recurring` prefix:** inside the recursive term, the CTE name refers to the **last iteration's** rows; `recurring.⟨cte⟩` gives all rows accumulated so far:

```sql
WITH RECURSIVE counter(i) AS (
    SELECT 1
    UNION ALL
    SELECT i + 1 FROM counter WHERE (SELECT max(i) FROM recurring.counter) < 5
)
SELECT * FROM counter;    -- 1..5
```

Mutually recursive CTEs are not supported.

### `USING KEY`

`USING KEY (key columns)` turns the union table into a keyed dictionary: rows for an existing key **overwrite** its payload instead of appending, which keeps the union table small and makes iterative algorithms feasible.

```sql
WITH RECURSIVE tbl(a, b) USING KEY (a) AS (
    SELECT a, b FROM (VALUES (1, 3), (2, 4)) t(a, b)       -- or: VALUES (1, 3), (2, 4)
    UNION ALL
    SELECT a + 1, b FROM tbl WHERE a < 3
)
SELECT * FROM tbl;      -- (1, 3), (2, 3), (3, 3)
```

- Payload columns default to `last` semantics; an aggregate can be specified per payload column: `USING KEY (a, avg(b))`, `USING KEY (a, max(b))`.
- **`UNION` vs `UNION ALL` (changed in 2.0.0):** both apply all candidate rows to the union table, but `UNION ALL` forwards every candidate to the next iteration, while `UNION` forwards only rows whose key is new or whose payload changed — so recursion stops when the table stops changing. (1.5.0 had deprecated `UNION` here; the `deprecated_using_key_syntax` setting was removed.)
- The union table can be referenced with `recurring.⟨cte⟩` (e.g. connected components).

```sql
WITH RECURSIVE shortest_paths(node, dist) USING KEY (node, min(dist)) AS (
    SELECT 1, 0
    UNION
    SELECT e.dst, sp.dist + e.weight
    FROM shortest_paths AS sp
    JOIN weighted_edges AS e ON e.src = sp.node
)
SELECT * FROM shortest_paths ORDER BY node;   -- terminates despite the cycle
```

## Set operations

Traditional set operations combine queries **by position** (same number of columns, implicit casts as needed; names from the first query).

| Operation | Semantics |
| --- | --- |
| `UNION` | Rows from both, duplicates removed |
| `UNION ALL` | Rows from both, duplicates kept |
| `INTERSECT` / `INTERSECT ALL` | Rows in both (set / bag) |
| `EXCEPT` / `EXCEPT ALL` | Rows only in the left query (set / bag) |
| `UNION BY NAME` / `UNION ALL BY NAME` | Combine **by column name**; missing columns filled with `NULL` |

```sql
SELECT * FROM range(2) t1(x) UNION ALL SELECT * FROM range(3) t2(x);
SELECT unnest([5, 5, 6, 6, 6, 6, 7, 8]) AS x INTERSECT ALL SELECT unnest([5, 6, 6, 7, 7, 9]);
SELECT * FROM capitals UNION BY NAME SELECT * FROM weather;
```

`UNION` does not guarantee row order; `UNION ALL` preserves it.

## `UNNEST`

`unnest` decomposes composite values: a `LIST` becomes rows, a `STRUCT` becomes columns (also `struct.*`), a `TUPLE` becomes columns named `element1`, `element2`, ….

```sql
SELECT unnest([1, 2, 3]), 10;                       -- (1, 10), (2, 10), (3, 10)
SELECT unnest([1, 2, 3]), unnest([10, 11]);         -- (1, 10), (2, 11), (3, NULL)
SELECT unnest(l) + 10 FROM (VALUES ([1, 2, 3]), ([4, 5])) tbl(l);
SELECT unnest({'a': 42, 'b': 84});                  -- columns a, b
SELECT unnest(l) AS x, generate_subscripts(l, 1) AS index FROM (VALUES ([1, 2, 3]), ([4, 5])) tbl(l);
```

- Usable in `SELECT` (and, **since DuckDB 2.0, in `GROUP BY`**) but not in `WHERE` or `ORDER BY`. For lists it also works as a table function in `FROM` or `CALL` (without extra parameters).
- Multiple `unnest`s in one `SELECT` align by position and pad shorter ones with `NULL`; empty and `NULL` lists produce **zero rows**.
- Recursive parameters: `recursive` (default `false`), `max_depth` (default `1`; values > 1 imply recursion), `keep_parent_names` (default `false`, structs only). Recursion follows the outermost type: lists unnest nested lists, structs unnest nested structs.

```sql
SELECT unnest([[1, 2, 3], [4, 5]], recursive := true);                                 -- 5 rows
SELECT unnest([{'a': 42, 'b': 84}, {'a': 100, 'b': NULL}], recursive := true);         -- columns a, b
SELECT unnest([[[1, 2], [3, 4]], [[5, 6], [7, 8, 9], []], [[10, 11]]], max_depth := 2) AS x;
SELECT unnest([{'a': 0, 'b': {'bb': {'bbb': 1}}}], recursive := true, keep_parent_names := true);
```

## Dynamic SQL: `query` and `query_table`

`query_table(name)` returns the named table (or the union of several, optionally `by_name`); `query(sql)` runs a query string. Both accept **constant strings only**, e.g. as prepared-statement parameters or inside table macros:

```sql
PREPARE select_from_table AS SELECT * FROM query_table($1);
EXECUTE select_from_table('my_table');

CREATE OR REPLACE MACRO my_summarize(table_name) AS TABLE
SELECT
    unnest([*COLUMNS('alias_.*')]) AS column_name,
    unnest([*COLUMNS('min_.*')]) AS min_value,
    unnest([*COLUMNS('max_.*')]) AS max_value
FROM (
    SELECT
        any_value(alias(COLUMNS(*))) AS "alias_\0",
        min(COLUMNS(*))::VARCHAR AS "min_\0",
        max(COLUMNS(*))::VARCHAR AS "max_\0"
    FROM query_table(table_name::VARCHAR)
);
SELECT * FROM my_summarize('https://blobs.duckdb.org/data/ontime.parquet') LIMIT 3;

CREATE OR REPLACE MACRO stack(table_name, index, name, values) AS TABLE
FROM query(
    'UNPIVOT ' || table_name
    || ' ON COLUMNS(* EXCLUDE (' || array_to_string(index, ', ')
    || ')) INTO NAME ' || name || ' VALUES ' || values
);
```

`query` can run arbitrary SQL, so never feed it untrusted input (see [Securing DuckDB](../../operations/security.md)).

## Graph queries with DuckPGQ

The `duckpgq` community extension (under active development; not available for every version) implements SQL/PGQ from SQL:2023. **Since DuckDB 2.0**, syntax-extending extensions plug into the PEG grammar and must be enabled explicitly:

```sql
INSTALL duckpgq FROM community;
LOAD duckpgq;
SET active_grammar_extensions = ['duckpgq'];

CREATE PROPERTY GRAPH social_network
VERTEX TABLES (Person)
EDGE TABLES (
    Knows SOURCE KEY (person1_id) REFERENCES Person (id)
          DESTINATION KEY (person2_id) REFERENCES Person (id)
);

FROM GRAPH_TABLE (social_network
    MATCH p = ANY SHORTEST (a:Person)-[k:Knows]->{1,3}(b:Person)
    WHERE a.name = 'Alice' AND b.name = 'Charlie'
    COLUMNS (a.name AS start_person, b.name AS end_person, path_length(p) AS hops)
);
FROM pagerank('social_network', 'Person', 'Knows');
```

Algorithms: `pagerank`, `local_clustering_coefficient`, `weakly_connected_component`.
