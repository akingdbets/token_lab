---
type: reference
title: Python Expression API, UDFs, Types and Appender
description: Build relational filters and computed columns with col(), lit(), when(), fn() and friends; register Python UDFs with create_function (native or Arrow, NULL and exception handling, side effects); describe SQL types with DuckDBPyType; and bulk-insert, upsert, update or delete rows with the Python appender.
tags: [python, expression-api, udf, create-function, types, duckdbpytype, appender, upsert]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-8c9add15d4c677ba83c935de
    resource: repo://docs/2.0/clients/python/appender.md
  - id: openwiki-source-6cf882b96613dcfa3de69d30
    resource: repo://docs/2.0/clients/python/expression.md
  - id: openwiki-source-47e450247a64ba257e679d6f
    resource: repo://docs/2.0/clients/python/function.md
  - id: openwiki-source-d9eea6f9767a3a27e75d152b
    resource: repo://docs/2.0/clients/python/types.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Python Expression API, UDFs, Types and Appender

These Python-only APIs complement the [Python Relational API](relational-api.md): expressions are what you pass to relation methods, UDFs let SQL call Python, the Types API describes SQL types, and the appender inserts Python-produced rows. Value conversion rules are in [Python Data Ingestion and Conversion](dataframes-and-arrow.md).

## Expression API

Expressions build filters and computed columns when names or conditions depend on code. They are passed to relation methods such as `select`, `filter`, `aggregate` and `sort`; `str()` of an expression returns its SQL text.

```python
import duckdb
import pandas as pd
from duckdb import col

sales = pd.DataFrame({"item": ["jeans", "hammer"], "price": [20, 42]})
price_column = "price"
rel = duckdb.from_df(sales)
print(rel.filter(col(price_column) > 30).fetchall())   # [('hammer', 42)]
print((col("a") > 1) & col("b"))                       # (("a" > 1) AND "b")
```

| Helper (preferred) | Older constructor |
| --- | --- |
| `col(name)` | `ColumnExpression(name)` |
| `lit(value)` | `ConstantExpression(value)` |
| `when(condition).then(value)` | `CaseExpression(condition, value)` |
| `fn(name, *args)` | `FunctionExpression(name, *args)` |
| `star(exclude=...)` | `StarExpression(exclude=...)` |
| `sql_expr(text)` | `SQLExpression(text)` |
| `coalesce(*values)` | `CoalesceOperator(*values)` |
| Python function such as `lambda x: x * 2` | `LambdaExpression(lhs, rhs)` |
| `.is_null()`, `.is_not_null()` | `.isnull()`, `.isnotnull()` |

**Operators:** `+ - * / // % **`, comparisons `== != < <= > >=`, and `&`, `|`, `~` for `AND`, `OR`, `NOT`. A Python value in an operation is a **constant**, including strings: `col("s") == "x"` compares with the text `'x'`, not column `x`. If the string is also a column name, DuckDB warns (`UserWarning: 'x' is used as a string value, and it is also a column name ...`). Expressions have no truth value: `if col("a") == 1:` raises `TypeError`.

**Columns:** `col("st.a")` is the column literally named `st.a`; for qualified names or struct fields use `col("st", "a")` or `col("st")["a"]`. `[]` also indexes maps by key and lists by 1-based position.

**Star:** `star(exclude=['b'])`, `star(exclude="b", rename={"c": "total"})`. To exclude one side's column in a join, use `StarExpression(exclude=[col("t", "b")])`.

**Case:** branches are tried in order; `.end()` without `.otherwise()` leaves `NULL`.

```python
from duckdb import col, when
size = (
    when(col("c") > 40).then("large")
    .when(col("c") > 20).then("medium")
    .otherwise("small")
    .alias("size")
)
```

**Functions:** plain string arguments are values (`fn('upper', 's')` passes the text `s`). Keyword arguments become named arguments: `fn("round", col("x"), precision=1)`. Python functions become SQL lambdas:

```python
from duckdb import fn
rel = duckdb.sql("SELECT [1, 2, 3] AS l")
print(rel.select(fn("list_transform", col("l"), lambda v: v * 10)).fetchall())  # [([10, 20, 30],)]
```

**SQL text:** `sql_expr("price * 2").alias("double_price")` splices text in as-is (`SQLExpression` also checks it is one expression). Never build either from untrusted input.

**Aggregates and windows:** methods such as `.sum()`, `.mean()`, `.min()`, `.max()`, `.count()`, `.median()`, `.string_agg()`, `.array_agg()`, `.arg_max()`, `.arg_min()`, plus `count_all()`; `.where(cond)` adds a filter. `.over(partition_by=..., order_by=..., rows=..., range=...)` makes a window, with `(start, end)` bounds relative to the current row and `None` meaning unbounded (`rows=(-2, 0)` is the current and two preceding rows).

```python
from duckdb import count_all, lag, row_number
rel = duckdb.sql("SELECT * FROM (VALUES ('a', 1), ('a', 2), ('b', 3)) t(g, x)")
rel.select(col("x").sum(), col("x").sum().where(col("g") == "a"), count_all())
rel.select(row_number().over(partition_by=col("g"), order_by=col("x")).alias("n"),
           lag(col("x")).over(order_by=col("x")).alias("previous"))
```

**Function families:** `.str()`, `.dt()`, `.list()`, `.json()` expose namespaced functions: `col("s").str().upper()`, `col("d").dt().year()`, `col("l").list().sort()`.

**Common operations:** `.alias(name)`, `.cast(type)`, `.try_cast(type)`, `.isin(*values)`, `.isnotin(*values)`, `.between(low, high)` (inclusive), `.like(pattern)`, `.ilike(pattern)`, `.collate(collation)`, `.concat(*values)`. For `order()`/`sort()`: `.asc()`, `.desc()`, `.nulls_first()`, `.nulls_last()`.

## Python UDFs: `create_function`

```python
import duckdb

def add_one(x: int) -> int:
    return x + 1

con = duckdb.connect()
con.create_function("add_one", add_one)
print(con.sql("SELECT add_one(41)").fetchall())   # [(42,)]
con.remove_function("add_one")
```

UDFs require NumPy (else `InvalidInputException: 'numpy' is required ...`). Signature:

`create_function(name, function, parameters=None, return_type=None, *, type=..., null_handling=..., exception_handling=..., side_effects=False)`

| Parameter | Meaning / default |
| --- | --- |
| `name` | Unique name in the connection catalog |
| `function` | Python callable (partials work; fixed args are not UDF parameters) |
| `parameters` | List of input types; if omitted, taken from annotations (unannotated = any type) |
| `return_type` | Return type; must be given or annotated, else `Could not infer the return type` |
| `type` | `'native'` (default, one tuple at a time) or `'arrow'` (batches of `pyarrow.ChunkedArray`, at most 2048 rows; much more efficient) |
| `null_handling` | Default `NULL`-in/`NULL`-out; `'special'` passes `NULL`s to the function |
| `exception_handling` | Default: query fails with `InvalidInputException` naming the Python exception; `'return_null'` returns `NULL` (not for `MemoryError` or non-`Exception` errors like `KeyboardInterrupt`) |
| `side_effects` | Default `False` (pure); set `True` for random/stateful functions, otherwise results may be reused (`my_counter()` returns `0` for every row) |

Always use `null_handling="special"` when the function can return `NULL`:

```python
from duckdb.sqltypes import VARCHAR
def return_str_or_none(x: str) -> str | None:
    if not x:
        return None
    return x
duckdb.create_function("return_str_or_none", return_str_or_none, [VARCHAR], VARCHAR, null_handling="special")
```

Arrow UDF:

```python
import pyarrow as pa
from pyarrow import compute as pc
def mirror(strings: pa.Array, sep: pa.Array) -> pa.Array:
    return pc.binary_join_element_wise(strings, pc.ascii_reverse(strings), sep)
duckdb.create_function("mirror", mirror, [VARCHAR, VARCHAR], return_type=VARCHAR, type="arrow")
```

A UDF cannot use the connection running its query (`ResourceInUseException`); use `con.cursor()` inside it. String type names (including `CREATE TYPE` names) are resolved on the registering connection; `create_function` raises `ResourceInUseException` while an `execute()` result is open. A function annotated to return `dict` returns a `MAP`; pass a `struct_type(...)` `return_type` to return a `STRUCT`.

## Types API: `DuckDBPyType`

`duckdb.sqltypes.DuckDBPyType` describes SQL types for parameters, return types and casts. Anywhere one is expected you may pass:

- **Python built-ins:** `bool`→`BOOLEAN`, `bytearray`/`bytes`→`BLOB`, `float`→`DOUBLE`, `int`→`BIGINT`, `str`→`VARCHAR`.
- **NumPy scalar types:** `numpy.int8`→`TINYINT` … `numpy.int64`→`BIGINT`, `numpy.uint8`→`UTINYINT` … `numpy.uint64`→`UBIGINT`, `numpy.float32`→`FLOAT`, `numpy.float64`→`DOUBLE`, `numpy.bool_`→`BOOLEAN` (a `numpy.dtype` object raises `NotImplementedException`).
- **Type names:** `"INTEGER"`, `"INT[]"`, `"STRUCT(a INT)"`, `"MAP(INT, VARCHAR)"`. `CREATE TYPE` types need a connection: `DuckDBPyType("mood", connection=con)` or `con.type("mood")`.
- **Nested Python types:** `list[int]`→`BIGINT[]`, `dict[str, int]`→`MAP(VARCHAR, BIGINT)`, `{'a': str, 'b': int}`→`STRUCT(a VARCHAR, b BIGINT)`, `Union[int, str]` or `int | str`→`UNION(u1 BIGINT, u2 VARCHAR)`.
- **Constants** in `duckdb.sqltypes`: `BIGINT`, `BIT`, `BLOB`, `BOOLEAN`, `DATE`, `DOUBLE`, `FLOAT`, `HUGEINT`, `INTEGER`, `INTERVAL`, `SMALLINT`, `SQLNULL`, `TIME`, `TIME_NS`, `TIME_TZ`, `TIMESTAMP`, `TIMESTAMP_MS`, `TIMESTAMP_NS`, `TIMESTAMP_S`, `TIMESTAMP_TZ`, `TINYINT`, `UBIGINT`, `UHUGEINT`, `UINTEGER`, `USMALLINT`, `UTINYINT`, `UUID`, `VARCHAR`, `VARIANT`.

Creation functions (on the module or a connection):

```python
from duckdb.sqltypes import INTEGER, VARCHAR
duckdb.list_type(INTEGER)                          # INTEGER[]
duckdb.array_type(INTEGER, 3)                      # INTEGER[3]
duckdb.struct_type({"a": INTEGER, "b": VARCHAR})   # also row_type; a list names fields v1, v2, ...
duckdb.map_type(VARCHAR, INTEGER)
duckdb.decimal_type(10, 2)                         # width 1–38, scale 0–width
```

`union_type(members)` and `string_type(collation="")` also exist; `enum_type` is not implemented (create the `ENUM` in SQL and fetch it with `con.type()`). Inspect types with `.id` (e.g. `'struct'`), `.children`, and struct field access `point.x` / `point["y"]`.

## The Python appender

The appender collects rows from Python and writes them in one statement per **flush**. A `with` block flushes on successful exit:

```python
con = duckdb.connect()
con.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name VARCHAR)")
with con.appender("people") as appender:
    appender.append_row(1, "Mark")
    appender.append_rows([(2, "Hannes"), (3, "Gabor")])
```

For data already in a DataFrame or Arrow table, `INSERT INTO people SELECT * FROM df` (or `con.append("people", df)` for pandas) is faster. `con.appender(table)` and `con.query_appender(statement, columns)` also exist on the `duckdb` module (default connection unless `connection=` is given).

- `con.appender(table)` resolves the table once, appends in declared column order and skips generated columns. `columns=["kind"]` appends to a subset; other columns get their defaults per row.
- `action` is `"insert"` (default), `"upsert"` (an `INSERT OR REPLACE`; needs exactly one primary key or unique constraint), `"update"` (matches on `key`) or `"delete"` (appends only `key` columns). A `NULL` key matches nothing. Plain inserts keep append order while `preserve_insertion_order` is on (the default); upserts do not.

```python
with con.appender("stock", action="upsert") as appender:
    appender.append_row("widget", 10)
with con.appender("stock", action="delete", key=["sku"]) as appender:
    appender.append_row("gizmo")
```

- `con.query_appender(statement, {"col": "TYPE", ...}, source=...)` runs your `INSERT` (incl. `INSERT OR REPLACE` / `ON CONFLICT`), `UPDATE`, `DELETE` or `MERGE INTO`, reading rows as `appender_data`; an optional `source` query reads `appender_buffer` first.
- Each `flush()` runs in your open transaction or commits by itself. On an exception inside `with`, buffered rows are discarded. Outside `with`, call `flush()` or `clear()`; there is no `close()`. Garbage collection discards buffered rows with a `ResourceWarning`.
- Statement errors (invalid SQL, `RETURNING`, `?` placeholders) are raised at creation. Buffered rows count toward `memory_limit` and may spill to temporary files. Use one appender per thread; concurrent calls raise instead of waiting.

The SQL-level appender for other clients is described in [INSERT, UPDATE, DELETE, MERGE INTO and the Appender](../../sql/statements/modifying-data.md).
