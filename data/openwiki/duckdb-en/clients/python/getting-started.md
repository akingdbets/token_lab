---
type: guide
title: "Python Client: Installation, Connections, DB-API and Threads"
description: Install the duckdb Python package (2.0.1, Python 3.11+), run SQL with duckdb.sql and connections, use the DB-API (execute, fetch, parameters, transactions, open results), share work across threads with cursor(), use Jupyter/JupySQL, and migrate Python code from DuckDB 1.x to 2.0.
tags: [python, installation, dbapi, connections, threads, cursor, jupyter, migration]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-88e5a81043c82cb7b1102816
    resource: repo://docs/2.0/clients/python/dbapi.md
  - id: openwiki-source-f9426ed7b21139fb77c35e54
    resource: repo://docs/2.0/clients/python/known_issues.md
  - id: openwiki-source-05a8426e8bc36b48a8ce88b5
    resource: repo://docs/2.0/clients/python/migration.md
  - id: openwiki-source-4412b1f9c8387399bc9c870b
    resource: repo://docs/2.0/clients/python/overview.md
  - id: openwiki-source-c654388bef22a69c9e38e254
    resource: repo://docs/2.0/guides/python/install.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Python Client: Installation, Connections, DB-API and Threads

The latest stable DuckDB Python client is **2.0.1**. This page covers installation, connections, the DB-API, threading and notebooks. For reading data and converting results see [Python Data Ingestion and Conversion](dataframes-and-arrow.md); for the relation methods see [Python Relational API](relational-api.md).

## Installation

```batch
pip install duckdb
pip install duckdb --upgrade --pre     # preview/nightly build
```

or `conda install python-duckdb -c conda-forge`. DuckDB 2.0 **requires Python 3.11 or newer**; free-threaded CPython builds are not supported. On Python 3.10, `pip` does not error — it silently installs a 1.x release (with `--pre`, a 1.x dev build).

## Running SQL

```python
import duckdb

duckdb.sql("SELECT 42").show()
results = duckdb.sql("SELECT 42").fetchall()   # [(42,)]
r1 = duckdb.sql("SELECT 42 AS i")
duckdb.sql("SELECT i * 2 AS k FROM r1").show()  # relations can be queried by name
```

`duckdb.sql()` runs on a global in-memory database created by the first call that needs it, and returns a **relation**. A read-only query runs when its result is fetched or displayed, and again every time it is read. Statements that change data or schema (`CREATE TABLE`, `INSERT`) run when `sql` is called; prefer `execute()` for DDL/DML. Write results with `write_parquet("out.parquet")`, `write_csv("out.csv")` or `COPY`.

### Query parameters

```python
con.execute("SELECT * FROM integers WHERE i = ?", [42]).fetchall()
con.execute("SELECT * FROM integers WHERE i = $value", {"value": 42}).fetchall()
con.sql("SELECT * FROM integers WHERE i = $value", params={"value": 42}).fetchall()
con.execute("SELECT $1, $1, $2", ["duck", "goose"])          # $1 reuses a list value
con.executemany("INSERT INTO integers VALUES (?)", [[1], [2], [3]])   # con.rowcount == 3
```

Parameterized queries run as prepared statements. Parameter names are case-insensitive (`"ABC"` binds `$abc`). The `params` container of `sql()` is copied at call time, but other values are converted each time the relation is read. Do **not** use `executemany` for large inserts — use the [appender](expressions-udfs-and-types.md#the-python-appender) or DataFrame ingestion.

## Connections

`duckdb.connect(database, read_only, config)`:

| `database` value | Result |
| --- | --- |
| omitted or `:memory:` | New, separate in-memory database |
| `:memory:name` | Named in-memory database; later connects with the same name share its catalog |
| `:default:` | The module's default connection (also `duckdb.default_connection()`) |
| file path | Persistent database; created if missing (extension irrelevant) |

```python
con = duckdb.connect("file.db")
con.execute("CREATE TABLE test (i INTEGER)")
con.execute("INSERT INTO test VALUES (42)")
con.table("test").show()
con.close()

with duckdb.connect("file.db") as con:          # closed at the end of the block
    con.execute("INSERT INTO test VALUES (43)")

con = duckdb.connect(config={"threads": 1})
con = duckdb.connect(config={"threads": 4, "async_threads": 4})
con = duckdb.connect("compatible.db", config={"storage_compatibility_version": "v1.5.0"})
```

- `read_only=True` never creates the file and is **required** if several processes open the same file. Within one process, all connections to a file must use the same configuration, including `read_only` (see [Connecting, Persistence and Concurrency](../../connect/connecting-and-concurrency.md)).
- Each database starts asynchronous I/O threads: by default four times the CPU cores, at most 256. Every `connect()` to an unnamed in-memory database starts a new database, so set `async_threads` if you open many.
- DuckDB 1.5 cannot open a file DuckDB 2.0 wrote in its default format; use `storage_compatibility_version: "v1.5.0"` to stay compatible.
- `duckdb.set_default_connection(con)` makes another connection the module default. Library authors should create their own connections rather than use the shared global database.
- Nearly every connection method exists on the module; exceptions include `duckdb.df(frame)` (build a relation, like `con.from_df`) vs `con.df()` (fetch the `execute()` result), and `duckdb.arrow(obj)`.
- Connections close when out of scope or on `close()`; the database closes with its last connection.

### Extensions

`con.install_extension()` / `con.load_extension()` mirror `INSTALL` / `LOAD`; many core extensions autoload. Community extensions: `con.install_extension("h3", repository="community")`. Unsigned extensions need `config={"allow_unsigned_extensions": "true"}` — only from trusted sources (see [Extensions](../../configuration/extensions.md)).

## DB-API 2.0

The API follows PEP 249, similar to `sqlite3`. `execute()` returns the connection; fetch with `fetchone()` (`None` when exhausted), `fetchmany(size)` (default one row) and `fetchall()`.

```python
con = duckdb.connect()
con.execute("CREATE TABLE items (item VARCHAR, value DECIMAL(10, 2), count INTEGER)")
con.execute("INSERT INTO items VALUES ('jeans', 20.0, 1), ('hammer', 42.2, 2)")
print(con.rowcount)          # 2
con.execute("SELECT * FROM items")
print(con.fetchone())        # ('jeans', Decimal('20.00'), 1)
print(con.fetchmany(5))      # [('hammer', Decimal('42.20'), 2)]
```

`description` holds column names; `rowcount` is the number of rows changed by the last `INSERT`/`UPDATE`/`DELETE` (summed over `executemany()` parameter sets) and `-1` after a query or a `RETURNING` statement.

### Open results

A query's result stays open until a fetch returns no rows or `fetchall()`/`df()`/`fetchnumpy()` reads the rest. While open, anything that runs a query on that connection (reading a relation, `register()`, `create_function()`) raises:

```console
_duckdb.ResourceInUseException: Resource In Use Error: connection has an unfinished result from execute(); call complete() or abort(), ...
```

`con.complete()` runs the result to its end; `con.abort()` cancels it (failing an open transaction). Building relations, `description` and `cursor()` still work. `execute()` results have no `fetch_arrow_table()`, `fetch_record_batch()`, `arrow()` or `pl()`; use a relation for Arrow/Polars output.

### Transactions

`con.begin()`, `con.commit()`, `con.rollback()` correspond to `BEGIN`/`COMMIT`/`ROLLBACK`. In 2.0, **any** failing statement inside a transaction aborts it; then `commit()` rolls back and other statements raise `TransactionContext Error: Current transaction is aborted (please ROLLBACK)`.

## Threads and `cursor()`

A connection runs one call at a time. A call from another thread while it is busy does **not** wait; it raises `ResourceInUseException` (`connection is busy with another call; ... use a separate connection from cursor()`). `duckdb.sql()`, other module functions and `duckdb.connect(":default:")` share one default connection, so the same applies. Give each thread its own cursor:

```python
import threading
con = duckdb.connect()
con.execute("CREATE TABLE numbers AS SELECT range AS n FROM range(1000)")

def count_even(cursor, results):
    results.append(cursor.sql("SELECT count(*) FROM numbers WHERE n % 2 = 0").fetchall())

results = []
threads = [threading.Thread(target=count_even, args=(con.cursor(), results)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
```

`cursor()` opens a new connection to the same database, with its own transaction and session settings (such as `search_path`); global settings like `threads` or `memory_limit` apply to the whole database. Code running inside a query (such as a Python UDF) cannot use that query's connection. If using pandas or NumPy with threads, import it (and `numpy.core.multiarray`) before starting threads to avoid deadlocks or crashes.

## Jupyter notebooks

In a plain cell `duckdb.sql("SELECT * FROM sales WHERE price > 30")` displays a table; add `.df()` to keep a DataFrame. With JupySQL (`pip install jupysql pandas matplotlib duckdb-engine`):

```python
%config SqlMagic.autopandas = True
%config SqlMagic.feedback = 0
%config SqlMagic.displaycon = False
%load_ext sql
conn = duckdb.connect(config={"python_scan_all_frames": True})
%sql conn --alias duckdb
```

```sql
%sql res << SELECT 'Off and flying!' AS a_duckdb_column;
%sql duckdb:///:memory:          -- via SQLAlchemy instead
```

Caveats: notebook DataFrames are found only with `python_scan_all_frames` (`%sql SET python_scan_all_frames=true` for SQLAlchemy); with JupySQL 0.11.1 `%sqlplot boxplot` fails on a native connection (`percentile_disc does not exist`) — use SQLAlchemy; `duckdb:///:default:` fails; SQL variables are not recognized on native connections; `DESCRIBE tbl` returns an empty table (use `FROM (DESCRIBE tbl)`). `magic_duckdb` is an alternative.

## Known issues

- `EXPLAIN` output shows literal `\n`; use `print(duckdb.sql("SELECT 42 AS x").explain())`.
- Windows `ImportError: DLL load failed` or access violations usually mean an outdated MSVC Redistributable; update it or `python3 -m pip install duckdb --no-binary duckdb`.
- Fetching `TIMESTAMP WITH TIME ZONE` needs `pytz`.
- `max_temp_directory_size` in `connect(config=...)` is ignored; use `con.execute("SET max_temp_directory_size = '10GB'")`.
- Ibis 12.0.0 fails on several operations with DuckDB 2.0 (see [Python Integrations](integrations.md)).

## Migrating Python code from 1.x to 2.0

| Area | Change in 2.0 |
| --- | --- |
| Python | 3.11+ required |
| `execute()` Arrow/Polars | `fetch_arrow_table()`, `fetch_record_batch()`, `arrow()`, `pl()` removed; use `con.sql(query).to_arrow_table()` |
| Relation fetching | `rel.fetchone()`, `fetchmany()`, `execute()`, `fetch_df_chunk()` removed |
| Strings in expressions | Plain strings are values, not column names |
| Dotted names | `col("t.x")` is one name; use `col("t", "x")` |
| Non-string dict keys | Become `MAP` in `values()`/expressions |
| Column names like methods | `rel.offset` is now a method; use `rel["offset"]` |
| `sql()` on DDL | Returns a relation instead of `None` |
| Open results / threads | Concurrent use raises `ResourceInUseException` instead of waiting |
| Transactions | Any failed statement aborts the transaction |
| `overwrite=False` writes | Raise `IOException` if the file exists |
| `Decimal("1E+2")` | `DECIMAL(3,0)` holding 100 (was `DECIMAL(3,2)`) |
| Arrow batch size | Default 131072 rows (was 1000000) |
| Database files | 1.5 cannot read 2.0 default-format files |

See also [Installation, Requirements, Docker, Migration](../../operations/installation-migration-and-footprint.md) for non-Python migration.
