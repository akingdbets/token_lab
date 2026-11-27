---
type: reference
title: CREATE TABLE, Constraints, ALTER TABLE, DROP, Schemas and Sequences
description: Defining and evolving DuckDB schema objects — CREATE TABLE with OR REPLACE, IF NOT EXISTS, temporary tables, CTAS and schema copies, generated columns; CHECK, NOT NULL, PRIMARY KEY, UNIQUE (DEFERRED, new in 2.0) and FOREIGN KEY constraints; ALTER TABLE operations and their limitations on indexed tables; DROP with RESTRICT/CASCADE; CREATE SCHEMA with nested schemas (new in 2.0); CREATE SEQUENCE, nextval, currval and setval (new in 2.0).
tags: [sql, ddl, create-table, constraints, alter-table, drop, schema, sequence]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-06b8f5517c62aa3478107e88
    resource: repo://docs/2.0/sql/constraints.md
  - id: openwiki-source-81a894c84bf92cf4823d1609
    resource: repo://docs/2.0/sql/statements/alter_table.md
  - id: openwiki-source-280e3baaf7fca1125c855ee8
    resource: repo://docs/2.0/sql/statements/create_schema.md
  - id: openwiki-source-cda8da91862ebf108cdae45a
    resource: repo://docs/2.0/sql/statements/create_sequence.md
  - id: openwiki-source-4b1bc54a30c718075bc75933
    resource: repo://docs/2.0/sql/statements/create_table.md
  - id: openwiki-source-40caef03e4b050fabca46206
    resource: repo://docs/2.0/sql/statements/drop.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# CREATE TABLE, Constraints, ALTER TABLE, DROP, Schemas and Sequences

Views, macros and types are on [Views, Macros, Types and Other Catalog Objects](views-macros-and-types.md). How constraints and indexes affect performance is covered on [Schema Design, Indexes and Join Performance](../../performance/schema-indexes-and-joins.md).

## `CREATE TABLE`

```sql
CREATE TABLE t1 (i INTEGER, j INTEGER);
CREATE TABLE t1 (id INTEGER PRIMARY KEY, j VARCHAR);
CREATE TABLE t1 (id INTEGER, j VARCHAR, PRIMARY KEY (id, j));        -- composite key
CREATE TABLE t1 (
    i INTEGER NOT NULL DEFAULT 0,
    decimalnr DOUBLE CHECK (decimalnr < 10),
    date DATE UNIQUE,
    time TIMESTAMP
);
CREATE OR REPLACE TABLE t1 (i INTEGER, j INTEGER);    -- drop and recreate
CREATE TABLE IF NOT EXISTS t1 (i INTEGER, j INTEGER); -- no-op if it exists
```

### `CREATE TABLE ... AS SELECT` (CTAS)

CTAS infers column names and types from a query — works with the CSV reader, `FROM`-first syntax, file-name shorthands and HTTP(S):

```sql
CREATE TABLE nums AS SELECT i FROM range(0, 3) t(i);
CREATE TABLE t1 AS FROM read_csv('path/file.csv');
CREATE OR REPLACE TABLE flights AS FROM 'https://duckdb.org/data/flights.csv';

-- copy only column names and types (no indexes, constraints or defaults)
CREATE TABLE t1 AS FROM t2 WITH NO DATA;
CREATE TABLE t1 AS FROM t2 LIMIT 0;
```

CTAS cannot declare constraints (primary keys, checks, …); create the table first and `INSERT` instead.

### Temporary tables

`CREATE TEMP TABLE` / `CREATE TEMPORARY TABLE` creates a session-scoped table in the `temp.main` schema, dropped when the connection closes. It lives in memory even in a persistent database, but spills to disk if `temp_directory` is set. Temporary tables take priority in name resolution; refer to a same-named regular table by its full name (e.g., `memory.main.t1`).

```sql
CREATE TEMP TABLE t1 AS SELECT * FROM read_csv('path/file.csv');
SET temp_directory = '/path/to/directory/';
```

### Generated columns

`[type] [GENERATED ALWAYS] AS (expr) [VIRTUAL|STORED]` defines a column computed from other columns. The type can be inferred. Only **`VIRTUAL`** (computed on read, the default) is currently supported.

```sql
CREATE TABLE t1 (x FLOAT, two_x AS (2 * x));
CREATE TABLE t1 (x FLOAT, two_x FLOAT GENERATED ALWAYS AS (2 * x) VIRTUAL);
```

## Constraints

Constraints slow down loading and updates but can speed up certain queries.

| Constraint | Enforces | Error on violation |
| --- | --- | --- |
| `CHECK (expr)` | Boolean expression holds for every row | `CHECK constraint failed: t1` |
| `NOT NULL` | No `NULL`s (columns are nullable by default) | `NOT NULL constraint failed: students.name` |
| `PRIMARY KEY` | Unique and not `NULL`; at most one per table | `Duplicate key "id: 1" violates primary key constraint` |
| `UNIQUE` | Unique values (many per table allowed) | `Duplicate key "email: ..." violates unique constraint.` |
| `FOREIGN KEY ... REFERENCES` | Referenced primary-key/unique value exists | `Violates foreign key constraint because key "id: 2" does not exist in the referenced table` |

```sql
CREATE TABLE students (name VARCHAR CHECK (NOT contains(name, ' ')));
CREATE TABLE t3 (
    id INTEGER PRIMARY KEY, x INTEGER, y INTEGER,
    CONSTRAINT x_smaller_than_y CHECK (x < y)
);
CREATE TABLE integers (i INTEGER, j INTEGER, k INTEGER, UNIQUE (i, j));
CREATE TABLE t4 (
    id INTEGER PRIMARY KEY, t3_id INTEGER, t3_j VARCHAR,
    FOREIGN KEY (t3_id, t3_j) REFERENCES t3(id, j)          -- composite foreign key
);
CREATE TABLE exams (
    exam_id INTEGER PRIMARY KEY,
    subject_id INTEGER REFERENCES subjects(id)               -- inline form
);
```

- An **ART index** is created automatically for every primary key, unique and foreign key constraint. Index limitations can make constraint checks over-eager (spurious "violates primary key/unique constraint" errors); see the indexes notes on the performance page.
- Foreign keys can reference unique columns as well as primary keys. **Not supported:** `ON DELETE CASCADE`, and inserting rows that reference rows inserted in the same statement into a self-referencing table.

### Deferred primary key and unique checks (new in DuckDB 2.0)

`PRIMARY KEY` and `UNIQUE` may be declared `DEFERRED`: they are checked at `COMMIT`, so a transaction may violate uniqueness temporarily; if the violation remains, the commit fails with a duplicate key error.

```sql
CREATE TABLE items (id INTEGER PRIMARY KEY DEFERRED, note VARCHAR);
BEGIN;
INSERT INTO items VALUES (1, 'keep'), (1, 'remove');  -- does not fail eagerly
DELETE FROM items WHERE note = 'remove';
COMMIT;                                               -- succeeds
```

`NOT NULL` on a deferred primary key is still checked eagerly; a foreign key cannot reference a deferred key; a deferred constraint cannot be an `ON CONFLICT` target. `duckdb_constraints()` has an `is_deferred` column.

## `ALTER TABLE`

All `ALTER TABLE` changes are transactional: invisible to other transactions until committed and fully undone by rollback.

```sql
ALTER TABLE integers ADD COLUMN k INTEGER;                 -- filled with NULL
ALTER TABLE integers ADD COLUMN l INTEGER DEFAULT 10;      -- filled with 10
ALTER TABLE integers DROP k;                               -- or DROP COLUMN k
ALTER TABLE integers ALTER i TYPE VARCHAR;                 -- = SET TYPE / SET DATA TYPE
ALTER TABLE integers ALTER i SET DATA TYPE VARCHAR USING concat(i, '_', j);
ALTER TABLE integers ALTER COLUMN i SET DEFAULT 10;        -- existing data unchanged
ALTER TABLE integers ALTER COLUMN i DROP DEFAULT;          -- = default NULL
ALTER TABLE integers ALTER COLUMN i SET NOT NULL;
ALTER TABLE integers ALTER COLUMN i DROP NOT NULL;
ALTER TABLE integers RENAME TO integers_old;
ALTER TABLE integers RENAME i TO ii;                       -- or RENAME COLUMN
ALTER TABLE integers ADD PRIMARY KEY (i, j);
ALTER TABLE integers ADD CONSTRAINT j_unique UNIQUE (j);
ALTER TABLE my_table SET ('option1' = 'value1', 'option2' = 'value2');   -- table options (since 1.5)
ALTER TABLE my_table RESET ('option1', 'option2');
```

- Renaming a table or column does **not** update dependent views; `CHECK` constraints are updated on column rename. **New in 2.0:** `ALTER TABLE ⟨view⟩ RENAME TO ⟨new_name⟩` also renames views (PostgreSQL compatibility).
- Adding a primary key or unique constraint fails with `Data contains duplicates on indexed column(s)` if existing data violates it. Adding `CHECK` or `FOREIGN KEY` constraints and `DROP CONSTRAINT` are **not supported** yet.
- A column with an index (including one from `PRIMARY KEY`/`UNIQUE`) cannot be dropped: `Cannot drop this column: an index depends on it!`
- **Indexed tables:** most `ALTER TABLE` operations (renames, dropping or retyping columns, `SET/DROP NOT NULL`) are refused on a table with an index (`Dependency Error`); adding columns and changing defaults are allowed. Drop the index, alter, then recreate it.
- Struct columns: change the sub-schema with `ALTER col TYPE USING struct_insert(col, a := 42, b := NULL::VARCHAR)`, or (since 1.3.0) with `ADD/DROP/RENAME COLUMN` on struct fields (see [Nested Types](../data-types/nested-types.md)).
- `ALTER COLUMN ... TYPE` fails if conflicting values *ever* existed in the column, even if deleted (`Could not convert string 'asdf' to INT32`). Workaround: `CREATE OR REPLACE TABLE tbl AS FROM tbl;` first.

## `DROP`

```sql
DROP TABLE tbl;
DROP VIEW IF EXISTS view1;
DROP FUNCTION fn;
DROP INDEX idx;
DROP SCHEMA sch;
DROP SEQUENCE seq;
DROP MACRO mcr;
DROP MACRO TABLE mt;      -- TABLE optional since v1.4.0
DROP TYPE typ;
```

By default (`RESTRICT`), an entry with dependents is not dropped; `CASCADE` also drops dependents. Tracked dependencies are a schema's functions, macros, table macros, schemas, sequences, tables, types and views:

```sql
CREATE SCHEMA myschema;
CREATE TABLE myschema.t1 (i INTEGER);
DROP SCHEMA myschema;            -- Dependency Error: ... Use DROP...CASCADE to drop all dependents.
DROP SCHEMA myschema CASCADE;    -- drops myschema and myschema.t1
```

- View dependencies are **not tracked**: dropping a table a view uses leaves the view invalid (`Table with name tbl does not exist!`).
- `DROP TABLE` frees memory but not always disk space; freed blocks are reused. Check `free_blocks` with `PRAGMA database_size;` and see [Installation, Migration and Footprint](../../operations/installation-migration-and-footprint.md) for reclaiming space.

## `CREATE SCHEMA`

The default schema is `main`.

```sql
CREATE SCHEMA s1;
CREATE SCHEMA IF NOT EXISTS s2;
CREATE OR REPLACE SCHEMA s2;
CREATE TABLE s1.t (id INTEGER PRIMARY KEY, other_id INTEGER);
SELECT * FROM s1.t s1t, s2.t s2t WHERE s1t.other_id = s2t.id;
```

**Nested schemas (new in DuckDB 2.0)** are addressed by dot-separated paths:

```sql
CREATE SCHEMA finance;
CREATE SCHEMA finance.reports;
CREATE TABLE finance.reports.q3 (revenue DECIMAL);
```

## `CREATE SEQUENCE`

```sql
CREATE SEQUENCE serial;                                          -- 1, 2, 3, ...
CREATE SEQUENCE serial START 101;
CREATE SEQUENCE serial START WITH 1 INCREMENT BY 2;              -- odd numbers
CREATE SEQUENCE serial START WITH 99 INCREMENT BY -1 MAXVALUE 99;
CREATE SEQUENCE serial START WITH 1 MAXVALUE 10 CYCLE;           -- wrap around
CREATE OR REPLACE SEQUENCE serial;
CREATE SEQUENCE IF NOT EXISTS serial;
DROP SEQUENCE IF EXISTS serial;
```

| Parameter | Default |
| --- | --- |
| `INCREMENT BY` | `1` (negative = descending) |
| `MINVALUE` | `1` ascending; `-(2^63 - 1)` descending |
| `MAXVALUE` | `2^63 - 1` ascending; `-1` descending |
| `START WITH` | `minvalue` ascending; `maxvalue` descending |
| `CYCLE` / `NO CYCLE` | `NO CYCLE` — reaching the limit errors: `nextval: reached maximum value of sequence "serial" (10)` |
| `TEMP` / `TEMPORARY` | Session-only; hides a same-named permanent sequence |

Sequences use `BIGINT` arithmetic. Use them for surrogate keys:

```sql
CREATE SEQUENCE id_sequence START 1;
CREATE TABLE tbl (id INTEGER PRIMARY KEY DEFAULT nextval('id_sequence'), s VARCHAR);
INSERT INTO tbl (s) VALUES ('hello'), ('world');            -- ids 1, 2
ALTER TABLE tbl2 ADD COLUMN id INTEGER DEFAULT nextval('id_sequence');
```

- `nextval('serial')` advances; `currval('serial')` returns the current value but errors (`sequence is not yet defined in this session`) before the first `nextval`.
- **`setval` (new in DuckDB 2.0):** `setval('serial', 42)` makes the next `nextval` return `43`; with `is_called = false` (`setval('serial', 42, false)`) it returns `42`.
- A sequence referenced by a column `DEFAULT` cannot be dropped or `CREATE OR REPLACE`d (`Dependency Error`). `DROP SEQUENCE ... CASCADE` drops the **whole table**, since dependencies are tracked per table; instead `ALTER TABLE tbl ALTER COLUMN id DROP DEFAULT;` first.
