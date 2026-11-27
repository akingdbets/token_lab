---
type: reference
title: ATTACH, DETACH, USE and Multiple Databases
description: Work with several databases in one DuckDB session — ATTACH options (READ_ONLY, TYPE, BLOCK_SIZE, ROW_GROUP_SIZE, STORAGE_VERSION, ENCRYPTION_KEY, RECOVERY_MODE), remote and encrypted databases, attaching Parquet/CSV/JSON files, DETACH, USE, name qualification and search_path, single-database write transactions, copying an in-memory database to a file, and read_duckdb.
tags: [attach, detach, use, multiple-databases, encryption, storage-version, read-duckdb, search-path]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-0bcde8792332650b33b3c8f3
    resource: repo://docs/2.0/guides/file_formats/read_duckdb.md
  - id: openwiki-source-b8ded95e91ab7aedd3df61fd
    resource: repo://docs/2.0/sql/statements/alter_database.md
  - id: openwiki-source-33b84ccac13f402e765aa63b
    resource: repo://docs/2.0/sql/statements/attach.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# ATTACH, DETACH, USE and Multiple Databases

A DuckDB session can work with many databases at once: native DuckDB files, in-memory databases, SQLite/PostgreSQL/MySQL databases (via extensions), and even data files. How the initial database is opened is covered in [Connecting, Persistence and Concurrency](connecting-and-concurrency.md).

## `ATTACH` examples

```sql
ATTACH 'file.db';                                  -- alias inferred from the name: file
ATTACH 'file.db' AS file_db;
ATTACH 'file.db' (READ_ONLY);
ATTACH 'file.db' (BLOCK_SIZE 16_384);
ATTACH 'file.db' (ROW_GROUP_SIZE 2048);
ATTACH 'file.db' (RECOVERY_MODE no_wal_writes);    -- faster, but no crash recovery
ATTACH 'sqlite_file.db' AS sqlite_db (TYPE sqlite);
ATTACH IF NOT EXISTS 'file.db' AS file_db;
ATTACH OR REPLACE 'file2.db' AS file_db;           -- detach and replace existing alias
CREATE TABLE file.new_table (i INTEGER);
DETACH file;
SHOW DATABASES;
USE file;
```

Attachments are **not persisted** between sessions: re-attach databases after starting a new session.

### Options

Option values may be given with or without quotes and may be arbitrary expressions.

| Name | Description | Default |
| --- | --- | --- |
| `READ_ONLY` | Read-only mode (`READ_WRITE` for read-write) | `false` |
| `COMPRESS` | Compress an in-memory database | `false` |
| `TYPE` | `DUCKDB`, `SQLITE`, `POSTGRES`, `MYSQL`, …; deduced from the path if omitted | `DUCKDB` |
| `DEFAULT_TABLE` | Table queried when the catalog name is used directly (`FROM ⟨db⟩`) | – |
| `BLOCK_SIZE` | Block size of a **new** file; power of two in [16384, 262144] | `262144` |
| `ROW_GROUP_SIZE` | Row group size of a new file | `122880` |
| `STORAGE_VERSION` | Storage format version | `latest` |
| `ENCRYPTION_KEY` | Encryption key | – |
| `ENCRYPTION_CIPHER` | `CBC`, `CTR` or `GCM` | – |
| `RECOVERY_MODE` | `no_wal_writes` disables WAL writes | – |

Databases of other systems accept extra type-specific options such as `SECRET` and `SCHEMA` (credentials are managed with the [Secrets Manager](../configuration/secrets-manager.md)).

**Type deduction** when `TYPE` is omitted: (1) a scheme prefix such as `sqlite:file.db`, `postgres:dbname=postgres` or `mysql:db=mysql` selects the type (at least two characters, not followed by `//`, so `https://…` is not a prefix); (2) otherwise the file header decides (SQLite header → `SQLITE`, DuckDB file → `DUCKDB`). Passing `TYPE DUCKDB` explicitly disables deduction, so a scheme prefix would then be ignored.

### Remote databases

HTTP(S) and S3 endpoints are attached **read-only by default**:

```sql
ATTACH 'https://blobs.duckdb.org/databases/stations.duckdb' AS stations_db;
ATTACH 's3://⟨blobs-duckdb⟩/databases/stations.duckdb' AS stations_db (READ_ONLY);   -- equivalent
```

### Storage versions

`STORAGE_VERSION` (introduced in 1.2.0) sets the minimum DuckDB version able to read the file. **Since DuckDB 2.0.0, new files use the latest storage version by default**, so older versions cannot read them. To stay readable by 1.5:

```sql
ATTACH 'file.db' (STORAGE_VERSION 'v1.5.0');
SELECT database_name, tags FROM duckdb_databases();   -- shows the storage version
```

### Encryption

Encryption uses AES-256 in GCM mode by default and covers the database file, the WAL and temporary files. It requires storage version 1.4.0 or later. Loading `httpfs` lets DuckDB use OpenSSL (hardware-accelerated, much faster) instead of the built-in `mbedtls`.

```sql
LOAD httpfs;
ATTACH 'encrypted.db' AS enc_db (ENCRYPTION_KEY 'quack_quack');
ATTACH 'encrypted.db' AS enc_db (ENCRYPTION_KEY 'quack_quack', ENCRYPTION_CIPHER 'CTR');
```

### Expressions in paths (new in DuckDB 2.0)

The path and option values can be scalar expressions evaluated at bind time (the path must not be `NULL`):

```sql
SET VARIABLE db_path = 'file.db';
ATTACH getvariable('db_path') AS file_db;
SET VARIABLE account_id = '123456789012';
ATTACH 'account_' || getvariable('account_id') || '.db' AS account_db;
ATTACH getenv('DATABASE_PATH') AS env_db;           -- getenv: CLI only
```

### Attaching data files

Parquet, CSV or JSON files can be attached directly. The database exposes two read-only views, `file` and one named after the alias, both defined as `SELECT * FROM '⟨path⟩'` (re-read on each query):

```sql
ATTACH 'people.parquet' AS people;
SELECT * FROM people.file;
SELECT * FROM people.people;
```

### `ATTACH TO EXTERNAL RESOURCE` (new in DuckDB 2.0.0)

```sql
ATTACH TO NEW TEMPORARY EXTERNAL RESOURCE ⟨type⟩ [(⟨create_option⟩ ...)] AS ⟨alias⟩ [(⟨attach_option⟩ ...)];
ATTACH TO EXTERNAL RESOURCE ⟨name⟩ AS ⟨alias⟩ [(⟨attach_option⟩ ...)];
```

The first provisions a resource just for this attachment (torn down by `DETACH`); the second attaches an existing registration. Both are refused when `enable_external_access` is `false`. See [Extensions: External Resources](../configuration/extensions.md).

## `DETACH`

`DETACH` closes an attached database and releases its file locks. You cannot detach the default database — switch first:

```sql
ATTACH ':memory:' AS memory_db;
USE memory_db;
```

Closing a client connection (e.g. Python `close()`) does **not** release file locks, because the file handles belong to the DuckDB instance.

## `ALTER DATABASE`

> **Warning:** `ALTER DATABASE ⟨old_name⟩ RENAME TO ⟨new_name⟩` is **not supported in DuckDB 2.0.0**; it fails with `Parser Error: syntax error at or near "RENAME"`. To rename, `DETACH` and `ATTACH` again with a different alias.

## `USE`, name qualification and the search path

Fully qualified names are `catalog.schema.name`:

```sql
ATTACH 'new_db.db';
CREATE SCHEMA new_db.my_schema;
CREATE TABLE new_db.my_schema.my_table (col INTEGER);
SELECT new_db.my_schema.my_table.col FROM new_db.my_schema.my_table;
```

Unqualified tables go into the default schema (`main`) of the default database. `USE` changes the default:

```sql
USE memory;          -- database; 'main' schema implicitly
USE duck.main;       -- database and schema
USE main;            -- schema of the currently selected database
```

A single qualifier may be a catalog or a schema. If both exist with the same name, DuckDB raises `Binder Error: Ambiguous reference to catalog or schema "new_db" - use a fully qualified path like "memory.new_db"`. The search path (system catalog, temp catalog, initial database's `main`) can be changed:

```sql
ATTACH ':memory:' AS db1;
ATTACH ':memory:' AS db2;
SET search_path = 'db1,db2';
SELECT * FROM tbl1;
```

## Transactions across databases

DuckDB opens a separate transaction per database, lazily on first reference (`SET immediate_transaction_mode = true` starts them at `BEGIN`). A single transaction may **write to only one attached database**:

```console
Attempting to write to database "db2" in a transaction that has already modified database "db1" -
a single transaction can only write to a single attached database.
```

Atomicity is only guaranteed within each database file. See [Transactions, CHECKPOINT, VACUUM](../sql/statements/transactions-and-maintenance.md).

## Copying an in-memory database to a file

```sql
ATTACH 'my_database.db';
COPY FROM DATABASE memory TO my_database;
DETACH my_database;
```

Make sure the target file does not exist beforehand. See [COPY and EXPORT/IMPORT DATABASE](../sql/statements/copy-and-export.md).

## Reading DuckDB files with `read_duckdb`

`read_duckdb(path, table_name = ...)` attaches read-only, reads one table, and closes the database. Globs read several databases; `table_name` is optional if each has a single table; `.db`/`.duckdb` files can be queried directly. Only tables (not views) are supported.

```sql
SELECT r_regionkey, r_name
FROM read_duckdb('https://blobs.duckdb.org/data/tpch-sf10.db', table_name = 'region');
SELECT x FROM read_duckdb('my-*.duckdb', table_name = 'numbers');
FROM 'my-2.duckdb';
```
