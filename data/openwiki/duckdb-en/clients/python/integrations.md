---
type: guide
title: "Python Integrations: Spark API, Ibis, PyTorch, marimo and fsspec"
description: Use DuckDB from other Python ecosystems — the experimental PySpark-compatible API, Ibis (which needs DuckDB below 2.0), streaming query results into PyTorch tensors, reactive SQL cells in marimo notebooks, and querying fsspec filesystems with register_filesystem.
tags: [python, spark, pyspark, ibis, pytorch, marimo, fsspec, integrations]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-57a403501cc7aa83d0b1fe77
    resource: repo://docs/2.0/clients/python/spark_api.md
  - id: openwiki-source-78ad6cb1c395d6b2d444d4f5
    resource: repo://docs/2.0/guides/python/filesystems.md
  - id: openwiki-source-001869ee726f72e8100058a1
    resource: repo://docs/2.0/guides/python/ibis.md
  - id: openwiki-source-77a86c3fa478ed294fd3493e
    resource: repo://docs/2.0/guides/python/marimo.md
  - id: openwiki-source-6a767d964bfd442be27708db
    resource: repo://docs/2.0/guides/python/pytorch.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Python Integrations: Spark API, Ibis, PyTorch, marimo and fsspec

DuckDB's Python client plugs into several other libraries. All of them build on the core mechanics described in [Python Data Ingestion and Conversion](dataframes-and-arrow.md) (replacement scans, Arrow export) and the [Python Relational API](relational-api.md).

## PySpark-compatible Spark API (experimental)

The DuckDB Spark API implements the PySpark API; statements are translated to relational-API plans and executed by DuckDB. Covered functions are tested against **PySpark 4.2.0 and 3.5.9**.

> **Warning:** the Spark API is experimental and receives **bug fixes only** — missing features will not be added and a later release will deprecate it. The docs recommend [SQLFrame](https://github.com/eakmanrq/sqlframe) as the replacement, but SQLFrame does not support DuckDB 2.0 yet.

```python
from duckdb.experimental.spark.sql import SparkSession as session
from duckdb.experimental.spark.sql.functions import lit, col

spark = session.builder.getOrCreate()

df = spark.createDataFrame(
    [(34, "Joan"), (45, "Peter"), (23, "John"), (56, "Bob")],
    ["age", "name"],
)
df = df.withColumn("location", lit("Seattle"))
res = df.select(col("age"), col("location")).collect()
print(res)
# [Row(age=34, location='Seattle'), Row(age=45, location='Seattle'), ...]
```

`createDataFrame` also accepts a pandas DataFrame (requires pandas). Contributions must be bug fixes tested with `pytest`.

## Ibis

[Ibis](https://ibis-project.org) is a Python dataframe library with 20+ backends; DuckDB is its default. Queries are built lazily and executed by DuckDB; only `to_pandas()` pulls results back.

> **Warning:** Ibis 12.0.0 and earlier do **not** support DuckDB 2.0 (for example `list_tables()` fails). The docs' examples use DuckDB 1.5; install with DuckDB pinned below 2.0:

```batch
pip install 'ibis-framework[duckdb,examples]' 'duckdb<2'
```

```python
import ibis

con = ibis.connect("duckdb://penguins.ddb")
if "penguins" not in con.list_tables():
    con.create_table(
        "penguins", ibis.memtable(ibis.examples.penguins.fetch().to_pyarrow())
    )

penguins = con.table("penguins")        # shows the schema (lazy)
penguins.head().to_pandas()             # evaluates the expression
ibis.options.interactive = True         # preview results (limit 10 rows)
```

Common table methods:

| Method | Example |
| --- | --- |
| `filter` | `penguins.filter((penguins.species == "Gentoo") & (penguins.body_mass_g > 6000))` |
| `select` | `penguins.select("species", "island", penguins.year).limit(3)` |
| `mutate` | `penguins.mutate(bill_length_cm=penguins.bill_length_mm / 10)` |
| selectors | `import ibis.selectors as s`; `penguins.select(~s.matches("bill_length_mm"))`, `s.numeric()` |
| `order_by` | `penguins.order_by(penguins.flipper_length_mm.desc())` or `ibis.desc("flipper_length_mm")` |
| `aggregate` | `penguins.aggregate([penguins.flipper_length_mm.mean(), penguins.bill_depth_mm.max()])` |
| `group_by` | `penguins.group_by(["species", "island"]).aggregate(penguins.bill_length_mm.mean())` |

Methods chain:

```python
penguins.filter(penguins.sex == "male").group_by(["island", "year"]).aggregate(
    penguins.body_mass_g.max().name("max_body_mass")
)
```

## PyTorch

Build tensors from query results by streaming Arrow record batches. DuckDB pushes filters and column selections into the scan of an Arrow dataset, so only needed rows and columns are converted.

```batch
pip install -U duckdb numpy pyarrow torch
```

```python
import duckdb, numpy as np, pyarrow.dataset as ds, torch

con = duckdb.connect()
train_dataset = ds.dataset(str(parquet_dir))

reader = con.sql("""
    SELECT feature_0, feature_1, label
    FROM train_dataset
    WHERE label = 1
""").to_arrow_reader(batch_size=2)

for batch in reader:
    features = torch.tensor(
        np.column_stack([batch.column(0).to_numpy(), batch.column(1).to_numpy()]),
        dtype=torch.float32,
    )
    labels = torch.tensor(batch.column(2).to_numpy(), dtype=torch.int64)
    print(features.shape, labels)      # torch.Size([2, 2]) tensor([1, 1])
```

`to_arrow_reader` streams instead of materializing the whole result; while the loop holds the reader, other queries on that connection are refused (use a `cursor()`). To get everything at once, a relation's `torch()` method returns a dict with one tensor per column (`tf()` does the same for TensorFlow).

## marimo notebooks

[marimo](https://github.com/marimo-team/marimo) is a reactive notebook stored as pure Python, tightly integrated with DuckDB.

```bash
pip install "marimo[sql]"      # or: uv add "marimo[sql]"  (also installs DuckDB, Polars, PyArrow)
marimo tutorial sql
marimo edit notebook.py
```

- SQL cells are serialized as `mo.sql()` calls with an f-string, so Python values interpolate with `{}`; sanitize user-generated input to avoid SQL injection.

```python
df = mo.sql(f"SELECT 'Off and flying!' AS a_duckdb_column")
```

- A DuckDB connection created in a cell (`conn = duckdb.connect("path/to/my/duckdb.db")`) is discovered automatically and selectable in the SQL cell's connection dropdown; the Data Sources panel shows databases, schemas, tables and columns.
- SQL cells can reference local DataFrames by variable name; if the connection has a table of the same name, the table wins.
- A non-underscored output variable makes the SQL result available to other cells.
- Cells are reactive: UI elements such as `mo.ui.slider(...)` re-run dependent SQL (or mark it stale in "lazy" runtime mode):

```sql
CREATE TABLE random_data AS
    SELECT i AS id, random() AS random_value,
    FROM range({digits.value}) AS t(i);
```

Notebooks can be exported as apps or scripts, or run in the browser with WebAssembly.

## fsspec filesystems

`fsspec` support lets DuckDB query filesystems that the `httpfs` extension does not support:

```batch
pip install duckdb fsspec gcsfs
```

```python
import duckdb
from fsspec import filesystem

# raises if the filesystem interface is not installed
duckdb.register_filesystem(filesystem('gcs'))
duckdb.sql("SELECT * FROM read_csv('gcs:///bucket/file.csv')")
```

These filesystems are implemented in Python, not C++, so performance may not match `httpfs`, and as third-party libraries they may have bugs outside DuckDB's control. For native remote access and credentials, see [Importing Data Overview, File Access](../../data/overview-and-file-access.md) and [Secrets Manager](../../configuration/secrets-manager.md).
