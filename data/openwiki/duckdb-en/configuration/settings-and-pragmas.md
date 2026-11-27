---
type: reference
title: Configuration Options, SET and PRAGMA
description: Configure DuckDB with SET, RESET and scopes (GLOBAL, SESSION), inspect settings with current_setting() and duckdb_settings(), the most important options with their defaults (memory_limit, threads, temp_directory, preserve_insertion_order, enable_external_access, ...), PRAGMA statements for metadata, profiling and checkpointing, and SQL variables with SET VARIABLE and the $name shorthand (new in 2.0).
tags: [configuration, set, reset, pragma, settings, memory-limit, threads, variables, getvariable]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-343af4a0bc8c4a9ef66a1570
    resource: repo://docs/2.0/configuration/overview.md
  - id: openwiki-source-3d2e73035a9a4a08cceaa5c4
    resource: repo://docs/2.0/configuration/pragmas.md
  - id: openwiki-source-8a78aaca8683ac32763a4331
    resource: repo://docs/2.0/sql/statements/set_variable.md
  - id: openwiki-source-0781909b93ab46c32a7a69f1
    resource: repo://docs/2.0/sql/statements/set.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Configuration Options, SET and PRAGMA

DuckDB's behavior is controlled by configuration options. Set them with `SET` (or, for clients, in the connection config — e.g. Python `duckdb.connect(config={...})`), reset with `RESET`, and inspect them with `current_setting()` or `duckdb_settings()`.

## `SET` and `RESET`

```sql
SET memory_limit = '10GB';
SET threads = 1;
SET threads TO 1;                       -- TO is equivalent to =
RESET threads;                          -- back to the default
SELECT current_setting('threads');
SET SESSION default_collation = 'nocase';
SET GLOBAL default_order = 'DESC';
SET GLOBAL threads = 4;
```

**Scopes:**

- `GLOBAL` — applies across the whole DuckDB instance.
- `SESSION` — applies only to the current session (connection).
- `LOCAL` — not yet implemented.

Without an explicit scope, the option's default scope is used — `GLOBAL` for most options. `GLOBAL` settings are **not written to the database file** and not persisted across instances: after all connections close and a new instance starts, options are back to defaults. In DuckDB 2.0 `TimeZone` defaults to the `SESSION` scope, so `SET TimeZone = 'UTC'` equals `SET SESSION TimeZone = 'UTC'`; use `SET GLOBAL TimeZone = 'UTC'` for all sessions.

```sql
SELECT current_setting('memory_limit') AS memlimit;
SELECT * FROM duckdb_settings() WHERE name = 'threads';   -- name, value, description, input_type, scope
```

## Important options and defaults

| Option (aliases) | Default | Description |
| --- | --- | --- |
| `memory_limit` (`max_memory`) | 80% of RAM | Maximum memory; **since 2.0** also accepts a percentage, e.g. `'60%'` |
| `threads` (`worker_threads`) | # CPU cores | Total background threads |
| `operator_memory_limit` | `NULL` (unset) | **New in 2.0**: per-connection cap for sort buffers / hash tables |
| `max_execution_time` | `0` (no limit) | **New in 2.0**: query wall-clock limit in ms; error `Query exceeded maximum execution time` |
| `temp_directory` | `⟨database_name⟩.tmp` or `.tmp` (in-memory) | Spill directory |
| `max_temp_directory_size` | 90% of available disk space | Cap on spilled data |
| `preserve_insertion_order` | `true` | If `false`, results without `ORDER BY` may be reordered (saves memory) |
| `default_order` | `ASCENDING` | Default sort direction |
| `default_null_order` (`null_order`) | `NULLS_LAST` | Default NULL ordering |
| `default_collation` | (none) | Collation when none specified |
| `access_mode` | `automatic` | `AUTOMATIC`, `READ_ONLY`, `READ_WRITE` |
| `enable_external_access` | `true` | Allow files, network, extension installs, replacement scans |
| `allowed_directories` / `allowed_paths` | `[]` | Always-allowed locations even when external access is off |
| `lock_configuration` | `false` | Prevent further configuration changes |
| `allow_unsigned_extensions` | `false` | Load extensions without valid signatures |
| `autoinstall_known_extensions` / `autoload_known_extensions` | `true` / `true` | Extension autoloading |
| `checkpoint_threshold` (`wal_autocheckpoint`) | `16.0 MiB` | WAL size that triggers an automatic checkpoint |
| `storage_compatibility_version` | `latest` | Storage format version written at checkpoint |
| `default_block_size` | `262144` | Block size for new database files |
| `immediate_transaction_mode` | `false` | Start transactions at `BEGIN` instead of lazily |
| `integer_division` | `false` | Make `/` integer division |
| `errors_as_json` | `false` | Structured JSON error messages |
| `enable_progress_bar` | `false` (`true` in the CLI) | Progress bar; `progress_bar_time` default `2000` ms |
| `enable_profiling` | `NULL` | `JSON`, `QUERY_TREE`, `QUERY_TREE_OPTIMIZER` (local) |
| `profiling_coverage` | `SELECT` | `SELECT` or `ALL` |
| `schema` / `search_path` | `main` / (empty) | Search path for unqualified names |
| `TimeZone`, `Calendar` | System locale | ICU time zone and calendar |
| `ordered_aggregate_threshold` | `262144` | Rows accumulated before sorting |
| `external_threads` | `1` | External threads working on DuckDB tasks |
| `catalog_error_max_schemas` | `100` | Schemas scanned for "did you mean" errors |

`search_path` sets a comma-separated list of schemas (optionally `catalog.schema`); `schema` sets it to one entry. Asynchronous I/O settings (`async_threads`, `read_ahead_depth`), new in 2.0, are covered in [Importing Data Overview, File Access](../data/overview-and-file-access.md). Deprecated options include `enable_object_cache` (does nothing), `old_implicit_casting`, `profiling_mode`, `lambda_syntax`, `extension_directory` (use `extension_directories`) and the legacy `s3_*` settings (use [secrets](secrets-manager.md)).

> **Memory warning:** `memory_limit` applies only to the buffer manager. Vectors, query results and aggregates with complex state (`list`, `mode`, `quantile`, `string_agg`, approximate functions) allocate outside it, so actual usage can exceed the limit. See [Performance Tuning](../performance/tuning-workloads.md).

## PRAGMA statements

> **Deprecated:** assigning settings with `PRAGMA name = value` emits a warning (an error with `warnings_as_errors`); use `SET`. Function-style pragmas such as `PRAGMA table_info('t')` and the SQLite form `PRAGMA table_info = 't'` are unaffected.

Many pragmas have a table-function form via `CALL pragma_...()`.

| Area | Statements |
| --- | --- |
| Schema info | `PRAGMA database_list;`, `PRAGMA show_tables;`, `PRAGMA show_tables_expanded;`, `PRAGMA functions;`, `PRAGMA show_databases;` |
| Table info | `PRAGMA table_info('table_name');` / `CALL pragma_table_info('table_name');` |
| Size / storage | `PRAGMA database_size;`, `PRAGMA storage_info('table_name');` (2.0: table-function form accepts `include_segment_info`) |
| System info | `PRAGMA version;`, `PRAGMA platform;` (e.g. `osx_arm64`), `PRAGMA user_agent;`, `PRAGMA metadata_info;`, `PRAGMA extension_versions;` |
| Collations | `PRAGMA collations;` |
| Progress bar | `PRAGMA enable_progress_bar;`, `PRAGMA disable_progress_bar;`, `PRAGMA enable_print_progress_bar;` |
| Profiling | `PRAGMA enable_profiling;` / `PRAGMA disable_profiling;` (also `enable_profile`) |
| Optimizer | `PRAGMA disable_optimizer;`, `PRAGMA enable_optimizer;`, `SET disabled_optimizers = 'filter_pushdown,statistics_propagation';` (debugging only) |
| Checkpointing | `PRAGMA force_checkpoint;`, `PRAGMA enable_checkpoint_on_shutdown;`, `PRAGMA disable_checkpoint_on_shutdown;`, `SET checkpoint_on_detach = 'ENABLED';` (new in 2.0) |
| Compression | `SET force_compression = 'bitpacking';`, `SET disabled_compression_methods = 'fsst,rle';` |

Profiling configuration:

```sql
SET enable_profiling = 'json';                 -- or 'query_tree', 'query_tree_optimizer', 'no_output'
SET profiling_output = '/path/to/file.json';   -- overwritten on every query
SET profiling_coverage = 'ALL';
SET tracked_metrics = ['query.*', 'operator.*'];   -- new in 2.0 (json/no_output only)
SET explain_output = 'all';                    -- 'physical_only' / 'optimized_only'
```

`profiling_mode` is deprecated in 2.0 and has no effect; `tracked_metrics` replaces the old `custom_profiling_settings`. See [DESCRIBE, SHOW, SUMMARIZE, EXPLAIN/Profiling](../sql/statements/inspection-and-metadata.md).

Other useful settings:

```sql
SET default_null_order = 'NULLS_LAST_ON_ASC_FIRST_ON_DESC';
SET order_by_non_integer_literal = true;   -- otherwise: Binder Error: ORDER BY non-integer literal has no effect.
SET temp_directory = '/path/to/temp_dir.tmp/';
SET errors_as_json = true;
SET default_block_size = '16384';           -- power of two, 16384..262144
```

**Division by zero (changed in 2.0):** integer division by zero (`1 // 0`, `1 % 0`, `INTERVAL '1' DAY / 0`) errors by default. `SET error_on_division_by_zero = false;` restores 1.x `NULL` results but is deprecated — prefer `TRY(1 // 0)`. `SET ieee_floating_point_ops = false;` changes floating-point semantics.

## Logging

```sql
SET logging_storage = 'memory';     -- CLI default shell_log_storage prints but is not queryable
SET enable_logging = true;
SET logging_level = 'debug';
SELECT write_log('A new client has connected.', level := 'debug', scope := 'connection');
SELECT * FROM duckdb_logs WHERE log_level = 'DEBUG';
```

## SQL variables: `SET VARIABLE`

SQL-level variables are visible only in the current session and are not persisted.

```sql
SET VARIABLE my_var = 30;
SELECT 20 + getvariable('my_var') AS total;   -- 50
SELECT 20 + $my_var AS total;                 -- $name shorthand, new in 2.0
SET VARIABLE my_map = MAP {'k1': 10, 'k2': 20};
SET VARIABLE list_of_files = (SELECT list(file) FROM csv_files);
SELECT * FROM read_csv(getvariable('list_of_files'), filename := True);
SELECT COLUMNS(lambda c: c != getvariable('column_to_exclude')) FROM tbl;
RESET VARIABLE my_var;
SHOW VARIABLES;                               -- also duckdb_variables()
```

- Setting an existing variable overwrites it; variables can hold any type, including query results.
- `getvariable('undefined_var')` returns `NULL`, but `$undefined_var` **raises** `Values were not provided for the following parameters: undefined_var`, because `$name` is a prepared-statement parameter filled from the session variable (so variables also act as default parameter values).
- Non-identifier names can be quoted: `$"my var"`.
