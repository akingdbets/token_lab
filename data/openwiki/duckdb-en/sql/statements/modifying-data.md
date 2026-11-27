---
type: reference
title: INSERT, UPDATE, DELETE, MERGE INTO and the Appender
description: Modifying data in DuckDB — INSERT with VALUES or queries, BY POSITION / BY NAME, ON CONFLICT DO NOTHING / DO UPDATE (upsert) with EXCLUDED and conflict targets, INSERT OR IGNORE / OR REPLACE, RETURNING; UPDATE with FROM and joins; DELETE, USING and TRUNCATE; MERGE INTO with WHEN MATCHED / NOT MATCHED [BY SOURCE|TARGET] and merge_action, including an SCD Type 2 pattern; and bulk loading with the Appender.
tags: [sql, dml, insert, upsert, on-conflict, update, delete, merge-into, appender, bulk-loading]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-b0a2d3e4134cca4fd1f1c265
    resource: repo://docs/2.0/data/appender.md
  - id: openwiki-source-62acec76e1cc6ed9fdd236bf
    resource: repo://docs/2.0/data/insert.md
  - id: openwiki-source-8fae0d11c882030cbfaf8922
    resource: repo://docs/2.0/sql/statements/delete.md
  - id: openwiki-source-83b796cdc7bc49fc5d2942bd
    resource: repo://docs/2.0/sql/statements/insert.md
  - id: openwiki-source-e2029552ceed9a52e20b486c
    resource: repo://docs/2.0/sql/statements/merge_into.md
  - id: openwiki-source-33b4860a8bab76cc5f75b9b8
    resource: repo://docs/2.0/sql/statements/update.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# INSERT, UPDATE, DELETE, MERGE INTO and the Appender

Constraints that drive conflicts are on [CREATE TABLE, Constraints, ALTER TABLE …](create-and-alter-tables.md); index and constraint costs on [Schema Design, Indexes and Join Performance](../../performance/schema-indexes-and-joins.md). Data-modifying statements can also be used inside CTEs (see [CTEs](../query-syntax/ctes-set-operations-unnest.md)).

## `INSERT`

```sql
INSERT INTO tbl VALUES (1), (2), (3);
INSERT INTO tbl SELECT * FROM other_tbl;
INSERT INTO tbl (i) VALUES (1), (2), (3);            -- other columns get defaults
INSERT INTO tbl (i) VALUES (1), (DEFAULT), (3);      -- explicit default
```

Columns not in the (explicit or implicit) column list get their declared default or `NULL`; values of the wrong type are converted automatically where possible.

### Column order: `BY POSITION` and `BY NAME`

`BY POSITION` (the default) maps values left-to-right onto the table's declared column order or the given column list. `BY NAME` matches the `SELECT`'s column names against the table's — names must exist in the table (else an error), and missing columns get their default:

```sql
CREATE TABLE tbl (a INTEGER, b INTEGER);
INSERT INTO tbl (b, a) VALUES (5, 42);               -- = INSERT INTO tbl BY POSITION (b, a) VALUES (5, 42)
INSERT INTO tbl BY NAME (SELECT 42 AS b, 32 AS a);
INSERT INTO tbl BY NAME (SELECT 22 AS b);            -- a = NULL
```

### `ON CONFLICT` (upsert)

Without handling, a duplicate key raises `Duplicate key "i: 1" violates primary key constraint.` and the earlier row stays. Two clauses handle `PRIMARY KEY` / `UNIQUE` conflicts:

```sql
CREATE TABLE tbl (i INTEGER PRIMARY KEY, j INTEGER);
INSERT INTO tbl VALUES (1, 42);

INSERT INTO tbl VALUES (1, 84) ON CONFLICT DO NOTHING;              -- keeps (1, 42)
INSERT OR IGNORE INTO tbl VALUES (1, 84);                           -- same

INSERT INTO tbl VALUES (1, 84) ON CONFLICT DO UPDATE SET j = EXCLUDED.j;
INSERT OR REPLACE INTO tbl VALUES (1, 84);                          -- updates every column
INSERT INTO tbl BY NAME (SELECT 1 AS i, 336 AS j) ON CONFLICT DO UPDATE SET j = EXCLUDED.j;
```

- In `SET` and `WHERE` of `DO UPDATE`, the `EXCLUDED` qualifier refers to the **to-be-inserted** row; unqualified names refer to the **existing** row.
- `INSERT OR REPLACE` is shorthand for `DO UPDATE SET c1 = EXCLUDED.c1, c2 = EXCLUDED.c2, ...`. With a composite key, declare one `PRIMARY KEY (id1, id2)`.
- If one `INSERT` contains several rows with the same conflicting key, **only one update per key** is applied and the winner is not guaranteed to be the last row (in `VALUES (1, 52), (1, 62)`, `j` ends up `52`). Deduplicate the input first (e.g., with a window function) for last-writer-wins.

**Conflict target:** `ON CONFLICT (cols)` names the columns of a unique/key constraint; if omitted, the primary key is targeted. It is required for `DO UPDATE` when the table has several unique/primary key constraints. An optional `WHERE` after `DO UPDATE SET` restricts which conflicting rows are updated:

```sql
CREATE TABLE tbl (i INTEGER PRIMARY KEY, j INTEGER UNIQUE, k INTEGER);
INSERT INTO tbl VALUES (1, 20, 300);
INSERT INTO tbl VALUES (1, 40, 700) ON CONFLICT (i) DO UPDATE SET k = 2 * EXCLUDED.k;
INSERT INTO tbl VALUES (1, 20, 900) ON CONFLICT (j) DO UPDATE SET k = 5 * EXCLUDED.k;
INSERT INTO tbl VALUES (1, 40, 700) ON CONFLICT (i) DO UPDATE SET k = 2 * EXCLUDED.k WHERE k < 100;
```

PostgreSQL's partial-index predicate (`ON CONFLICT (i) WHERE ... DO UPDATE`) is not supported (`Binder Error`). Deferred constraints cannot be conflict targets.

### `RETURNING`

Returns the inserted rows — useful for generated values such as sequence keys. Columns can be chosen, aliased or computed:

```sql
INSERT INTO t2 SELECT 2 AS i, 3 AS j RETURNING *, i * j AS i_times_j;

CREATE TABLE t3 (i INTEGER PRIMARY KEY, j INTEGER);
CREATE SEQUENCE 't3_key';
INSERT INTO t3
    SELECT nextval('t3_key') AS i, 42 AS j
    UNION ALL
    SELECT nextval('t3_key') AS i, 43 AS j
    RETURNING *;
```

### Loading with `INSERT`

Each `INSERT` has parsing and processing overhead, so avoid row-by-row inserts in a loop; insert as much data per statement as possible, or use `COPY`, file readers or the Appender. If you must loop, wrap the statements in `BEGIN TRANSACTION` … `COMMIT` — in auto-commit mode every statement is its own transaction and syncs to disk.

## `UPDATE`

```sql
UPDATE tbl SET i = 0 WHERE i IS NULL;
UPDATE tbl SET i = 1, j = 2;                                   -- all rows
UPDATE tbl SET j = j + 10 WHERE i = 1 RETURNING *;             -- rows after the update
```

Unmentioned columns keep their values. `RETURNING` works like a `SELECT` list without `DISTINCT`.

**From another table** — via `FROM` (joins expressed in `WHERE`) or a subquery; both run in bulk:

```sql
UPDATE original SET value = new.value FROM new WHERE original.key = new.key;
UPDATE original SET value = (SELECT new.value FROM new WHERE original.key = new.key);

UPDATE city
SET revenue = revenue + 100
FROM country
WHERE city.country_code = country.code
  AND country.name = 'France';

-- same table: aliases on both sides are required
UPDATE original AS true_original
    SET value = (SELECT new.value || ' a change!' AS value
                 FROM original AS new
                 WHERE true_original.key = new.key);
```

If a target row matches several `FROM` rows, it is updated once with an **unspecified** source row; deduplicate the source for deterministic results. The subquery form instead errors when the subquery returns more than one row.

## `DELETE` and `TRUNCATE`

```sql
DELETE FROM tbl WHERE i = 2;          -- rows where the condition is false or NULL are kept
DELETE FROM tbl;                      -- all rows
TRUNCATE tbl;                         -- alias for DELETE FROM tbl
DELETE FROM employees RETURNING name, 2025 - age AS approx_birthyear;
```

`USING` deletes based on other tables or subqueries. Deleted rows are only marked as deleted; space is reclaimed on `CHECKPOINT`, and `VACUUM` currently does not reclaim space (see [Transactions, Checkpoints and Maintenance](transactions-and-maintenance.md)).

## `MERGE INTO`

`MERGE INTO` is an upsert alternative to `INSERT ... ON CONFLICT` that needs **no primary key**, using a custom match condition (`ON (...)` or `USING (cols)`):

```sql
CREATE TABLE people (id INTEGER, name VARCHAR, salary FLOAT);
INSERT INTO people VALUES (1, 'John', 92_000.0), (2, 'Anna', 100_000.0);

-- whole-row upsert
MERGE INTO people
    USING (
        SELECT unnest([3, 1]) AS id, unnest(['Sarah', 'John']) AS name,
               unnest([95_000.0, 105_000.0]) AS salary
    ) AS upserts
    ON (upserts.id = people.id)
    WHEN MATCHED THEN UPDATE
    WHEN NOT MATCHED THEN INSERT;

-- change set
MERGE INTO people
    USING (SELECT 1 AS id, 98_000.0 AS salary) AS salary_updates
    USING (id)
    WHEN MATCHED THEN UPDATE SET salary = salary_updates.salary;

-- conditional delete set
MERGE INTO people
    USING (SELECT unnest([3, 2]) AS id) AS deletes
    USING (id)
    WHEN MATCHED AND people.salary >= 100_000.0 THEN DELETE;

-- several conditions, report actions
MERGE INTO people
    USING (SELECT unnest([3, 1]) AS id, unnest([89_000.0, 70_000.0]) AS salary) AS upserts
    USING (id)
    WHEN MATCHED AND people.salary < 100_000.0 THEN UPDATE SET salary = upserts.salary
    WHEN MATCHED AND people.salary > 100_000.0 THEN DELETE
    WHEN NOT MATCHED THEN INSERT BY NAME
    RETURNING merge_action, *;

-- remove target rows absent from the source
MERGE INTO target
    USING (SELECT 1 AS id) source
    USING (id)
    WHEN MATCHED THEN UPDATE
    WHEN NOT MATCHED BY SOURCE THEN DELETE
    RETURNING merge_action, *;
```

- `WHEN NOT MATCHED BY TARGET` behaves the same as `WHEN NOT MATCHED`.
- A `MERGE` may not affect the same target row more than once: if a target row matches several source rows under a `WHEN MATCHED` action, it fails with `MERGE INTO command cannot affect the same target row more than once` — unlike `UPDATE ... FROM`, which picks an arbitrary row.

| Use case | Clauses |
| --- | --- |
| Simple upsert | `WHEN MATCHED THEN UPDATE` + `WHEN NOT MATCHED BY TARGET THEN INSERT` |
| Upsert and delete missing rows | add `WHEN NOT MATCHED BY SOURCE THEN DELETE` |
| Insert only | omit `WHEN MATCHED` |
| See affected rows | `RETURNING merge_action, *` |

### Slowly changing dimension (SCD Type 2)

Expire changed or vanished current rows and insert new ones, keeping history:

```sql
MERGE INTO master_ducks AS target
USING incoming_ducks AS source
ON target.duck_id = source.duck_id AND target.is_current = true
WHEN MATCHED AND (
       target.duck_name <> source.duck_name OR
       target.breed     <> source.breed     OR
       target.location  <> source.location
) THEN UPDATE SET
    end_date = CURRENT_DATE - INTERVAL '1 day', is_current = false
WHEN NOT MATCHED BY SOURCE AND target.is_current = true THEN UPDATE SET
    end_date = CURRENT_DATE - INTERVAL '1 day', is_current = false
WHEN NOT MATCHED BY TARGET THEN INSERT (
    record_id, duck_id, duck_name, breed, location, begin_date, end_date, is_current
) VALUES (
    nextval('duck_record_seq'), source.duck_id, source.duck_name, source.breed,
    source.location, source.begin_date, source.end_date, source.is_current
)
RETURNING merge_action, *;
```

A follow-up `INSERT` adds new current versions for the changed records. Wrap the `MERGE` and `INSERT` in a transaction, keep `end_date` `NULL` for current rows, and test with `RETURNING` first.

## The Appender

The Appender is the fastest way to bulk-load rows from application code; it is available in the C, C++, Go, Java, Julia, Node.js, Python and Rust clients.

- It is tied to one connection and appends to one table, within that connection's transaction context.
- Rows are **cached** and may not be visible until flushed; the cache flushes when the Appender is closed or goes out of scope, or manually. In Python, call `flush()` or use a `with` block (an exception inside the block discards buffered rows; garbage collection also discards them).
- Each row must supply a value for every column, in column order.
- `NOT NULL`, `PRIMARY KEY` and `UNIQUE` are checked **at flush time**. A key violation fails the **entire** append (`PRIMARY KEY or UNIQUE constraint violated: duplicate key "..."`) and no rows are inserted.
- Except in Python, the Appender commits every **204,800 rows** by default; wrap batches in `BEGIN TRANSACTION` / `COMMIT` to change this.

```cpp
DuckDB db;
Connection con(db);
con.Query("CREATE TABLE people (id INTEGER, name VARCHAR)");
Appender appender(con, "people");
appender.AppendRow(1, "Mark");
appender.BeginRow();
appender.Append<int32_t>(2);
appender.Append<string>("Hannes");
appender.EndRow();
```

```python
con = duckdb.connect()
con.execute("CREATE TABLE people (id INTEGER, name VARCHAR)")
with con.appender("people") as appender:
    appender.append_row(1, "Mark")
```

```java
try (var appender = conn.createAppender(DuckDBConnection.DEFAULT_SCHEMA, "tbl")) {
    appender.beginRow();
    appender.append(10);
    appender.append("hello");
    appender.endRow();
}
```

Go uses `NewAppenderFromConn(conn, "", "test")` with `AppendRow`/`Flush`; Rust uses `conn.appender("foo")?` with `append_row(params![...])` and `flush()`. In C++, dates and times are appended most efficiently as `Date::FromDate(1992, 1, 1)`, `Time::FromTime(1, 1, 1, 0)` and `Timestamp::FromDatetime(...)`.
