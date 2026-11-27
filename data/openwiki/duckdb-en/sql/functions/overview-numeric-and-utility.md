---
type: reference
title: Function Basics, Numeric and Utility Functions
description: How to call DuckDB functions (dot-operator chaining, listing functions with duckdb_functions()), numeric operators including / vs // and division-by-zero behavior, the ! factorial precedence change in 2.0, numeric functions (round, round_even, trunc, log, gcd, random, decimal_division new in 2.0), and utility scalar and table functions (coalesce, nullif, typeof, hash, uuid, current_setting, query, query_table, glob, repeat_row, sql_tokenize).
tags: [sql, functions, numeric, operators, utility, method-chaining, uuid, typeof]
verified:
  - by: openwiki/0.7.0
    at: 2026-11-27T12:34:27.566Z
sources:
  - id: openwiki-source-1b00c07b9319313224cc65d2
    resource: repo://docs/2.0/sql/functions/numeric.md
  - id: openwiki-source-7f5b8756920cfca800bdd5c0
    resource: repo://docs/2.0/sql/functions/overview.md
  - id: openwiki-source-1d83ce13b6fa7de7b570f155
    resource: repo://docs/2.0/sql/functions/utility.md
generated: { by: "claude-code", at: "2026-11-27T12:34:27.566Z" }
---

# Function Basics, Numeric and Utility Functions

Other function families: [text](text-and-pattern-matching.md), [list/array/lambda](list-array-and-lambda.md), [struct/map/union](struct-map-and-union.md), [date/time](date-and-time.md), [timestamp](timestamp.md), [aggregate](aggregate.md), [window](window.md); BLOB and bitstring functions are on [Numeric, Text, BLOB and BITSTRING Types](../data-types/numeric-text-and-binary.md).

## Calling functions

**Dot-operator chaining** rewrites `fn(arg1, arg2, ...)` as `arg1.fn(arg2, ...)`:

```sql
SELECT goose_name.replace('goose', 'duck') AS duck_name
FROM unnest(['African goose', 'Faroese goose', 'Hungarian goose', 'Pomeranian goose']) breed(goose_name);
SELECT 'hello world'.replace(' ', '_');
SELECT m[1].map_entries() FROM (VALUES ([MAP {'hello': 42}, MAP {'world': 42}])) t(m);
SELECT (2).sqrt();          -- numeric literals need parentheses; 2.sqrt() is a Parser Error
```

Chaining works only for **scalar** functions, not table functions (`('my_file.parquet').read_parquet()` fails). Named arguments use `:=` (e.g. `read_csv('f.csv', header := true)` or `=`).

**Listing functions:** `duckdb_functions()` returns names, types, parameters, parameter types and descriptions:

```sql
SELECT DISTINCT ON(function_name) function_name, function_type, return_type, parameters, parameter_types, description
FROM duckdb_functions()
WHERE function_type = 'scalar' AND function_name LIKE 'b%'
ORDER BY function_name;
```

The CLI's `.manual FUNCTION` shows the same information (see [CLI Dot Commands](../../clients/cli/dot-commands-and-output-formats.md)).

## Numeric operators

| Operator | Description | Example | Result |
| --- | --- | --- | --- |
| `+`, `-`, `*` | Arithmetic | `2 * 3` | `6` |
| `/` | **Float** division | `5 / 2` | `2.5` |
| `//` | Integer division | `5 // 2` | `2` |
| `%` | Modulo | `5 % 4` | `1` |
| `**`, `^` | Exponent | `3 ** 4` | `81` |
| `&`, `\|` | Bitwise AND / OR | `91 & 15` | `11` |
| `<<`, `>>` | Bit shifts | `1 << 4` | `16` |
| `~` | Bitwise negation | `~15` | `-16` |
| `!` | Factorial | `4!` | `24` |

- `/` and `//` are equivalent when either operand is `FLOAT`/`DOUBLE`; with two integers, `/` is float division (unlike PostgreSQL).
- **Division by zero (2.0):** `//`, `%` and `INTERVAL / 0` raise `Invalid Input Error` instead of returning `NULL`; use `TRY(1 // 0)` or the deprecated `SET error_on_division_by_zero = false`. Float `1 / 0` returns `inf`.
- **`!` precedence changed in 2.0:** `SELECT 2 * 3!;` returns `12` (`2 * (3!)`), whereas 1.5 returned `720`; write `(2 * 3)!` for the old result.
- Bitwise, negation and factorial operators work only on integral types.
- `-2^2` is `4.0` because unary minus binds tighter (see [SQL quirks](../dialect/introduction-and-compatibility.md)).

## Numeric functions

| Function | Description |
| --- | --- |
| `abs(x)`, `@(x)` | Absolute value |
| `ceil(x)` (`ceiling`), `floor(x)`, `trunc(x)` | Round up / down / truncate |
| `round(v, s)` | Round to `s` decimals, halves **away from zero**; `s < 0` allowed |
| `round_even(v, s)` (`roundbankers`) | Round half to even |
| `even(x)` | Round to next even number away from zero |
| `sqrt(x)`, `cbrt(x)`, `pow(x, y)` (`power`), `exp(x)` | Roots and powers |
| `ln(x)`, `log(x)` (`log10`, base 10), `log2(x)` | Logarithms |
| `sin`, `cos`, `tan`, `cot`, `asin`, `acos`, `atan`, `atan2(y, x)`, `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh` | Trigonometry |
| `degrees(x)`, `radians(x)`, `pi()` | Angle conversion |
| `factorial(x)`, `gamma(x)`, `lgamma(x)`, `binom(n, k)` (`HUGEINT`) | Combinatorics |
| `gcd(x, y)` (`greatest_common_divisor`), `lcm(x, y)` (`least_common_multiple`) | GCD / LCM |
| `greatest(x1, ...)`, `least(x1, ...)` | Max / min of arguments |
| `sign(x)`, `signbit(x)` | Sign (−1, 0, 1) / sign bit |
| `isfinite(x)`, `isinf(x)`, `isnan(x)` | Float classification |
| `nextafter(x, y)` | Next float toward `y` |
| `fdiv(x, y)`, `fmod(x, y)` | Floored division / modulo as `DOUBLE` |
| `decimal_division(x, y)` | Exact decimal division returning `DECIMAL` — **new in 2.0** |
| `random()`, `setseed(x)` | Random in `[0.0, 1.0)` / set seed |
| `bit_count(x)`, `xor(x, y)` | Bit operations |
| `add`, `subtract`, `multiply`, `divide` | Function forms of `+`, `-`, `*`, `//` |

## Utility scalar functions

| Function | Description |
| --- | --- |
| `coalesce(expr, ...)`, `ifnull(expr, other)` | First non-`NULL` value |
| `nullif(a, b)` | `NULL` if `a = b`, else `a` |
| `if(a, b, c)` | Ternary conditional |
| `constant_or_null(arg1, arg2)` | `NULL` if `arg2` is `NULL`, else `arg1` |
| `typeof(expr)`, `pg_typeof(expr)`, `get_type(expr)` | Result type name (lowercase for `pg_typeof`; `TYPE` value for `get_type`) |
| `can_cast_implicitly(source, target)` | Whether an implicit cast exists |
| `make_type(name, ...)`, `replace_type(value, source_type, target_type)` | Build `TYPE` values / recursively recast fields |
| `alias(column)` | Column name |
| `current_setting('name')` | Setting value |
| `current_database()`, `current_catalog()` (default `memory`), `current_schema()` (default `main`), `current_schemas(bool)`, `in_search_path(db, schema)` | Catalog context |
| `current_query()`, `current_query_id()`, `txid_current()`, `version()` | Session info |
| `nextval('seq')`, `currval('seq')` | Sequences (`nextval` must be called before `currval`) |
| `getvariable('name')` | SQL variable or `NULL` |
| `getenv(var)` | Environment variable — **CLI only** |
| `hash(value)` | `UBIGINT` hash (may change across versions) |
| `md5`, `md5_number`, `md5_number_lower`, `md5_number_upper`, `sha1`, `sha256` | Hashes |
| `uuid()` (`uuidv4()`, `gen_random_uuid()`), `uuidv7()`, `uuid_extract_version`, `uuid_extract_timestamp` | UUIDs |
| `create_sort_key(...)`, `icu_sort_key(string, collator)` | Binary-comparable sort keys |
| `equi_width_bins(min, max, bincount, nice := false)` | Histogram bin boundaries |
| `duckdb_format_sql(sql[, config])` | Pretty-format SQL text |
| `parse_formatted_bytes('16 KiB')` | Bytes as `UBIGINT` |
| `stats(expr)` | Statistics as `VARIANT` |
| `checkpoint(db)`, `force_checkpoint(db)`, `get_block_size(db)` | Storage helpers |
| `error(message)`, `sleep_ms(ms)` | Raise an error / pause |
| `read_text(source)`, `read_blob(source)` | File contents |

```sql
SELECT coalesce(NULL, NULL, 1);
SELECT typeof([1, 2]);                      -- INTEGER[]
SELECT can_cast_implicitly(1, 1.5);
SELECT uuid_extract_timestamp(uuidv7());
```

## Utility table functions

| Function | Description |
| --- | --- |
| `range([start,] stop[, step])` / `generate_series(...)` | Rows from start to stop (exclusive / inclusive) |
| `glob(search_path)` | Matching file names in column `file` (empty result if none) |
| `repeat(value, count)`, `repeat_row(varargs, num_rows)` | Repeated rows |
| `unnest(list)` | One row per element |
| `query(query_string)` | Run a constant query string (can invoke arbitrary SQL) |
| `query_table(tbl_name)` / `query_table(tbl_names, [by_name])` | Read a table by name, or union several (optionally `UNION BY NAME`) |
| `sql_tokenize(sql)` | Tokens with `start` offset and `token_type` |
| `register_external_resource_type`, `create_external_resource`, `register_external_resource`, `deregister_external_resource`, `destroy_external_resource` | External resource lifecycle (see [Extensions](../../configuration/extensions.md)) |

`query` and `query_table` enable dynamic SQL — see [CTEs, Set Operations, UNNEST and query()](../query-syntax/ctes-set-operations-unnest.md).
