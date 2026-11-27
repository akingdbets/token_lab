---
type: guide
title: "CLI Client: Installation, Usage and Command-Line Arguments"
description: How to install and run the DuckDB 2.0.1 command line client, open in-memory or persistent databases, configure it with ~/.duckdbrc and -init, run it non-interactively, pipe via stdin/stdout, read environment variables with getenv, serve/connect remote databases (new in 2.0), and the full list of command-line arguments.
tags: [cli, installation, arguments, duckdbrc, stdin, getenv, quack, serve, connect]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-4a6e14656280b8ba1457feea
    resource: repo://docs/2.0/clients/cli/arguments.md
  - id: openwiki-source-9a2108c5dc5a35f2893d3271
    resource: repo://docs/2.0/clients/cli/overview.md
  - id: openwiki-source-cacbeb4d030b15a692160a3f
    resource: repo://docs/2.0/guides/troubleshooting/command_line.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# CLI Client: Installation, Usage and Command-Line Arguments

The DuckDB CLI is a single, dependency-free executable, precompiled for Windows, macOS and Linux (stable and nightly builds). The latest stable version documented here is **DuckDB 2.0.1**. The shell is based on the SQLite command line shell, but DuckDB's SQL follows PostgreSQL conventions (see [SQL Introduction, Dialect and PostgreSQL Compatibility](../../sql/dialect/introduction-and-compatibility.md)). `tldr duckdb` shows a summary of common uses.

## Installation

Download the binary from the installation page, decompress it into any directory and run `duckdb` (or `./duckdb` in PowerShell/POSIX shells). See also [Installation, Requirements, Docker, Migration](../../operations/installation-migration-and-footprint.md) for the install script.

The CLI is also a Python package:

```bash
pip install duckdb-cli
duckdb
```

The package also installs the command `duckdb-cli`, so `uvx duckdb-cli` runs it with nothing installed. Extensions are extras: `pip install "duckdb-cli[httpfs]"` installs `httpfs` into the environment so `LOAD httpfs` needs no download.

## Basic usage

```batch
duckdb ⟨OPTIONS⟩ ⟨FILENAME⟩
```

- Without `FILENAME`, the CLI opens a temporary [in-memory database](../../connect/connecting-and-concurrency.md); the prompt shows `«memory» D`.
- With a path, it opens or creates a persistent database: `duckdb my_database.duckdb`.

```text
DuckDB v2.0.1 (Cyanoptera)
Enter ".help" for usage hints.
«memory» D
```

Enter SQL followed by `;` and press Enter; without a semicolon, Enter continues a multi-line statement. Exit with `Ctrl`+`D` (or `Ctrl`+`C` / `.exit`). When connected to a remote database via `CONNECT`, the first `Ctrl`+`D` disconnects back to the local database; a CLI started with `-connect` exits on the first `Ctrl`+`D`. A persistent database is checkpointed automatically on exit.

### Opening databases with `.open`

`.open` closes the current database and opens another (in-memory if no path; `:memory:` also works). To keep the current database while adding another, use [`ATTACH`](../../connect/attach-and-multiple-databases.md).

```text
.open persistent.duckdb
.open --readonly preexisting.duckdb
.open --sql "getenv('MY_DB_PATH')"
```

Read-only mode requires an existing database, so an in-memory database cannot be opened read-only.

### Running scripts with `.read`

`.read FILE` executes SQL and dot commands from a file, then returns control to the terminal; output follows `.output`/`.once`:

```sql
-- write_markdown_to_file.sql
.mode markdown
.output series.md
SELECT *
FROM generate_series(5);
```

```text
.read write_markdown_to_file.sql
```

## Configuring the CLI: `~/.duckdbrc` and `-init`

On startup the CLI executes every command (dot commands and SQL) in `~/.duckdbrc`. Use `-init FILENAME` to run a different file instead, or `-no-init` to skip it.

```text
.prompt "{color:yellow1}{sql:select current_database()} ⚫◗ "
```

```batch
duckdb -init prompt.sql
```

The CLI reads and writes `~/.duckdbrc`, `~/.duckdb_history` and the extension directory `~/.duckdb/extensions`. If the home directory is missing or not writable, startup can fail with `IO Error: Failed to create directory`; in sandboxes set `HOME` to a writable location.

## Non-interactive usage

```batch
duckdb < select_example.sql
duckdb :memory: "SELECT 42 AS the_answer"
duckdb -c "SELECT 42"
```

### Piping through stdin and stdout

On Unix, use `/dev/stdin` and `/dev/stdout` as file locations:

```sql
COPY (SELECT 42 AS woot UNION ALL SELECT 43 AS woot) TO 'test.csv' (HEADER);
```

```batch
cat test.csv | duckdb -c "SELECT * FROM read_csv('/dev/stdin')"
cat test.csv | \
    duckdb -c "COPY (SELECT * FROM read_csv('/dev/stdin')) TO '/dev/stdout' WITH (FORMAT csv, HEADER)"
```

**Troubleshooting:** if output is piped and an AI agent variable such as `AI_AGENT` is set, the CLI switches to [agent mode](interactive-features.md#agent-mode-new-in-duckdb-20) and prints compact Markdown tables (`| x:INTEGER |`). Disable it with `-no-agent`, `DUCKDB_AGENT_MODE=0`, or an explicit output-mode flag such as `-csv` or `-json`:

```bash
echo "SELECT 42 AS x;" | duckdb -no-agent | cat
```

## Environment variables with `getenv`

```sql
SELECT getenv('HOME') AS home;
SET default_null_order = getenv('DEFAULT_NULL_ORDER');
```

`getenv` works only when `enable_external_access` is `true` (the default), and is available **only in the CLI client** (it is disabled in safe mode).

## Other CLI features

- Extensions load with ordinary SQL: `INSTALL fts; LOAD fts;` (see [Extensions](../../configuration/extensions.md)).
- Prepared statements via `PREPARE` and `EXECUTE` (see [prepared statements](../../sql/query-syntax/select-from-where.md)).
- **Query completion ETA:** the progress bar shows an estimated remaining time computed with a Kalman filter over the progress API, and the total execution time on completion. Estimates may rise rather than fall linearly and are less reliable under memory pressure, CPU or I/O contention, remote/network sources, external function calls or skewed data.

## Command-line arguments

`duckdb -help` lists all options. Arguments are processed **in order**:

```batch
duckdb -csv -c 'SELECT 42 AS hello' -json -c 'SELECT 84 AS world'
```

```text
hello
42
[{"world":84}]
```

Exception: the `-init` script (or `~/.duckdbrc`) always runs at startup before any `-cmd`, `-c` or `-s` command, so `-cmd` cannot inject configuration that the init script depends on — put that configuration at the top of the init script.

| Argument | Description |
| --- | --- |
| `-agent` / `-no-agent` | Force agent-mode output on / off |
| `-ascii`, `-box`, `-column`, `-csv`, `-html`, `-json`, `-jsonlines`, `-line`, `-list`, `-markdown`, `-quote`, `-table` | Set the output mode |
| `-bail` | Stop after hitting an error |
| `-batch` / `-interactive` | Force batch / interactive I/O |
| `-cmd COMMAND` | Run `COMMAND` before reading stdin |
| `-c COMMAND`, `-s COMMAND` | Run `COMMAND` and exit |
| `-connect [TYPE[:SECRET]]` | Connect to a remote database; default type `quack` |
| `-dark-mode` / `-light-mode` | Highlighting color scheme |
| `-echo` | Print commands before execution |
| `-f FILENAME` | Run the script and exit (`~/.duckdbrc` is executed first if it exists) |
| `-format` / `-format-file FILENAME` | Format SQL from stdin / a file to stdout |
| `-init FILENAME` | Run `FILENAME` at startup instead of `~/.duckdbrc` |
| `-no-init` | Skip the init file |
| `-header` / `-noheader` | Headers on / off |
| `-h`, `-help` | Help message |
| `-manual FUNCTION` | Show a function's manual page and exit |
| `-newline SEP` | Row separator. Default: `\n` |
| `-no-stdin` | Exit after processing options |
| `-nullvalue TEXT` | Text for `NULL`. Default: `NULL` |
| `-readonly` | Open read-only; also supports attaching remote databases via HTTPS |
| `-safe` | Enable [safe mode](interactive-features.md#safe-mode) |
| `-separator SEP` | Column separator. Default: `\|` |
| `-serve [quack[:SECRET]]` | Serve the opened database with Quack |
| `-storage-version VER` | Storage compatibility version; `-storage-version latest` for the newest |
| `-ui` | Load and start the DuckDB UI (installs the `ui` extension if needed) |
| `-unredacted` | Allow printing unredacted secrets (sets `allow_unredacted_secrets = true`) |
| `-unsigned` | Allow loading unsigned extensions (for extension development; see [Securing DuckDB](../../operations/security.md)) |
| `-version` | Show the DuckDB version |

## Serving and connecting to remote databases (new in 2.0)

`-serve` starts a Quack server for the opened database; by default it serves an in-memory database on `localhost:9494`. `-connect` connects to `localhost:9494` using the default `quack` secret, which `-serve` creates as a persistent secret if missing, so both work together on one machine without setup:

```batch
duckdb analytics.duckdb -serve
duckdb -connect
duckdb analytics.duckdb -serve quack:analytics
duckdb -connect quack:analytics
```

Only the `quack` type can be served. `-connect` cannot be combined with a local database path. By default `-serve` calls `quack_serve` and `-connect` runs a [`CONNECT`](../../connect/connecting-and-concurrency.md) statement; customize them with `.serve_command` / `.connect_command`.
