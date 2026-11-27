---
type: reference
title: Views, Macros, Custom Types, Triggers and Comments
description: DuckDB catalog objects beyond tables — CREATE VIEW and SECURE VIEW (new in 2.0), ALTER VIEW; CREATE MACRO / CREATE FUNCTION with scalar and table macros, typed and default parameters, named arguments, overloading, expansion and limitations; sharing macros through attached database files; CREATE TYPE for ENUM, STRUCT, UNION and aliases; CREATE TRIGGER (new in 2.0) with row and statement granularity, transition tables and limitations; COMMENT ON.
tags: [sql, ddl, views, secure-view, macros, table-macros, create-type, triggers, comment-on]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-81b4930fc3969c71b737382b
    resource: repo://docs/2.0/guides/snippets/sharing_macros.md
  - id: openwiki-source-55ad2ef4ce9b7529451fe764
    resource: repo://docs/2.0/sql/statements/comment_on.md
  - id: openwiki-source-6825fdbbaa20c72af87d47ce
    resource: repo://docs/2.0/sql/statements/create_macro.md
  - id: openwiki-source-31cdcfd11033f29c651dcd7b
    resource: repo://docs/2.0/sql/statements/create_trigger.md
  - id: openwiki-source-51c631a8c5ec46d1e9533381
    resource: repo://docs/2.0/sql/statements/create_view.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Views, Macros, Custom Types, Triggers and Comments

Tables, schemas and sequences are on [CREATE TABLE, Constraints, ALTER TABLE …](create-and-alter-tables.md). Lambdas, often used inside macros, are on [List, Array and Lambda Functions](../functions/list-array-and-lambda.md).

## Views

```sql
CREATE VIEW view1 AS SELECT * FROM tbl;
CREATE OR REPLACE VIEW view1 AS SELECT 42;
CREATE VIEW view1 (a) AS SELECT 42;                  -- rename columns
SELECT sql FROM duckdb_views() WHERE view_name = 'view1';   -- view definition
ALTER VIEW view1 RENAME TO view2;
```

- Views are **not materialized**: the query runs every time the view is referenced.
- Temporary views live in a special schema, so no schema name can be given for them.
- `ALTER VIEW` is transactional; views that depend on a renamed view are **not** updated automatically. Since 2.0, `ALTER TABLE ⟨view⟩ RENAME TO` also works.
- View dependencies on tables are not tracked: dropping a referenced table leaves the view invalid.

**Secure views (new in DuckDB 2.0)** do not leak information about the underlying tables through statistics or plans — on a secure view, `stats()` returns uninformative statistics and `EXPLAIN ANALYZE` shows a single `Secure View` node:

```sql
CREATE SECURE VIEW users AS
    SELECT username
    FROM all_users
    WHERE access_level = 'standard';
```

## Macros

`CREATE MACRO` (alias `CREATE FUNCTION`) defines a named, callable SQL expression:

```sql
CREATE [OR REPLACE] [TEMPORARY] MACRO [IF NOT EXISTS] ⟨name⟩([⟨parameters⟩]) AS [TABLE] ⟨expression⟩;
```

- Macros are schema objects and are **persisted** in a database file unless `TEMPORARY`. `OR REPLACE` and `IF NOT EXISTS` are mutually exclusive; redefining without `OR REPLACE` fails.
- **Scalar macros** evaluate to a value (expression or scalar subquery); usable wherever the expression is, e.g. in `SELECT` and `WHERE`. A scalar macro whose expression uses an aggregate behaves like an aggregate.
- **Table macros** (`AS TABLE`) return a result set and behave like table functions in `FROM` or `CALL`.

```sql
CREATE MACRO add(a, b) AS a + b;
CREATE MACRO ifelse(a, b, c) AS CASE WHEN a THEN b ELSE c END;
CREATE MACRO one() AS (SELECT 1);
CREATE FUNCTION main.my_avg(x) AS sum(x) / count(x);
CREATE MACRO arr_append(l, e) AS list_concat(l, list_value(e));
CREATE MACRO is_maximal(a INTEGER) AS a = 2^31 - 1;          -- typed parameter

CREATE MACRO static_table() AS TABLE SELECT 'Hello' AS column1, 'World' AS column2;
CREATE MACRO get_users(i) AS TABLE
    SELECT * FROM users WHERE uid IN (SELECT unnest(i));
SELECT * FROM get_users([1, 5]);
```

### Parameters and calls

Each parameter is `⟨name⟩ [⟨type⟩] [:= ⟨default⟩]`:

- Names must be unique (`Duplicate parameter` otherwise); `TABLE`-typed parameters are not possible.
- Defaults make a parameter optional and are evaluated at **definition time** (with few exceptions); parameters with defaults must come after those without.
- Arguments are passed positionally or by name with **`:=`**. Named arguments come after positional ones and may be in any order. Do **not** use `=` — in a macro call it is a comparison, silently turning the argument into a positional boolean.

```sql
CREATE MACRO add_default(a, b := 5) AS a + b;
SELECT add_default(37);                                  -- 42
CREATE MACRO triple_add(a, b := 5, c := 10) AS a + b + c;
SELECT triple_add(40, c := 1, b := 1) AS x;              -- 42
```

Macros are **expanded**: `SELECT add(40, 2)` becomes `SELECT 40 + 2`. Names in the body must be parameters or resolvable columns — `CREATE MACRO add(a) AS a + b;` fails with `Referenced column "b" not found in FROM clause!`. Calls whose argument types match several candidates (e.g. `add('hello', 3)`) error and need explicit casts.

### Overloading

One `CREATE MACRO` statement can define several implementations with distinct parameter-type signatures (all scalar or all table). Wrap table-macro `SELECT`s in parentheses:

```sql
CREATE MACRO add_x
    (a, b) AS a + b,
    (a, b, c) AS a + b + c;

CREATE OR REPLACE MACRO is_maximal
    (a TINYINT) AS a = 2^7 - 1,
    (a INT) AS a = 2^31 - 1;

CREATE MACRO tbl_range
    (n) AS TABLE (SELECT * FROM range(n)),
    (start, stop) AS TABLE (SELECT * FROM range(start, stop));
SELECT count(*) FROM tbl_range(3, 8);                    -- 5
```

Overloads must all be defined at creation; a macro name cannot be defined twice without removing the first definition.

### Table macros over arbitrary tables and files

Use `query_table` for table-generic macros. A table macro's body is **bound at creation**, so file names written into it are resolved then; pass them as parameters to resolve at call time:

```sql
CREATE MACRO checksum(tbl) AS TABLE
    SELECT bit_xor(md5_number(COLUMNS(*)::VARCHAR))
    FROM query_table(tbl);
SELECT * FROM checksum('tbl');

CREATE MACRO read_pipe() AS TABLE FROM read_csv('/dev/stdin');   -- IO Error at creation if missing
CREATE OR REPLACE TEMPORARY MACRO read_pipe(pipe := '/dev/stdin') AS TABLE
    FROM read_csv(pipe);
FROM read_pipe();
```

### Limitations

- Table macros and scalar macros defined with scalar subqueries cannot be used in table function arguments (`Table function cannot contain subqueries`).
- Recursive macros are not supported (they hit `Max expression depth limit of 1000 exceeded`).
- List macros: `SELECT schema_name, function_name, function_type, parameters FROM duckdb_functions();`

### Sharing macros

Because macros persist in the database file, a file of macros can be published and attached — even over HTTPS with `httpfs`:

```sql
-- in pretty_print_integer_macro.duckdb
CREATE MACRO pretty_print_integer(n) AS
    CASE
        WHEN n >= 1_000_000_000 THEN printf('%dB', n // 1_000_000_000)
        WHEN n >= 1_000_000     THEN printf('%dM', n // 1_000_000)
        WHEN n >= 1_000         THEN printf('%dk', n // 1_000)
        ELSE printf('%d', n)
    END;

-- elsewhere
INSTALL httpfs;
ATTACH 'https://blobs.duckdb.org/data/pretty_print_integer_macro.duckdb' AS pretty_print_macro_db;
SELECT pretty_print_macro_db.pretty_print_integer(42_123) AS x;     -- 42k
```

## `CREATE TYPE`

Defines named types, listed in `duckdb_types()`:

```sql
CREATE TYPE mood AS ENUM ('happy', 'sad', 'curious');
CREATE TYPE many_things AS STRUCT(k INTEGER, l VARCHAR);
CREATE TYPE one_thing AS UNION(number INTEGER, string VARCHAR);
CREATE TYPE x_index AS INTEGER;                                 -- alias
CREATE OR REPLACE TYPE mood AS ENUM ('cheerful', 'gloomy');
```

Custom operators for types (like PostgreSQL's `&&`) need a C++ extension. Type details are on [Nested Types](../data-types/nested-types.md).

## Triggers (new in DuckDB 2.0)

`CREATE TRIGGER` runs a single SQL statement (typically `INSERT`/`UPDATE`/`DELETE`) automatically on `INSERT`, `UPDATE` or `DELETE` events of a base table.

```sql
-- statement-level audit with transition tables
CREATE TRIGGER trg_audit
    AFTER UPDATE ON target
    REFERENCING
        OLD TABLE AS o
        NEW TABLE AS n
    FOR EACH STATEMENT
        INSERT INTO audit
        SELECT n.id, o.val, n.val
        FROM o
        JOIN n ON o.id = n.id;

-- row-level
CREATE TRIGGER trg_log
    AFTER INSERT ON t
    FOR EACH ROW
        INSERT INTO log VALUES (NEW.id);

-- only when specific columns change
CREATE TRIGGER trg_price
    AFTER UPDATE OF price ON products
    FOR EACH STATEMENT
        INSERT INTO price_changes DEFAULT VALUES;

DROP TRIGGER IF EXISTS trg_audit ON target;     -- the table must be named (and exist)
SELECT trigger_name, table_name, action_timing, event_manipulation, for_each FROM duckdb_triggers();
```

- **Timing:** `BEFORE` or `AFTER` the triggering statement. **Granularity:** `FOR EACH ROW` (refer to `NEW` for inserts, `OLD` for deletes) or `FOR EACH STATEMENT` (once per statement).
- **Transition tables** (statement level): `NEW TABLE` for `INSERT`/`UPDATE`, `OLD TABLE` for `UPDATE`/`DELETE`.
- `CREATE OR REPLACE TRIGGER` / `CREATE TRIGGER IF NOT EXISTS`; otherwise a duplicate name errors. Several triggers per event fire in creation order. Dropping a table drops its triggers.
- `RETURNING` works on tables with statement-level triggers.

**Limitations in DuckDB 2.0:**

- Not supported: `BEFORE ... FOR EACH ROW`, `UPDATE ... FOR EACH ROW`, `INSTEAD OF` triggers, triggers on views, and temporary triggers.
- `RETURNING` and `ON CONFLICT` are not supported on tables with row-level triggers.
- `MERGE INTO` is not supported on tables with triggers. `INSERT ... ON CONFLICT`, `INSERT OR REPLACE` and `INSERT OR IGNORE` run as merges, so they fail on tables with `UPDATE` or `DELETE` triggers.
- Row- and statement-level triggers cannot be mixed for the same event on a table.
- Triggers are not included in `EXPORT DATABASE` or `COPY FROM DATABASE` (see [COPY and EXPORT/IMPORT DATABASE](copy-and-export.md)).

## `COMMENT ON`

Attaches comments to catalog entries (PostgreSQL syntax); set to `NULL` to remove:

```sql
COMMENT ON TABLE test_table IS 'very nice table';
COMMENT ON COLUMN test_table.test_table_column IS 'very nice column';
COMMENT ON VIEW test_view IS 'very nice view';
COMMENT ON INDEX test_index IS 'very nice index';
COMMENT ON SEQUENCE test_sequence IS 'very nice sequence';
COMMENT ON TYPE test_type IS 'very nice type';
COMMENT ON MACRO test_macro IS 'very nice macro';
COMMENT ON MACRO TABLE test_table_macro IS 'very nice table macro';
COMMENT ON TABLE test_table IS NULL;
```

Read comments from the `comment` column of `duckdb_tables()`, `duckdb_columns()`, `duckdb_views()`, `duckdb_indexes()`, `duckdb_sequences()`, `duckdb_types()` and `duckdb_functions()` (macros and table macros). Schemas and databases cannot be commented.
