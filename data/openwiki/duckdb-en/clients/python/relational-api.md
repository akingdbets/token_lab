---
type: reference
title: Python Relational API
description: Build DuckDB queries step by step with DuckDBPyRelation — lazy evaluation and materialize(), relation creation (sql, table, read_csv, from_df, values), inspection (columns, types, explain, sql_query), transformations (filter, select, aggregate, group_by, join, union_by_name, pivot, with_columns), aggregate/window function methods, and output methods (df, to_arrow_table, iter_rows, create, insert_into, write_csv, write_parquet).
tags: [python, relational-api, duckdbpyrelation, lazy-evaluation, join, aggregate, write-parquet, write-csv]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-ce10bae30f89bd45e504feec
    resource: repo://docs/2.0/clients/python/relational_api.md
  - id: openwiki-source-57bbbc7aa78b3c5f50eaf92f
    resource: repo://docs/2.0/guides/python/relational_api_pandas.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Python Relational API

A relation (`DuckDBPyRelation`) is a piece of SQL text. Transformation and function methods return a **new** relation whose SQL extends the one they were called on; output methods run it. Expressions passed to these methods are described in [Python Expression API, UDFs, Types and Appender](expressions-udfs-and-types.md); connections in [Python Client: Installation, Connections, DB-API and Threads](getting-started.md).

## Lazy evaluation

Building a relation runs nothing: DuckDB binds the text once to learn column names and types and holds no data.

```python
import duckdb
duckdb_conn = duckdb.connect()
rel = duckdb_conn.sql("FROM range(1_000_000_000) t(id) SELECT id, id % 7 AS bucket")
print(rel.sql_query())   # FROM range(1_000_000_000) t(id) SELECT id, id % 7 AS bucket
rel.filter("bucket = 3").order("id").limit(3).show()
```

- The query runs when an output method reads the relation, and **again on every read**, so each read sees current data. Printing a relation or `show()` also runs it.
- Only reading statements (e.g. `SELECT`) are lazy. Any other statement passed to `sql()` (`CREATE TABLE`, `INSERT`) runs at the call, and the relation holds what it returned.
- `params` are copied when the relation is created and converted on each run.
- Columns are attributes (`rel.price`) unless a method has that name: a column `offset` is `rel["offset"]`.
- `materialize()` runs once and returns a relation over rows held in client memory (it replaces the removed `execute()`; `create_view()` refuses a materialized relation):

```python
duckdb_conn.sql("CREATE TABLE items (id INTEGER)")
counted = duckdb_conn.sql("SELECT count(*) AS n FROM items")
held = counted.materialize()
duckdb_conn.sql("INSERT INTO items VALUES (1), (2)")
print(counted.fetchall(), held.fetchall())   # [(2,)] [(0,)]
```

## Creating relations

| Method | Description |
| --- | --- |
| `sql(query, params=...)` (aliases `query`, `from_query`) | Reading statements give a lazy relation; other statements run now; earlier statements in a multi-statement string run immediately |
| `table(name)`, `view(name)` | Relation over a table or view |
| `read_csv(name, ...)` (alias `from_csv_auto`), `read_json(name, ...)`, `read_parquet(path_or_buffer, ...)` (alias `from_parquet`) | File readers |
| `from_df(df)`, `from_arrow(obj)` | Relation from a DataFrame / Arrow object |
| `table_function(name, parameters)` | Relation from a table function |
| `values(...)` | Relation from Python values |

## Inspecting relations

| Method | Description |
| --- | --- |
| `columns`, `types` (alias `dtypes`), `shape`, `description` | Column names, types, `(rows, columns)`, result description |
| `alias`, `set_alias(name)` | Get / set the relation alias |
| `describe()` | Basic statistics (min, max, NULLs) per column |
| `explain()` | Plan as text (HTML in Jupyter) |
| `preview(limit)`, `show()` | Draw the first rows |
| `sql_query()` | Equivalent SQL; `params=` values stay markers |
| `query(virtual_table_name, sql_query)` | Run SQL over the relation exposed as a view |
| `type` | Relation type |

## Transformations

All build a new query and run nothing.

| Method | Description |
| --- | --- |
| `filter(filter_expr)` | `WHERE` (SQL text or Expression) |
| `select(...)` (alias `project`), `select_types(...)` (alias `select_dtypes`) | Projection; select columns by type |
| `with_columns(**columns)` | Add columns; same-named columns replaced in place |
| `drop(...)`, `rename(old=new)` | Remove / rename columns |
| `aggregate(aggr_expr, group_expr='')` | Aggregate; `''` or `None` groups by every non-aggregate column (`GROUP BY ALL`) |
| `group_by(*columns).agg(*aggregates)` | Grouped aggregation |
| `apply(...)` | Apply a function to columns by optional groups |
| `distinct(on=...)` | Distinct rows, or first row per distinct `on` value |
| `order(order_expr)`, `sort(*args)` | Ordering (`'price DESC'` or Expressions) |
| `limit(n, offset)`, `offset(n)`, `head(n)` | Row limits |
| `sample(n / percent, seed)` | Random subset |
| `join(other_rel, condition, how='inner', suffix=None)` | Joins (see below) |
| `cross(other)` | Cartesian product |
| `union`, `intersect`, `except_` | Set operations |
| `union_by_name(other, all=...)` | Union matching columns by name; keeps duplicates unless `all` is false |
| `pivot(column, values, aggregate)` | `PIVOT` with explicit values |
| `unpivot(...)` | Columns to rows (`name`/`value` columns) |
| `unnest(...)` | One row per list element |
| `map(function)` | Call a Python function on the relation |

### Joins

`join(other_rel, condition=None, how='inner', suffix=None)` supports `how` = `'inner'`, `'left'`, `'right'`, `'outer'`, `'full'`, `'semi'`, `'anti'`, `'cross'`, `'positional'`, `'natural'` and `'asof'`. The condition may be SQL text (`'a.id = b.id'`), a column name or list of names (a `USING` join), an Expression, or a function of the two sides. Inner/left/right/outer/full/semi/anti/asof joins require a condition (else `InvalidInputException`); cross, positional and natural joins take none. `suffix` renames right-side columns that clash with the left side (`USING`/natural join columns keep their names).

```python
left = duckdb_conn.sql("SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) AS t(id, name)")
right = duckdb_conn.sql("SELECT * FROM (VALUES (1, 'x'), (3, 'z'), (4, 'w')) AS t(id, name)")
print(left.join(right, "id").order("id"))
left.join(right, lambda a, b: a["id"] == b["id"], how="left", suffix="_right").order("id")
```

See [FROM Clause and Joins](../../sql/query-syntax/joins.md) for the semantics of each join type.

### Chaining on pandas

```python
import duckdb, pandas
con = duckdb.connect()
input_df = pandas.DataFrame.from_dict({'i': [1, 2, 3, 4], 'j': ["one", "two", "three", "four"]})
rel = con.from_df(input_df)
# equivalent to: SELECT i, j, i*2 AS two_i FROM input_df WHERE i >= 2 ORDER BY i DESC LIMIT 2
transformed_rel = rel.filter('i >= 2').select('i, j, i*2 AS two_i').order('i DESC').limit(2)
output_df = transformed_rel.df()
```

## Function methods

Relations have methods that compute aggregate or window results (they also build a query and run nothing): `any_value`, `arg_max`, `arg_min`, `avg` (alias `mean`), `bit_and`, `bit_or`, `bit_xor`, `bitstring_agg`, `bool_and`, `bool_or`, `count`, `favg` and `fsum` (Kahan summation), `first`, `last`, `geomean`, `histogram`, `list`, `max`, `min`, `median`, `mode`, `product`, `quantile_cont`, `quantile_disc` (alias `quantile`), `stddev_pop`, `stddev_samp` (aliases `std`, `stddev`), `var_pop`, `var_samp` (aliases `var`, `variance`), `string_agg`, `sum`, `unique`, `value_counts`, and window functions `cume_dist`, `dense_rank` (alias `rank_dense`), `first_value`, `last_value`, `lag`, `lead`, `n_tile`, `nth_value`, `percent_rank`, `rank`, `row_number`. Their SQL counterparts are documented in [Aggregate Functions](../../sql/functions/aggregate.md) and [Window Functions](../../sql/functions/window.md).

## Output methods

| Method | Description |
| --- | --- |
| `fetchall()` | All rows as tuples |
| `iter_rows(batch_size=1024)` | Rows in batches from **one** run; connection free between batches (replaces 1.x `fetchone()`/`fetchmany()` loops) |
| `to_dicts()` | Rows as dicts |
| `df()` (aliases `fetchdf`, `to_df`), `pl()`, `fetchnumpy()`, `torch()`, `tf()` | DataFrame / Polars / NumPy / tensors |
| `to_arrow_table()`, `to_arrow_reader()` (alias `arrow`) | Arrow; `fetch_arrow_table`, `fetch_arrow_reader`, `fetch_record_batch` are deprecated aliases |
| `create(table_name)` (alias `to_table`) | New table from the relation |
| `create_view(view_name)` (alias `to_view`) | View over the relation |
| `insert_into(table_name)` | Insert into an existing table |
| `insert(values)` | Insert one row into the table the relation reads (from `table()`) |
| `update(set, *, condition=None)` | Update the table the relation reads; string values raise `TypeError` (use `col()`/`lit()`) |
| `write_csv(...)` (alias `to_csv`), `write_parquet(...)` (alias `to_parquet`) | Write files |
| `close()` | Does nothing (relations hold no result) |

### `write_csv` and `write_parquet`

Options mirror [`COPY ... TO`](../../sql/statements/copy-and-export.md). `overwrite` maps to `OVERWRITE_OR_IGNORE`: omitted or `True` replaces an existing file, **`False` raises `IOException`** (changed in 2.0).

`write_csv(file_name, *, sep, na_rep, header, quotechar, escapechar, date_format, timestamp_format, quoting, encoding, compression, overwrite, per_thread_output, use_tmp_file, partition_by, write_partition_columns)`:

| Parameter | Maps to / default when omitted |
| --- | --- |
| `sep` | `DELIMITER`; comma |
| `na_rep` | `NULL`; empty |
| `header` | written |
| `quotechar` / `escapechar` | `QUOTE` / `ESCAPE`; `"` |
| `quoting` | `csv.QUOTE_ALL`, `'ALL'` or `'FORCE'` quotes every value; otherwise only where needed |
| `encoding` | only `'utf-8'` / `'utf8'` |
| `compression` | `'none'`, `'gzip'`, `'zstd'`; chosen from the extension |

`write_parquet(file_name, *, compression, field_ids, row_group_size_bytes, row_group_size, overwrite, per_thread_output, use_tmp_file, partition_by, write_partition_columns, append, filename_pattern, file_size_bytes)`:

| Parameter | Default / notes |
| --- | --- |
| `compression` | `'snappy'`; also `'uncompressed'`, `'gzip'`, `'zstd'`, `'brotli'`, `'lz4'`, `'lz4_raw'` |
| `row_group_size` | 122880 rows |
| `row_group_size_bytes` | bytes or text such as `'2MB'` |
| `field_ids` | dict of column → id, or `'auto'` |
| `partition_by` | Hive-partitioned directories under `file_name` (see [Multiple Files and Hive Partitioning](../../data/multiple-files-and-partitioning.md)) |
| `append` | choose new names instead of overwriting generated files; with `overwrite` raises `BinderException` |
| `filename_pattern` | `{i}` index, `{uuid}` UUID |
| `file_size_bytes` | start a new file past this size (e.g. `'1MB'`) |

`per_thread_output` writes one file per thread into a directory; `use_tmp_file` writes to a temporary file first so a cancelled write does not leave a broken file.

```python
rel = duckdb_conn.sql("SELECT * FROM (VALUES (1, 'jeans', 'clothing', 20, TRUE)) AS items(id, item, category, price, in_stock)")
rel.write_csv("items.csv")
rel.write_parquet("items_by_category", partition_by=["category"])
```
