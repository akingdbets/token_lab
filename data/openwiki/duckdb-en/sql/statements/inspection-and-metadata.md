---
type: reference
title: DESCRIBE, SHOW, SUMMARIZE, EXPLAIN/Profiling, CALL and Metadata Functions
description: Inspecting DuckDB schemas and queries — DESCRIBE and SUMMARIZE for tables and queries, SHOW for settings (new in 2.0; SHOW for tables deprecated) plus SHOW DATABASES / SCHEMAS / VARIABLES / EXTERNAL RESOURCES, EXPLAIN, EXPLAIN (SQL) (new in 2.0) and EXPLAIN ANALYZE, CALL, the duckdb_* metadata table functions and views, and information_schema with catalog functions.
tags: [sql, describe, show, summarize, explain, profiling, call, metadata, information-schema]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-9c1fb337e283d150c007e842
    resource: repo://docs/2.0/sql/meta/duckdb_table_functions.md
  - id: openwiki-source-12648648481690ed1100d255
    resource: repo://docs/2.0/sql/meta/information_schema.md
  - id: openwiki-source-e8f4b9d7708e3fbe1fe73c09
    resource: repo://docs/2.0/sql/statements/call.md
  - id: openwiki-source-8ae62c168f8db6199de3b000
    resource: repo://docs/2.0/sql/statements/describe.md
  - id: openwiki-source-7ba37eec105a2df7fdf94a2f
    resource: repo://docs/2.0/sql/statements/profiling.md
  - id: openwiki-source-474b5ec7bde9ca275c83026c
    resource: repo://docs/2.0/sql/statements/show.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# DESCRIBE, SHOW, SUMMARIZE, EXPLAIN/Profiling, CALL and Metadata Functions

Settings themselves are covered on [Settings, PRAGMAs and Configuration](../../configuration/settings-and-pragmas.md); reading query plans for performance on [Performance Tuning](../../performance/tuning-workloads.md).

## `DESCRIBE` and `SUMMARIZE`

`DESCRIBE` shows the schema (column names, types, nullability, keys, defaults) of a table, view or query; `SUMMARIZE` computes summary statistics per column. Prepend either to a query to inspect its result:

```sql
DESCRIBE tbl;
DESCRIBE SELECT * FROM tbl;
SUMMARIZE tbl;
SUMMARIZE SELECT * FROM tbl;
```

`DESCRIBE` never resolves a setting name.

## `SHOW`

**Deprecated in DuckDB 2.0:** using `SHOW` to describe a table, view or query prints a warning — use `DESCRIBE`.

**New in DuckDB 2.0:** `SHOW ⟨name⟩` prints a configuration setting when the name is not a table (PostgreSQL-style):

```sql
SET threads = 42;
SHOW threads;          -- 42
```

If a table and a setting share the name, `SHOW` describes the table (with the deprecation warning). The `show_behavior` setting controls resolution: `'auto'` (default: table if it exists, else setting), `'table'`, or `'setting'`.

```sql
SET show_behavior = 'setting';
```

Other `SHOW` statements:

```sql
SHOW DATABASES;                      -- attached databases, e.g. memory, my_database
SHOW SCHEMAS;                        -- database_name, schema_name, current (since 1.5)
SET VARIABLE int_var = 42;
SHOW VARIABLES;                      -- name, value (VARCHAR), type of SQL-level variables
SHOW [ALL] EXTERNAL RESOURCES [WITH TYPE ⟨type⟩];
SELECT name, kind FROM (SHOW EXTERNAL RESOURCE TYPES);
```

- In `SHOW SCHEMAS`, `current` marks the default schema chosen with `USE`.
- Variables removed by `RESET VARIABLE` are not listed; the same data is in `duckdb_variables()`.
- `SHOW EXTERNAL RESOURCES` lists resource registrations (`ALL` also lists the underlying resources). **Since 2.0.1**, `WITH TYPE` filters by external resource type and the statement is a query usable as a subquery or in a CTE. `SHOW EXTERNAL RESOURCE TYPES` (new in 2.0.1) has the columns of `duckdb_external_resource_types()`.

## `EXPLAIN` and `EXPLAIN ANALYZE`

```sql
EXPLAIN ⟨query⟩;            -- plan with estimated cardinalities; does not run the query
EXPLAIN ANALYZE ⟨query⟩;    -- runs the query; actual cardinalities and cumulative wall-clock time per operator
```

**`EXPLAIN (SQL)` (new in DuckDB 2.0)** renders the *optimized* logical plan back as executable DuckDB SQL:

```sql
EXPLAIN (SQL) SELECT 1 + 2 AS answer;
-- explain_key = sql, explain_value = SELECT CAST(3 AS INTEGER) AS answer
```

- The output can differ substantially from the input (join reordering, constant folding, subquery introduction). Result column names, order and logical types are preserved, but formatting and generated aliases are not a stable interface.
- It does not execute the query, supports only `SELECT`, `VALUES`, `WITH`, `INSERT`, `UPDATE`, `DELETE` and `MERGE INTO`, and cannot be combined with `ANALYZE` or `FORMAT`.

Profiler output and metrics are configured through settings; `duckdb_profiling_settings()` returns the current profiling-related settings and `duckdb_available_metrics()` (new in 2.0) lists metrics that can be collected, e.g., via the `tracked_metrics` setting.

## `CALL`

`CALL` invokes a table function and returns its result. Because procedures are table functions, `FROM` works too:

```sql
CALL duckdb_functions();
CALL pragma_table_info('pg_am');
FROM duckdb_functions();

SELECT function_name, parameters, parameter_types, return_type
FROM duckdb_functions()
WHERE function_name LIKE 'ST_%';
```

## `duckdb_*` metadata table functions

Table functions in the `main` schema, prefixed `duckdb_`, describe the instance; use them like tables. Parentheses are required (`SELECT * FROM duckdb_settings();` or `CALL duckdb_settings();`). Some also exist as identically named **views** that filter out internal objects:

```sql
SELECT * FROM duckdb_views();    -- all views, including internal ones
SELECT * FROM duckdb_views;      -- view: non-internal only
```

| Function | Describes |
| --- | --- |
| `duckdb_columns()`, `duckdb_tables()`, `duckdb_views()`, `duckdb_schemas()`, `duckdb_databases()` | Catalog objects |
| `duckdb_constraints()`, `duckdb_indexes()`, `duckdb_sequences()`, `duckdb_dependencies()` | Constraints, secondary indexes, sequences, dependencies |
| `duckdb_functions()` | Functions and macros (`extension_name` column new in 2.0) |
| `duckdb_types()`, `duckdb_keywords()` | Data types; SQL keywords |
| `duckdb_settings()` | Settings (2.0: `debug`, `deprecated`, `include_all` parameters) |
| `duckdb_extensions()`, `duckdb_extension_repositories()` (2.0) | Extensions and repositories |
| `duckdb_grammar_extensions()` (2.0) | Syntax-extending grammar extensions |
| `duckdb_secrets()`, `duckdb_secret_types()`, `duckdb_secret_type_parameters()` (2.0) | Secrets (see [Secrets Manager](../../configuration/secrets-manager.md)) |
| `duckdb_triggers()` (2.0) | Triggers |
| `duckdb_external_resources()`, `duckdb_external_resource_types()` (2.0.0) | External resources |
| `duckdb_prepared_statements()`, `duckdb_variables()` | Session prepared statements; SQL-level variables |
| `duckdb_memory()`, `duckdb_temporary_files()` | Buffer manager usage; spill files (mostly for debugging) |
| `duckdb_logs()`, `duckdb_log_contexts()` | Log entries and contexts |
| `duckdb_optimizers()` | Optimizer rules (e.g., `filter_pushdown`) |
| `duckdb_connection_count()` | Open connections |
| `duckdb_coordinate_systems()` | Coordinate reference systems |

`duckdb_settings()` returns only regular settings by default; `debug := true` or `deprecated := true` selects those categories, and `include_all := true` (not combinable with the other two) returns everything:

```sql
SELECT * FROM duckdb_settings(include_all := true);
```

In `duckdb_sequences()`, `last_value` is `NULL` if no value was drawn; a cycling sequence restarts at its range boundary, not necessarily the start value.

## `information_schema`

SQL-standard views modeled on PostgreSQL's information schema:

| View | Contents |
| --- | --- |
| `information_schema.schemata` | Catalogs and schemas |
| `information_schema.tables` | Tables and views (`table_type`: `BASE TABLE`, `LOCAL TEMPORARY`, `VIEW`) |
| `information_schema.columns` | Columns (`is_generated`, `generation_expression` new in 2.0) |
| `table_constraints`, `key_column_usage`, `referential_constraints`, `constraint_column_usage` | Constraints and their columns |
| `character_sets` | Character sets |

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'main';
```

Catalog functions:

| Function | Result |
| --- | --- |
| `current_catalog()` | Active catalog; default `'memory'` |
| `current_schema()` | Active schema; default `'main'` |
| `current_schemas(true)` | Schema search list including implicit schemas, e.g. `['main', 'main', 'main', 'pg_catalog']` |
