---
type: concept
title: Connecting, Persistence and Concurrency
description: How to open in-memory and persistent DuckDB databases, storage-format compatibility with DuckDB 2.0, read-only access, the CONNECT/DISCONNECT statements for remote databases (new in 2.0), and DuckDB's concurrency model — one writer process, MVCC with optimistic concurrency control within it, Quack or DuckLake for multi-process writes, and transaction conflicts.
tags: [connect, persistence, in-memory, concurrency, mvcc, optimistic-concurrency, quack, read-only]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-b67f54eb3afd1e0cbe3eaeb9
    resource: repo://docs/2.0/connect/concurrency.md
  - id: openwiki-source-52e3ac31fabb68c3b1ecbd4c
    resource: repo://docs/2.0/connect/overview.md
  - id: openwiki-source-a32fe00873f421c15f58c66d
    resource: repo://docs/2.0/sql/statements/connect.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Connecting, Persistence and Concurrency

DuckDB is an in-process database: each client opens a database file (or an in-memory database) inside its own process. Exact syntax differs per client (CLI: `duckdb my_database.duckdb`; Python: `duckdb.connect("file.db")` — see [CLI Client](../clients/cli/overview-and-arguments.md) and [Python Client](../clients/python/getting-started.md)), but every client takes an argument that controls persistence. Since DuckDB 1.5.3 the **Quack protocol** can also run DuckDB as a server, and DuckDB 2.0 adds the **`CONNECT`** statement to route queries to a remote instance.

## Persistence

### Persistent databases

Pass a file path, such as `my_database.duckdb`. If the file exists it is opened; otherwise it is created. Any extension works; `.db`, `.duckdb` and sometimes `.ddb` are common.

- Since v0.10 the storage format is backwards-compatible: newer DuckDB versions read files written by older ones.
- **DuckDB versions before 2.0 cannot read files created by DuckDB 2.0** (new files use the latest storage version by default). To keep files readable by 1.5, attach with `STORAGE_VERSION 'v1.5.0'` or set `storage_compatibility_version` — see [ATTACH, DETACH, USE and Multiple Databases](attach-and-multiple-databases.md) and the migration notes in [Installation, Migration and Footprint](../operations/installation-migration-and-footprint.md).

### In-memory databases

Pass the special value `:memory:` or omit the database argument. Nothing is persisted; all data is lost when the process ends.

Both persistent and in-memory databases **spill to disk** for larger-than-memory workloads (out-of-core processing); see [File Formats, Bulk Import, Huge Databases and Out-of-Memory](../performance/file-formats-and-large-data.md).

### Read-only access

Open a database read-only with `access_mode = 'READ_ONLY'` (CLI `-readonly`, Python `read_only=True`, `ATTACH ... (READ_ONLY)`). A read-only open does not create a missing file.

## Concurrency model

### Single process

In in-process mode there are two configurations:

1. **Read-write mode:** one process can both read and write the database.
2. **Read-only mode:** multiple processes can read, but no process can write (`access_mode = 'READ_ONLY'`).

In read-write mode, DuckDB supports **multiple writer threads** within that single writer process, using MVCC (multi-version concurrency control) plus optimistic concurrency control. This model lets DuckDB cache data in RAM, together with function pointers and the catalog, so analytical queries do not go back and forth to disk.

Rules within one process:

- As long as there are no write conflicts, concurrent writes succeed.
- **Appends never conflict**, even on the same table.
- Threads can update separate tables or separate subsets of the same table simultaneously.
- If two threads edit (update or delete) the **same row** at the same time, the second fails with a conflict error.

In client APIs, give each thread its own connection (e.g. Python `con.cursor()`), because a single connection serves one call at a time.

### Multiple processes

Writing to DuckDB's native format from multiple processes is supported through the **Quack remote protocol**, which turns DuckDB into a client-server database. DuckDB 2.0 ships a polished version of Quack (first released in 1.5.3) with substantial performance and stability improvements. Start a server from the CLI with `duckdb analytics.duckdb -serve` and connect with `duckdb -connect`.

Alternatively, use the **DuckLake** format with PostgreSQL as the catalog database; coordinating through a central catalog lets DuckDB instances read and write the same database concurrently. DuckLake 1.1, intended for production use, was released alongside DuckDB 2.0.

### Optimistic concurrency control

Optimistic concurrency control is considered the best fit for read-intensive analytical systems because it speeds up reads. Transactions that modify the same rows at the same time cause:

```console
Transaction conflict: cannot update a table that has been altered!
```

The usual workaround is to **rerun the transaction**. Transaction statements are described in [Transactions, CHECKPOINT, VACUUM, ANALYZE](../sql/statements/transactions-and-maintenance.md).

### File locks

DuckDB coordinates access with file locks. Be careful with database files in shared directories, for example when accessed from different operating systems with different file systems, or on network-attached storage.

## `CONNECT` and `DISCONNECT` (new in DuckDB 2.0)

`CONNECT` routes the current session to a remote database: subsequent queries execute remotely and results stream back. `DISCONNECT` returns to the local database (and errors if no connection is active).

```sql
CONNECT { ⟨attached_database⟩ | '⟨connection_string⟩' };
DISCONNECT;
```

Attach a DuckDB server over Quack, route queries there, then disconnect:

```sql
ATTACH 'quack:server.example.com' AS qk (TOKEN '⟨my_token⟩');
CONNECT qk;
SELECT count(*) FROM events;   -- executes on the server, results stream back
DISCONNECT;
```

Connect directly with a connection string; non-DuckDB strings start with the database type, e.g. `postgres:` followed by a libpq connection string:

```sql
CONNECT 'postgres:dbname=mydb host=localhost';
SELECT count(*) FROM orders;   -- runs on the PostgreSQL server
DISCONNECT;
```

- While connected, queries that do not explicitly qualify another database run on the remote.
- Supported targets: DuckDB servers over Quack, and PostgreSQL and MySQL servers (for these, the remote pushdown optimizer ships SQL to the server instead of pulling tables).
- In-process local databases (the default in-memory database or a DuckDB file) do **not** support `CONNECT`.
- External resources: `CONNECT TO NEW TEMPORARY EXTERNAL RESOURCE ⟨type⟩ [(...)]` provisions a resource for this connection (torn down by `DISCONNECT`), and `CONNECT TO EXTERNAL RESOURCE ⟨name⟩ [(...)]` uses an existing registration. Both are refused when `enable_external_access` is `false` (see [Extensions](../configuration/extensions.md)).

In the CLI, the prompt shows the remote name while connected, and the first `Ctrl`+`D` disconnects (see [CLI Interactive Features](../clients/cli/interactive-features.md)).
