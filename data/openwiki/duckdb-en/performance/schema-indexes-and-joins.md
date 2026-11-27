---
type: guide
title: Schema Design, Indexes and Join Performance
description: How schema choices affect DuckDB performance — proper types vs. VARCHAR, dimension tables, why constraints slow loading, automatic zonemaps and the value of ordered data, ART indexes (CREATE INDEX, index scans, memory, UPDATE/foreign-key limitations), and controlling join order (disabled_optimizers, temporary tables, approximate_join_order_threshold).
tags: [performance, schema, indexes, art-index, zonemaps, create-index, joins, constraints]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-dae144da404490537e665974
    resource: repo://docs/2.0/guides/performance/indexing.md
  - id: openwiki-source-3667a2513650e9d19a6724d4
    resource: repo://docs/2.0/guides/performance/join_operations.md
  - id: openwiki-source-d98c5e684690d8443a4c46d4
    resource: repo://docs/2.0/guides/performance/schema.md
  - id: openwiki-source-e9d4ddb020ffd87c0ed7f23d
    resource: repo://docs/2.0/sql/indexes.md
  - id: openwiki-source-32e57632f974a23e827063d2
    resource: repo://docs/2.0/sql/statements/create_index.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Schema Design, Indexes and Join Performance

Good schema choices often matter more than indexes in DuckDB. This page covers types and constraints, DuckDB's two index types, and join-order control. Table DDL is described in [CREATE TABLE, Constraints, ALTER TABLE](../sql/statements/create-and-alter-tables.md); general tuning in [Performance Tuning](tuning-workloads.md).

## Use the right types

Encode values with their proper types (`BIGINT`, `DATE`, `DATETIME`, …) rather than strings — strings use more space and are slower for filtering, joins and aggregation. CSV auto-detection usually picks good types. In memory-constrained setups use the smallest adequate type (e.g. `TINYINT`): bitpacking keeps small values small on disk, but larger types still cost memory during processing.

Microbenchmark on ~554 million timestamps (LDBC SF300):

| Column type | Storage | Query time |
| --- | ---: | ---: |
| `DATETIME` (`avg(extract('day' FROM creationDate))`) | 3.3 GiB | 0.19 s |
| `VARCHAR` (`avg(CAST(creationDate[9:10] AS INTEGER))`) | 5.3 GiB | 1.85 s |

Self-join on identifiers (LDBC SF100):

| Payload | Schema type | Query time |
| --- | --- | ---: |
| `BIGINT` | `BIGINT` | 0.92 s |
| `BIGINT` | `VARCHAR` | 0.97 s |
| `UUID` | `UUID` | 0.71 s |
| `UUID` | `VARCHAR` | 1.38 s |

> **Best practice:** avoid representing numeric values as strings, especially for join keys (`UUID` vs `VARCHAR`: ~1.9× faster).

### Dimension tables for repeated strings

Replace a wide, low-cardinality string column with an integer key into a dimension table (a star schema), aggregate on the key, and join strings back at the end. For a fixed set of values, `ENUM` does this automatically. DuckDB already dictionary-encodes strings in storage, so this mostly pays off for query-heavy workloads.

```sql
CREATE OR REPLACE TABLE dim_table AS
    SELECT field_name, (row_number() OVER (ORDER BY field_name))::INTEGER AS field_pk
    FROM (SELECT DISTINCT field_name FROM fact_table);

WITH rollup AS (
    SELECT field_pk, count(*) AS count
    FROM fact_table NATURAL JOIN dim_table
    GROUP BY ALL
)
SELECT rollup.* EXCLUDE (field_pk), field_name
FROM rollup NATURAL JOIN dim_table;
```

## Constraints cost load time

`UNIQUE`, `PRIMARY KEY` and `FOREIGN KEY` build indexes and run checks, slowing loads, and **very rarely speed up queries** — DuckDB does not use these indexes for joins or aggregations.

| Operation (554M rows from `.csv.gz`) | Time |
| --- | ---: |
| Load with primary key | 159.3 s |
| Load without primary key | 45.0 s |
| Load without, then add primary key | 77.5 s |

> **Best practice:** define constraints only for data integrity; if required, add them **after** bulk loading.

## Zonemaps (min-max indexes)

Zonemaps are created **automatically** for all general-purpose data types and used for predicate pushdown and aggregations: a row group whose min–max range excludes the filter value (e.g. range 1000–2000 for `= 123`) is skipped.

- **Ordering makes zonemaps effective.** Random values defeat skipping; pre-sort data on selectively filtered columns at insert time (even imperfect order helps). Ordered `DATETIME` columns are the common best case: an ordered timestamp column stored in 1.3 GiB vs 3.3 GiB unordered (2.5× smaller) and ran ~10% faster even for a full scan; selective filters gain more.
- Prefer auto-incrementing `INTEGER` keys over random `UUID`s for columns used in selective filters.

## ART indexes

Adaptive Radix Tree indexes are created implicitly for `PRIMARY KEY`, `FOREIGN KEY` and `UNIQUE` constraints, or explicitly with `CREATE INDEX`. They enforce constraints and speed up point lookups and very selective queries (< 0.1% of rows), but slow down inserts, updates and deletes and **do not help joins, aggregations or sorting**. Spatial R-tree indexes are available via the `spatial` extension. Zonemaps and ART indexes are both persisted.

```sql
CREATE UNIQUE INDEX films_id_idx ON films (id);
CREATE INDEX s_idx ON films (revenue);
CREATE INDEX IF NOT EXISTS s_idx ON films (revenue);   -- no early exit: builds, then checks
CREATE INDEX gy_idx ON films (genre, year);
CREATE INDEX i_index ON integers ((j + k));            -- expression index
DROP INDEX title_idx;
```

`CREATE INDEX` does not support `OR REPLACE`. Optional index type and options (`is_cool`, `my_option = 2`) can be given.

### Index scans

DuckDB uses an index scan for equality and `IN (...)` conditions, and for dynamic filters pushed from hash joins — but only on **single-column indexes without expressions** (`idx_multi_column` and `idx_expr` above are not eligible). The threshold is `MAX(2048, 0.001 * table_cardinality)`, configurable via `index_scan_percentage` and `index_scan_max_count` (zero disables). Verify with `EXPLAIN ANALYZE`.

### Memory and opening databases

- ART indexes must **fit in memory during creation**.
- Index memory is registered with the buffer manager but **not buffer-managed** (not evicted), so indexes can crowd out memory-intensive queries. `DETACH` + `ATTACH` helps because indexes are deserialized lazily; disabling index scans helps further.
- Lazy deserialization means indexes do not slow down opening a database.

> **Best practice:** use keys/unique constraints only to enforce constraints; create explicit indexes only for highly selective queries with enough memory; create ART indexes **after** bulk loading.

### Limitations when modifying indexed data

`UPDATE`s on indexed columns (and columns that cannot be updated in place) are rewritten as `DELETE` + `INSERT` per 2048-row chunk — costly for wide tables, and it causes spurious violations:

```sql
CREATE TABLE my_table (i INTEGER PRIMARY KEY);
INSERT INTO my_table SELECT range FROM range(3_000);
UPDATE my_table SET i = i + 1;   -- Constraint Error: Duplicate key "i: 2048" violates primary key constraint.
```

Workaround: in a transaction, copy rows to a temp table, `DELETE`, and re-`INSERT` (or use `DELETE ... RETURNING` and the Appender). Similarly, updating a composite (`LIST`/`STRUCT`) payload column of a primary-key table referenced by a foreign key raises `Violates foreign key constraint ...` because DuckDB cannot look ahead during the rewrite.

## Join performance and join order

DuckDB's cost-based optimizer estimates cardinalities from table statistics (DuckDB tables or Parquet). To force a join order:

```sql
SET disabled_optimizers = 'join_order,build_side_probe_side';   -- left-deep tree in JOIN clause order
SELECT ... FROM ... JOIN ... /* first */ JOIN ... /* second */;
SET disabled_optimizers = '';
```

Or materialize steps with `CREATE OR REPLACE TEMPORARY TABLE t1 AS ...;` and drop them afterwards.

The optimizer enumerates join orders exactly (dynamic programming) below `approximate_join_order_threshold` tables (**default 12**) and greedily at or above it; it also falls back to the approximate algorithm when exact enumeration exceeds its budget. Raising the threshold can find better orders at higher optimization cost:

```sql
SET approximate_join_order_threshold = 16;   -- exact for joins of up to 15 tables
```

If joins over Parquet get poor orders, loading the data into DuckDB (which has HyperLogLog statistics) can help — see [File Formats, Bulk Import, Huge Databases](file-formats-and-large-data.md). Join syntax is on [FROM Clause and Joins](../sql/query-syntax/joins.md).
