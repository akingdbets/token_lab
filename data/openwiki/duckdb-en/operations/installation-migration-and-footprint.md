---
type: guide
title: Installation, Requirements, Docker, Migration, Limits, Files and Logging
description: Operational reference for DuckDB 2.0.1 — install script and supported platforms, Docker image, migrating to DuckDB 2.0 (storage format, lambda syntax, PEG parser, transaction errors, division by zero and other breaking changes), built-in limits, files DuckDB creates and .gitignore snippets, the logging framework, HTTP user agents, and handy snippets (synthetic data, database checksum, analyzing a Git log).
tags: [operations, installation, docker, migration, storage-format, limits, logging, files, gitignore]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-3df75589af6239617d2589e7
    resource: repo://docs/2.0/operations_manual/footprint_of_duckdb/files_created_by_duckdb.md
  - id: openwiki-source-676b9fca9827fdf3f9062105
    resource: repo://docs/2.0/operations_manual/installing_duckdb/install_script.md
  - id: openwiki-source-698416b631ceb5741af9b2ac
    resource: repo://docs/2.0/operations_manual/installing_duckdb/requirements.md
  - id: openwiki-source-f434e7585caf386f5f8a5f1c
    resource: repo://docs/2.0/operations_manual/limits.md
  - id: openwiki-source-61e31dc18e9268ebcd2a3298
    resource: repo://docs/2.0/operations_manual/logging/overview.md
  - id: openwiki-source-65af78f4090d65d2511ae0d3
    resource: repo://docs/2.0/operations_manual/migration.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Installation, Requirements, Docker, Migration, Limits, Files and Logging

DuckDB is designed to be easy to deploy; most users never need the operations manual. This page collects the operational facts for running **DuckDB 2.0.1**. Security hardening is on [Securing DuckDB](security.md), and problems on [Troubleshooting](troubleshooting.md).

## Installing

**Install script (Linux/macOS)** — installs the CLI to `~/.duckdb/cli/latest/duckdb` (a symlink to the versioned binary):

```bash
curl https://install.duckdb.org | bash
export PATH="~/.duckdb/cli/latest":$PATH                       # add to ~/.bashrc / ~/.zshrc
curl https://install.duckdb.org | DUCKDB_VERSION=1.2.2 bash     # past releases back to v1.0.0
curl https://install.duckdb.org | DUCKDB_INSTALL=static,cli bash   # new in 2.0: C/C++ libs
```

`DUCKDB_INSTALL` takes `cli` (default), `static` and `shared`; libraries go to `~/.duckdb/lib/⟨version⟩/release_⟨platform⟩`. **Windows (beta):**

```bash
powershell -NoExit -ExecutionPolicy Bypass -Command "irm https://install.duckdb.org/install.ps1 | iex"
```

Other channels: `pip install duckdb` (Python), `pip install duckdb-cli` (see [CLI](../clients/cli/overview-and-arguments.md)).

### Supported platforms

| Platform | OS | Architecture | Support |
| --- | --- | --- | --- |
| `linux_amd64` | Linux | x86_64 | Full |
| `linux_arm64` | Linux | AArch64 (Graviton, …) | Full |
| `osx_amd64` | macOS 12+ | x86_64 (Intel) | **Partial** — since 2.0.0 community extensions are best-effort |
| `osx_arm64` | macOS 12+ | Apple Silicon | Full |
| `windows_amd64` | Windows 10+ | x86_64 | Full |
| `windows_arm64` | Windows 10+ | ARM64 (Copilot+ PCs) | Full |

Linux binaries need **glibc 2.28 or newer** (built with `manylinux_2_28` since 1.3.0); build from source for older glibc. musl (Alpine), Android and WebAssembly work with varying support.

### Docker

The official image supports ARM64 and AMD64:

```batch
docker run --rm -it -v "$(pwd):/workspace" -w /workspace duckdb/duckdb
docker run --rm -it -v "$(pwd):/workspace" -w /workspace --net host duckdb/duckdb   # for the UI
```

Then `CALL start_ui();`. Host networking forwards all ports — avoid it in secure environments.

## Migrating to DuckDB 2.0

For mission-critical workloads consider waiting for patch releases; **DuckDB 1.5 support is extended until March 2027**, and **1.4 LTS reaches end of life on November 17, 2026**. Best practice: run a shadow system tracking the production workload.

| Change | What to do |
| --- | --- |
| **Storage format** (storage version 69): versions before 2.0 cannot read new files (`IO Error: Trying to read a database file with version number 69, but we can only read versions between 64 and 68.`). 2.0 reads/writes old files and keeps their version. | In mixed-version deployments upgrade every process first. Write compatible files with `-storage-version v1.5.6`, `storage_compatibility_version` or `ATTACH ... (STORAGE_VERSION ...)`. Convert: `EXPORT DATABASE` with the old version, `IMPORT DATABASE` with 2.0 (or `COPY FROM DATABASE`). |
| **Lambda syntax**: `x -> x + 1` disabled by default | Use `lambda x : x + 1`; temporary bridge `SET lambda_syntax = 'enable_single_arrow';` (removed in 2.1) |
| **PEG parser** replaces the PostgreSQL-derived parser | `~`/`!~` now partial-match (`'abc' ~ 'b'` is `true`; `SET regex_match_operator_semantics = 'full'` restores); `2 * 3!` is now `12`; `X'…'`/`B'…'` produce `BLOB`/`BITSTRING`. Old parser: `INSTALL AND LOAD legacy_parser; SET enable_legacy_parser = true;` |
| **Errors in transactions** abort the transaction (`Current transaction is aborted (please ROLLBACK)`) | Check first or run outside the transaction; or `SET default_transaction_invalidation_policy = 'SYNTACTIC_ERRORS_DO_NOT_INVALIDATE';` |
| **Integer division/modulo by zero** errors | `TRY(1 // 0)` or `SET error_on_division_by_zero = false`; `1 / 0` still returns `inf` |
| **`MERGE INTO`** matching a target row multiple times errors | Deduplicate the source or make `ON` unique |
| **Untyped `NULL`** keeps type `"NULL"` (`CREATE TABLE t AS SELECT NULL AS x`) | Cast (`NULL::VARCHAR`) or `SET legacy_disable_null_type = true;` |
| **`preserve_identifier_case`** is now `VARCHAR`: `'preserve_case'` (default), `'lowercase'`, `'uppercase'` | `true`/`false` still map to `'preserve_case'`/`'lowercase'` |
| **S3 URL parameters** (`?s3_access_key_id=...`) disabled | Use secrets, or `SET s3_enable_deprecated_url_parameters = true` |
| Removed settings | `custom_profiling_settings` → `tracked_metrics`; `enable_http_logging`/`http_logging_output` → `CALL enable_logging('HTTP')`; `profiling_mode` deprecated |
| ICU removed from the core build | Time zones, calendars and collations come from the `icu` extension; no query changes |
| C API v2 | More powerful but not yet stable |
| Python client | Python 3.11+ and API changes — see [Python Client: Getting Started](../clients/python/getting-started.md) |

New in 2.0 (documented elsewhere in this wiki): DuckDB as a server (`quack`, [`CONNECT`](../connect/connecting-and-concurrency.md)), the [`VARIANT` type](../sql/data-types/variant-and-geometry.md), [triggers](../sql/statements/views-macros-and-types.md), data-modifying CTEs and nested schemas, [asynchronous I/O](../data/overview-and-file-access.md), and self-hostable extension repositories.

## Limits

| Limit | Default | Setting |
| --- | --- | --- |
| Array size | 100000 | – |
| BLOB size / string size | 4 GB | – |
| Expression depth | 1000 | `max_expression_depth` |
| Memory allocation for a vector | 128 GB | – |
| Memory use | 80% of RAM (buffer manager only) | `memory_limit` |
| Temporary directory size | 90% of available disk space | `max_temp_directory_size` |

There is no practical limit on database file size — files of 15 TB+ work, though connecting may take seconds and checkpointing is slower.

## Files created by DuckDB

| Location | Purpose | Shared between versions / clients |
| --- | --- | --- |
| `~/.duckdbrc` | CLI startup commands | Yes / CLI only |
| `~/.duckdb_history` | CLI history | Yes / CLI only |
| `~/.duckdb/extensions` | Installed extension binaries | No / Yes |
| `~/.duckdb/stored_secrets` | Persistent secrets | Yes / Yes |
| `~/.duckdb/extension_repositories` | Custom repository definitions (`CREATE EXTENSION REPOSITORY`) | Yes (v2.0+) / Yes |
| `⟨database⟩` (e.g. `weather.duckdb`) | Database file (on-disk mode) | |
| `⟨database⟩.wal` | Write-ahead log; deleted on normal exit, needed for crash recovery | |
| `⟨database⟩.tmp/` or `.tmp/` | Temporary (spill) directory for on-disk / in-memory mode | |

`.gitignore` snippets: keep the database but ignore `*.wal` and `*.tmp/`; or ignore everything with `*.duckdb*`, `*.wal`, `*.tmp/`. Reclaiming space is covered in [Transactions, CHECKPOINT, VACUUM](../sql/statements/transactions-and-maintenance.md).

## Logging

> Logs may contain secrets and credentials; enable and share them with care.

```sql
CALL enable_logging(storage = 'memory');     -- CLI default storage 'shell_log_storage' is not queryable
SELECT * FROM duckdb_logs;
CALL enable_logging(level = 'debug');
CALL enable_logging(['HTTP', 'QueryLog']);
SELECT request.headers FROM duckdb_logs_parsed('HTTP');
CALL enable_logging(storage_path = 'path/to/store/logs');   -- file storage (CSV)
CALL truncate_duckdb_logs();
CALL disable_logging();
```

- Levels: `FATAL`, `ERROR`, `WARNING`, `INFO` (**default**), `DEBUG`, `TRACE`. Deprecation warnings are logged at `WARNING`.
- Storages: `memory` (default outside the CLI), `stdout` (CSV), `file`, `shell_log_storage` (CLI default; prints to console, cannot be queried).
- Log types: `QueryLog`, `FileSystem`, `HTTP`, `PhysicalOperator`, `Metrics` (all but `QueryLog` are structured; inspect with `DESCRIBE FROM duckdb_logs_parsed('HTTP')`).

## HTTP user agent

Core DuckDB sends `duckdb/v2.0.0(osx_arm64) cli` — version, platform and client API (`duckdb_api`, e.g. `cli`, `capi`, `cpp`). `custom_user_agent` is appended and can only be set at startup. Azure and Delta extensions add their own SDK user agents.

## Useful snippets

```sql
-- synthetic data
SELECT i FROM range(1, 4) t(i);                         -- range excludes stop; generate_series includes it
FROM repeat_row('placeholder', 0, num_rows = 3);
SELECT (random() * 100)::INTEGER AS score, uuidv7() AS id FROM range(3);
INSTALL tpch; LOAD tpch; CALL dbgen(sf = 0.1);

-- database checksum: commutative bit_xor over all columns of a table
CREATE OR REPLACE MACRO table_checksum(table_name) AS TABLE
    SELECT bit_xor(value) AS table_checksum
    FROM (UNPIVOT (SELECT bit_xor(md5_number(COLUMNS(*)::VARCHAR)) FROM query_table(table_name)) ON columns(*));

-- analyze a git log exported with a 4-byte delimiter
CREATE TABLE commits AS
    FROM read_csv('git-log.csv', delim = '🍥', header = false,
                  column_names = ['timestamp', 'hash', 'author', 'message']);
```

(`git log --date=iso-strict --pretty=format:%ad🍥%h🍥%an🍥%s > git-log.csv`; 4-byte delimiters are supported since v1.2.0.)
