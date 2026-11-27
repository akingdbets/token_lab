---
type: guide
title: "Python Data Ingestion and Conversion: pandas, Arrow, Polars and NumPy"
description: How the DuckDB Python client reads CSV/Parquet/JSON files, queries pandas, Polars, NumPy and Arrow objects by variable name (replacement scans), registers objects, converts results with df(), fetchnumpy(), to_arrow_table(), pl() and friends, and maps Python objects to DuckDB types.
tags: [python, pandas, arrow, polars, numpy, replacement-scans, conversion, data-ingestion]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-d9c4c93cd5f15e143b8a5943
    resource: repo://docs/2.0/clients/python/conversion.md
  - id: openwiki-source-434dc72710f96febaa97b4f6
    resource: repo://docs/2.0/clients/python/data_ingestion.md
  - id: openwiki-source-bfdcbd15203cc91a6674dd05
    resource: repo://docs/2.0/guides/python/export_arrow.md
  - id: openwiki-source-fcf7c01f049bd85257afc941
    resource: repo://docs/2.0/guides/python/polars.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Python Data Ingestion and Conversion

This page covers getting data **into** DuckDB from Python (files and in-memory objects) and getting results **out** as Python, NumPy, pandas, Arrow or Polars objects, plus the rules for converting Python values to DuckDB types. Connection basics are in [Python Client: Installation, Connections, DB-API and Threads](getting-started.md); the relation methods used here are covered in [Python Relational API](relational-api.md).

## Reading files

The module-level readers return relations and accept the same parameters as the SQL functions ([CSV](../../data/csv/reading-and-writing-csv.md), [Parquet](../../data/parquet.md), [JSON](../../data/json/loading-and-writing-json.md)):

```python
import duckdb

duckdb.read_csv("example.csv")                       # fully auto-detected
duckdb.read_csv("folder/*.csv")
duckdb.read_csv("example.csv", header = False, sep = ",")
duckdb.read_csv("example.csv", dtype = ["int", "varchar"])
duckdb.read_csv("example.csv", filename=True)        # adds a filename column

import io
duckdb.read_csv(io.BytesIO(b"a,b\n1,2\n"))           # file-like objects need fsspec

duckdb.read_parquet("example.parquet")
duckdb.read_parquet(["file1.parquet", "file2.parquet", "file3.parquet"])
duckdb.read_parquet("https://some.url/some_file.parquet")

duckdb.read_json("example.json")                     # detects NDJSON vs. regular JSON

duckdb.sql("SELECT * FROM 'example.csv'")
duckdb.sql("SELECT * FROM read_parquet('example.parquet')")
```

Write results with the relation methods `write_csv` and `write_parquet`; passing `overwrite=False` refuses to replace an existing file.

## Querying DataFrames and Arrow objects by name

DuckDB finds Python objects by their variable name through **replacement scans**, so no registration is needed:

```python
import duckdb
import pandas as pd

test_df = pd.DataFrame.from_dict({"i": [1, 2, 3, 4], "j": ["one", "two", "three", "four"]})
print(duckdb.sql("SELECT * FROM test_df").fetchall())
# [(1, 'one'), (2, 'two'), (3, 'three'), (4, 'four')]
```

This works for pandas DataFrames and Series, Polars DataFrames, LazyFrames and Series, NumPy arrays, a `dict` of one-dimensional NumPy arrays, relations, and Arrow objects (tables, record batches, arrays, chunked arrays, datasets, RecordBatchReaders and scanners).

- Only variables visible at the location of the `sql()`/`execute()` call are found; set `python_scan_all_frames` to `true` to also search calling functions.
- Disable replacement scans with `SET python_enable_replacements = false;`.
- Name precedence: objects registered with `register()` → native DuckDB tables and views → replacement scans.

Use `register()` to give an object a SQL name (useful for objects in dicts or attributes), and `CREATE TABLE ... AS` / `INSERT INTO` to materialize it:

```python
my_dictionary = {}
my_dictionary["test_df"] = pd.DataFrame.from_dict({"i": [1, 2, 3, 4], "j": ["one", "two", "three", "four"]})
duckdb.register("test_df_view", my_dictionary["test_df"])

duckdb.execute("CREATE TABLE test_df_table AS SELECT * FROM test_df")
duckdb.execute("INSERT INTO test_df_table SELECT * FROM test_df_view")
```

If columns are in a different order or missing, use `INSERT INTO my_table BY NAME SELECT * FROM my_df`. Alternatively `con.append("my_table", my_df)` appends a DataFrame directly; pass `by_name=True` to match by name. A relation's `create` method also creates a table, and a catalog-qualified name such as `other_db.main.test_df_table` creates it in an attached database. For row-by-row inserts use the [appender](expressions-udfs-and-types.md).

### Pushdown and scanning behavior

- Filters (and column selections) are pushed into **Arrow datasets** and **Polars LazyFrames**. Arrow tables, record batches, readers, scanners and Polars DataFrames are read whole and filtered afterwards.
- A `RecordBatchReader` can be scanned only once; a second scan raises `InvalidInputException: This RecordBatchReader has already been consumed and cannot be scanned again.` Read it into a table with `read_all()` first.
- Arrow tables and Polars DataFrames are scanned on all threads, so order-dependent queries without `ORDER BY` (for example using `first()`) can differ between runs.
- Any object implementing the Arrow PyCapsule interface (`__arrow_c_stream__`) can be queried by name or passed to `duckdb.from_arrow()`.

### NumPy specifics

Each array in a dict supplies one column. A two-dimensional array is accepted, with each outer array treated as a column (transpose row-major data first). Masked elements of a masked array become `NULL`. Dict keys that differ only in case get a suffix (`a` and `A` become `a` and `A_1`).

```python
import numpy as np
columns = {"id": np.array([1, 2, 3]), "value": np.array([9.0, 8.0, 7.0])}
print(duckdb.sql("SELECT * FROM columns").fetchall())   # [(1, 9.0), (2, 8.0), (3, 7.0)]
```

### pandas `object` columns

`object`-dtype columns are analyzed on a sample to pick the target type; the sample size defaults to **1000** rows. A wrong guess causes `Invalid Input Error: Failed to cast value`; increase `pandas_analyze_sample`:

```python
duckdb.execute("SET GLOBAL pandas_analyze_sample = 100_000")
```

## Converting results to Python

`con.sql()`, `con.table()`, readers and relational methods return **relations**; `con.execute()` (DB-API) returns results on the connection.

| Result | Relation | DB-API (`con.execute()`) |
| --- | --- | --- |
| Python tuples | `fetchall()`, `iter_rows(batch_size=1024)` | `fetchone()`, `fetchmany(size=1)`, `fetchall()` |
| Python dicts | `to_dicts()` | |
| NumPy | `fetchnumpy()` | `fetchnumpy()` |
| pandas | `df()` | `df()`, `fetch_df_chunk()` |
| Arrow | `to_arrow_table()`, `to_arrow_reader()` | same, but both make a copy |
| Polars | `pl()` | |
| PyTorch | `torch()` | `torch()` |
| TensorFlow | `tf()` | `tf()` |

Relations are recommended except for row-based work; they are stateless and have no `fetchone()`, `fetchmany()` or `fetch_df_chunk()` — use `limit(n).fetchall()`, `iter_rows()` or `to_arrow_reader()`.

```python
con = duckdb.connect()
con.execute("CREATE TABLE items (item VARCHAR, value DECIMAL(10, 2), count INTEGER)")
df = con.execute("SELECT * FROM items").df()
arr = con.execute("SELECT * FROM items").fetchnumpy()
tbl = con.sql("SELECT * FROM items").to_arrow_table()
```

- **NumPy:** `fetchnumpy()` returns a dict of arrays; columns with `NULL`s are masked arrays.
- **pandas:** `fetchdf()` and connection `fetch_df()` are older names of `df()`. `fetch_df_chunk(vectors_per_chunk)` returns at most vector size (2048 by default) × `vectors_per_chunk` (default 1) rows.
- **Arrow:** `to_arrow_reader(batch_size)` yields at most `batch_size` rows per batch (default **131072**); `arrow()` is an older relation-only name. On relations the reader streams; on a `con.execute()` result the rows are copied first and a `UserWarning` recommends `con.sql(query).to_arrow_table()`. While a reader is partially read, other queries on its connection raise `ResourceInUseException`.
- **Deprecated:** on relations `fetch_arrow_table()`, `fetch_record_batch()` and `fetch_arrow_reader()` are aliases; after `con.execute()`, `fetch_arrow_table()`, `fetch_record_batch()`, `arrow()` and `pl()` no longer exist, nor do `duckdb.fetch_arrow_table()`, `duckdb.fetch_record_batch()` and `duckdb.pl()`.
- **PyCapsule export:** a relation implements `__arrow_c_stream__`, so `pyarrow.table(rel)`, `pyarrow.RecordBatchReader.from_stream(rel)` and `polars.DataFrame(rel)` work (Polars without pyarrow). `pl.from_arrow(rel)` returns a Series of structs.
- **Polars:** `pl()` returns a DataFrame, `pl(lazy=True)` a LazyFrame. Install with `pip install -U duckdb 'polars[pyarrow]'`.
- **Intervals:** DuckDB's single `INTERVAL` maps to Arrow `month_day_nano_interval`; all Arrow interval and `duration[...]` types import as `INTERVAL`, so durations round-trip as `month_day_nano_interval`.

```python
rel = con.sql("SELECT i FROM range(5) AS t(i)")
with rel.to_arrow_reader(batch_size=2) as reader:
    for batch in reader:
        print(batch.to_pydict())
```

## Converting Python objects to DuckDB

The same rules apply to query parameters (`execute()`, `executemany()`, `sql(..., params=...)`), `values()` rows, expression constants and `duckdb.Value`.

| Python | DuckDB |
| --- | --- |
| `None` | `NULL` |
| `bool` | `BOOLEAN` |
| `str` | `VARCHAR` (non-UTF-8-encodable strings raise `InvalidInputException`) |
| `bytes` | `BLOB` (or `BIT` in `duckdb.Value(b"0101", duckdb.sqltypes.BIT)`) |
| `bytearray`, `memoryview` | `BLOB` (parameters must be C-contiguous) |
| `float` | always `DOUBLE` |
| `int` | first fitting of `INTEGER`, `BIGINT`, `UBIGINT`, `HUGEINT`, `UHUGEINT`; >128 bits raises an error |
| `decimal.Decimal` | `DECIMAL` sized from digits/exponent; >38 digits → `DOUBLE`; `NaN`/infinities → `FLOAT` |
| `uuid.UUID` | `UUID` |
| `datetime.timedelta` | `INTERVAL` |
| `datetime.datetime` | `TIMESTAMPTZ` with tzinfo, else `TIMESTAMP` |
| `datetime.time` | `TIMETZ` with tzinfo, else `TIME` |
| `datetime.date` | `DATE` |
| `list`, `tuple` | `LIST` of the most permissive child type (`[12345, "test"]` → `VARCHAR[]`) |
| `dict` | `STRUCT` (string keys) or `MAP` (see below) |
| NumPy arrays / `datetime64` | via `tolist()` |

Notes: `Decimal("12.5")` is `DECIMAL(3,1)`; `2**63` is `UBIGINT`. Fetching `TIMESTAMPTZ` needs `pytz` (else `Required module 'pytz' failed to import`). `datetime.max`/`min` convert to ordinary values, while `infinity`/`-infinity` are returned as `max`/`min`. A dict with exactly the keys `key` and `value` (equal-length lists) becomes a `MAP` as a parameter and in `values()`; dicts with non-string keys become a `MAP` in `values()`/expressions but a `STRUCT` with stringified field names as a parameter. NumPy integer scalars must be passed as `.item()` when used as query parameters. Use `duckdb.Value` to force a type:

```python
from duckdb.sqltypes import TINYINT
con.execute("SELECT typeof(?), typeof(?), typeof(?)", [5, 2**64, duckdb.Value(5, TINYINT)]).fetchall()
# [('INTEGER', 'HUGEINT', 'TINYINT')]
```

UDF return conversion for dicts (MAP vs STRUCT `return_type`) is covered in [Python Expression API, UDFs, Types and Appender](expressions-udfs-and-types.md).
