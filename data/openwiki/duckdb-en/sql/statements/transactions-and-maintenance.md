---
type: reference
title: Transactions, CHECKPOINT, VACUUM, ANALYZE and Reclaiming Space
description: DuckDB transaction statements (BEGIN TRANSACTION, COMMIT, ROLLBACK/ABORT), auto-commit behavior of multi-statement batches, snapshot isolation; CHECKPOINT and FORCE CHECKPOINT including in-memory checkpointing; VACUUM's limited semantics and index-aware vacuuming (new in 2.0); ANALYZE for join-order statistics; and how to reclaim disk space after deletes.
tags: [sql, transactions, acid, checkpoint, vacuum, analyze, wal, disk-space, maintenance]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-9dc961c6066efa7823ffd06c
    resource: repo://docs/2.0/operations_manual/footprint_of_duckdb/reclaiming_space.md
  - id: openwiki-source-d2af2eec6632375f7e50f847
    resource: repo://docs/2.0/sql/statements/analyze.md
  - id: openwiki-source-3ed76970d34dfa372a76c144
    resource: repo://docs/2.0/sql/statements/checkpoint.md
  - id: openwiki-source-b23719872372b9910dc1e7c5
    resource: repo://docs/2.0/sql/statements/transactions.md
  - id: openwiki-source-8b774a9f73336ed50ede976b
    resource: repo://docs/2.0/sql/statements/vacuum.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Transactions, CHECKPOINT, VACUUM, ANALYZE and Reclaiming Space

Concurrency between processes and connections is described on [Connecting and Concurrency](../../connect/connecting-and-concurrency.md); database file size on [Installation, Migration and Footprint](../../operations/installation-migration-and-footprint.md).

## Transactions

DuckDB supports ACID transactions. Changes in a transaction are invisible to concurrent transactions until committed, and aborting discards them.

```sql
BEGIN TRANSACTION;
COMMIT;            -- make changes visible and persist them (in persistent mode)
ROLLBACK;          -- discard changes
ABORT;             -- identical to ROLLBACK
```

`COMMIT`, `ROLLBACK` and `ABORT` fail outside an active transaction.

```sql
CREATE TABLE person (name VARCHAR, age BIGINT);

BEGIN TRANSACTION;
INSERT INTO person VALUES ('Ada', 52);
COMMIT;

BEGIN TRANSACTION;
DELETE FROM person WHERE name = 'Ada';
INSERT INTO person VALUES ('Bruce', 39);
ROLLBACK;

SELECT * FROM person;     -- only ('Ada', 52)
```

- **Multi-statement batches** (statements separated by semicolons) run in **auto-commit** mode: each successful statement commits immediately and execution stops at the first failure — earlier statements are **not** rolled back. Wrap the batch in `BEGIN TRANSACTION` … `COMMIT` to make it atomic.
- **Isolation:** DuckDB guarantees snapshot isolation (PostgreSQL's *repeatable read*); transactions that would violate it are aborted.
- Bulk loading in a loop should also use explicit transactions (see [Modifying Data](modifying-data.md)). Deferred `PRIMARY KEY`/`UNIQUE` constraints are checked at `COMMIT` (see [Constraints](create-and-alter-tables.md)).

## `CHECKPOINT`

`CHECKPOINT` synchronizes the write-ahead log (WAL) into the database file. Checkpoints happen automatically based on WAL size (the `checkpoint_threshold` setting, see [Settings](../../configuration/settings-and-pragmas.md)); the statement is for manual checkpoints.

```sql
CHECKPOINT;                 -- default database
CHECKPOINT file_db;         -- a specific attached database
FORCE CHECKPOINT;           -- wait for the checkpoint lock, block new transactions
```

- Plain `CHECKPOINT` **fails if transactions are running**. `FORCE CHECKPOINT` waits until it can grab the checkpoint lock (since v1.4; earlier versions aborted in-progress transactions).
- **In-memory checkpointing (since v1.4.0):** in-memory databases also checkpoint, which vacuums deleted rows and enables compression (off by default):

```sql
ATTACH ':memory:' AS memory_compressed (COMPRESS);
USE memory_compressed;
```

## `VACUUM`

`VACUUM` has only basic support, mostly for PostgreSQL compatibility; its semantics differ from PostgreSQL and are likely to change.

```sql
VACUUM;                                   -- no-op
VACUUM ANALYZE;                           -- no-op
VACUUM my_table(my_column);               -- rebuild statistics for the column
VACUUM ANALYZE my_table(my_column);
VACUUM FULL;                              -- Not implemented Error: FULL is not yet implemented
```

**`VACUUM` does not reclaim space** — it does not vacuum deletes.

**Index-aware vacuuming (new in DuckDB 2.0):** when a checkpoint compacts row groups, the moved rows' row IDs change. With storage version 2.0.0 or later, DuckDB remaps ART index entries incrementally, so tables with ART indexes (including those from `PRIMARY KEY` and `UNIQUE`) are vacuumed by default without a full index rebuild. With older storage versions, indexed tables are skipped; the deprecated `vacuum_rebuild_indexes` setting (a max row count up to which indexes are rebuilt; default `0` = disabled) is a fallback, settable only before startup or as an `ATTACH` option.

## `ANALYZE`

`ANALYZE` recomputes table statistics, which are used **only for join order optimization**. Run it after large inserts or deletes to improve join orders:

```sql
ANALYZE;
```

## Reclaiming disk space

DuckDB's single-file format limits space reclamation:

- **Deleted rows** are only marked as deleted. A checkpoint (automatic or manual) partially reclaims their space by merging row groups with many deletes — currently this requires about **25% of rows deleted in adjacent row groups**. It does not remove all deleted rows.
- **`DROP TABLE`** frees blocks for reuse, but the file may not shrink (check `free_blocks` with `PRAGMA database_size;`).
- **To compact a file**, copy it into a fresh database:

```sql
ATTACH 'db1.db' AS db1;
ATTACH 'db2.db' AS db2;
COPY FROM DATABASE db1 TO db2;
```

See [COPY and EXPORT/IMPORT DATABASE](copy-and-export.md) for `COPY FROM DATABASE` and `EXPORT DATABASE`.
